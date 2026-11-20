"""
Controle por gestos (fork PT-BR 1.9) — MediaPipe Hands, leve, só na CPU.

    "Jarvis, liga os gestos"      "Jarvis, desliga os gestos"      "Jarvis, status dos gestos"

Com a mão na frente da webcam:
    ✋ mão aberta (parada meio segundo)  → pausa / continua a música ou o vídeo
    👋 deslizar a mão para o lado        → troca de janela (direita = próxima, esquerda = anterior)
    🤏 pinça (polegar + indicador) e subir/descer a mão → volume
    ✌ "paz e amor" (indicador + médio)  → chama o JARVIS sem falar
    ✊ abrir e fechar a mão (2.14)        → abre o Chrome (ou o que você escolher)

Abrir e fechar a mão (2.14):
    "Jarvis, quando eu abrir e fechar a mão, abre o Spotify"   → troca o comando fixo
    "Jarvis, abre o chrome quando eu fechar a mão"             → arma só a PRÓXIMA vez (60 s)
    "Jarvis, o que o gesto da mão faz?"                        → mostra o comando atual
O comando pode ser "abrir <app>" ou "site <endereço>". Antes de rodar, passa
pelo guardião de decisões: gesto só faz o que é seguro fazer sozinho.
Para não brigar com o "mão aberta = pausa", a pausa agora espera a mão parada
0,7 s; abrir e fechar rápido (menos de 0,7 s aberta) é o gesto novo.

Usa a mesma câmera da Central e da presença (plugins/_camera_remota.py).
Precisa do mediapipe (python -m pip install mediapipe). Em versões novas do
mediapipe, o JARVIS baixa o modelo hand_landmarker.task (7 MB) sozinho.
"""

from __future__ import annotations

import math
import threading
import time
import urllib.request
from collections import deque

from plugins._comum import CONFIG, cfg, falar, registrar

PLUGIN = {
    "name": "gestos",
    "brief": "Hand gestures through the webcam (MediaPipe): open hand pauses media, swipe switches windows, pinch "
             "sets volume, peace sign wakes JARVIS.",
    "description": (
        "Hand-gesture control through the webcam. action='ligar' starts it, 'desligar' stops it, 'status' says if it is "
        "running and the last gesture. Gestures: open hand = play/pause, swipe = switch window, pinch + move up/down = "
        "volume, peace sign = wake JARVIS, open-then-close hand = runs the gesture command (default: open Chrome). "
        "action='comando' with comando ('abrir spotify', 'site youtube.com') sets what open-and-close does "
        "permanently ('quando eu abrir e fechar a mão, abre X'); without comando it tells the current one. "
        "action='armar' with comando arms it only for the NEXT open-and-close within 60 s ('abre o chrome quando "
        "eu fechar a mão'). Both turn the gestures on if they are off."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status | comando | armar"},
                                                 "comando": {"type": "STRING", "description":
                                                             "for comando/armar: 'abrir <app>' or 'site <url>'"}},
                   "required": []},
}

PLUGIN_SETTINGS = {
    "namespace": "gestos",
    "title": "Gestos (webcam)",
    "fields": [
        {"key": "ligar_ao_abrir", "label": "Ligar os gestos quando o JARVIS abrir", "type": "toggle", "default": False},
        {"key": "espelhar", "label": "Imagem espelhada (mão direita para a direita)", "type": "toggle", "default": True},
        {"key": "falar", "label": "JARVIS confirma por voz ao ser chamado com o gesto", "type": "toggle", "default": True},
        {"key": "comando_abrir_fechar", "label": "Abrir e fechar a mão faz (ex.: abrir chrome, site youtube.com)",
         "type": "text", "default": "abrir chrome"},
    ],
}

MODELO = CONFIG / "modelos" / "hand_landmarker.task"
URL_MODELO = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/"
              "hand_landmarker.task")

# índices do MediaPipe Hands
PULSO, POLEGAR_IP, POLEGAR, IND_MCP, IND_PIP, INDICADOR = 0, 3, 4, 5, 6, 8
MEIO_MCP, MEIO_PIP, MEIO, ANEL_PIP, ANEL, MIN_MCP, MIN_PIP, MINIMO = 9, 10, 12, 14, 16, 17, 18, 20


def _d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dedos(lm) -> dict:
    """Quais dedos estão esticados (lm: 21 pontos (x, y) normalizados) (pura)."""
    pulso = lm[PULSO]
    estica = lambda ponta, junta: _d(lm[ponta], pulso) > _d(lm[junta], pulso) * 1.12  # noqa: E731
    palma = _d(pulso, lm[MEIO_MCP]) or 1e-6
    return {"polegar": _d(lm[POLEGAR], lm[MIN_MCP]) > _d(lm[POLEGAR_IP], lm[MIN_MCP]) * 1.08
            and _d(lm[POLEGAR], lm[IND_MCP]) > palma * 0.45,
            "indicador": estica(INDICADOR, IND_PIP), "medio": estica(MEIO, MEIO_PIP),
            "anelar": estica(ANEL, ANEL_PIP), "minimo": estica(MINIMO, MIN_PIP)}


def gesto(lm) -> str:
    """'aberta', 'pinca', 'paz', 'punho' ou '' (pura)."""
    d = dedos(lm)
    palma = _d(lm[PULSO], lm[MEIO_MCP]) or 1e-6
    if _d(lm[POLEGAR], lm[INDICADOR]) / palma < 0.28 and not (d["anelar"] and d["minimo"] and d["medio"]):
        return "pinca"
    if all(d.values()):
        return "aberta"
    if d["indicador"] and d["medio"] and not d["anelar"] and not d["minimo"]:
        return "paz"
    if not any((d["indicador"], d["medio"], d["anelar"], d["minimo"])):
        return "punho"
    return ""


class Interpretador:
    """Transforma a sequência de mãos em ações, com confirmação e intervalo (puro, nos testes)."""

    SEGURAR_S = 0.45
    SEGURAR_ABERTA_S = 0.7       # 2.14: mão aberta parada este tempo = pausa
    ABERTA_MIN_S = 0.12          # 2.14: abrir e fechar — a mão fica aberta pelo menos isso…
    FECHAR_EM_S = 0.6            # …e fecha até este tempo depois
    INTERVALO_S = 1.4
    DESLIZE = 0.22               # fração da largura da imagem
    DESLIZE_S = 0.6
    VOLUME_POR_TELA = 120        # pontos de volume por altura inteira da imagem

    def __init__(self, espelhar: bool = True):
        self.espelhar = espelhar
        self.atual, self.desde = "", 0.0
        self.ultima_acao = -99.0
        self.disparou = False
        self.trilha = deque()
        self.pinca_y = None
        self.volume_acumulado = 0.0
        self.ultima_aberta = None    # 2.14: (início, fim, já disparou) da última mão aberta

    def alimentar(self, lm, t: float) -> list[tuple]:
        acoes: list[tuple] = []
        if lm is None:
            self.atual, self.trilha, self.pinca_y = "", deque(), None
            return acoes
        g = gesto(lm)
        x = 1 - lm[PULSO][0] if self.espelhar else lm[PULSO][0]
        if g != self.atual:
            if self.atual == "aberta":           # 2.14: guarda quando a mão aberta terminou
                self.ultima_aberta = (self.desde, t, self.disparou)
            self.atual, self.desde, self.disparou = g, t, False
            if g != "pinca":
                self.pinca_y = None
        livre = t - self.ultima_acao >= self.INTERVALO_S
        # deslizar: o pulso andou rápido para um lado
        self.trilha.append((t, x))
        while self.trilha and t - self.trilha[0][0] > self.DESLIZE_S:
            self.trilha.popleft()
        if livre and g in ("aberta", "") and len(self.trilha) >= 3:
            dx = self.trilha[-1][1] - self.trilha[0][1]
            if abs(dx) >= self.DESLIZE:
                acoes.append(("trocar_janela", dx < 0))         # voltar = para a esquerda
                self.ultima_acao, self.disparou, self.trilha = t, True, deque()
                self.ultima_aberta = None
                return acoes
        # pinça: subir/descer muda o volume
        if g == "pinca":
            y = (lm[POLEGAR][1] + lm[INDICADOR][1]) / 2
            if self.pinca_y is not None:
                self.volume_acumulado += (self.pinca_y - y) * self.VOLUME_POR_TELA
                if abs(self.volume_acumulado) >= 4:
                    passo = int(self.volume_acumulado)
                    acoes.append(("volume", passo))
                    self.volume_acumulado -= passo
            self.pinca_y = y
            return acoes
        # 2.14: abrir e fechar a mão — aberta por pouco tempo e logo depois punho
        if g == "punho" and livre and not self.disparou and self.ultima_aberta and t - self.desde >= 0.07:
            ini, fim, ja = self.ultima_aberta
            if not ja and fim - ini >= self.ABERTA_MIN_S and self.desde - fim <= self.FECHAR_EM_S:
                acoes.append(("abrir_fechar",))
                self.ultima_acao, self.disparou, self.ultima_aberta = t, True, None
                return acoes
        # gestos parados
        segurar = self.SEGURAR_ABERTA_S if g == "aberta" else self.SEGURAR_S
        if livre and not self.disparou and t - self.desde >= segurar:
            if g == "aberta" and len(self.trilha) >= 2 and abs(self.trilha[-1][1] - self.trilha[0][1]) < 0.06:
                acoes.append(("play_pause",))
            elif g == "paz":
                acoes.append(("chamar",))
            if acoes:
                self.ultima_acao, self.disparou = t, True
        return acoes


# ── MediaPipe (as duas APIs: a antiga "solutions" e a nova "tasks") ──────────
class _Detector:
    def __init__(self):
        import mediapipe as mp
        self.mp = mp
        self.modo = ""
        solucoes = getattr(mp, "solutions", None)
        if solucoes is not None and hasattr(solucoes, "hands"):
            self.maos = solucoes.hands.Hands(static_image_mode=False, max_num_hands=1, model_complexity=0,
                                             min_detection_confidence=0.6, min_tracking_confidence=0.5)
            self.modo = "solutions"
            return
        from mediapipe.tasks.python import BaseOptions, vision
        if not MODELO.exists():
            MODELO.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(URL_MODELO, timeout=60) as r:
                MODELO.write_bytes(r.read())
        op = vision.HandLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODELO)),
                                          running_mode=vision.RunningMode.VIDEO, num_hands=1,
                                          min_hand_detection_confidence=0.6, min_tracking_confidence=0.5)
        self.maos = vision.HandLandmarker.create_from_options(op)
        self.modo = "tasks"

    def mao(self, bgr, t_ms: int):
        rgb = bgr[:, :, ::-1].copy()
        if self.modo == "solutions":
            r = self.maos.process(rgb)
            if not r.multi_hand_landmarks:
                return None
            return [(p.x, p.y) for p in r.multi_hand_landmarks[0].landmark]
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        r = self.maos.detect_for_video(img, t_ms)
        if not r.hand_landmarks:
            return None
        return [(p.x, p.y) for p in r.hand_landmarks[0]]


_estado = {"ligado": False, "ultimo": "", "erro": "", "thread": None, "armado": None}


# ── 2.14: comando do "abrir e fechar a mão" ────────────────────────────────────
_APELIDOS = {"cromi": "chrome", "crome": "chrome", "cromo": "chrome", "google chrome": "chrome", "o chrome": "chrome"}


def comando_fixo() -> str:
    return str(cfg("gestos", PLUGIN_SETTINGS).get("comando_abrir_fechar") or "abrir chrome").strip()


def normalizar_comando(texto: str) -> tuple[str, str]:
    """'abre o cromi' → ('abrir', 'chrome'); 'site youtube.com' → ('site', 'youtube.com') (pura)."""
    import re
    t = (texto or "").strip()
    m = re.match(r"^(?:abr[ae]|abrir|inici[ae]r?|ligar?|execut[ae]r?|rod[ae]r?)\s+(?:o |a |os |as )?(.+)$", t, re.I)
    alvo = m.group(1).strip() if m else t
    m2 = re.match(r"^(?:site|entr[ae]r?\s+(?:no|na|em))\s+(.+)$", alvo, re.I)
    if m2:
        return "site", m2.group(1).strip()
    if re.search(r"\.(com|br|net|org|io|gg|tv)\b|^https?://", alvo, re.I):
        return "site", alvo
    return "abrir", _APELIDOS.get(alvo.lower(), alvo)


def rodar_comando(comando: str, player=None) -> str:
    tipo, alvo = normalizar_comando(comando)
    if not alvo:
        return ""
    try:
        from plugins import _guardiao
        av = _guardiao.avaliar("controle_pc", {"action": "abrir", "alvo": alvo}, f"{tipo} {alvo}")
        if av.decisao != "automático":
            return f"✊ não rodei '{comando}' pelo gesto: {av.texto()}"
    except Exception:
        pass
    if tipo == "site":
        import webbrowser
        webbrowser.open(alvo if alvo.startswith("http") else "https://" + alvo)
        return f"✊ abri {alvo}"
    try:
        from core import registro_ferramentas
        r = registro_ferramentas.executar("controle_pc", {"action": "abrir", "alvo": alvo}, player=player)
    except Exception:
        from plugins import _indice_apps
        ok, e = _indice_apps.abrir(alvo)
        r = f"Abrindo {e['nome']}." if ok else f"Não encontrei {alvo}."
    return f"✊ {r}"
_parar = threading.Event()
_iniciou = threading.Event()


def _executar(acao: tuple, player) -> str:
    from plugins import _midia
    nome = acao[0]
    if nome == "play_pause":
        _midia.tecla("play_pause")
        return "✋ pausa/continua"
    if nome == "trocar_janela":
        _midia.alt_tab(voltar=acao[1])
        return "👋 janela anterior" if acao[1] else "👋 próxima janela"
    if nome == "volume":
        from plugins.controle_audio_video import _volume
        try:
            from actions import computer_settings as cs
            atual = cs.volume_get() or 50
        except Exception:
            atual = 50
        _volume(str(max(0, min(100, atual + acao[1]))))
        return f"🤏 volume {'+' if acao[1] > 0 else ''}{acao[1]}"
    if nome == "chamar":
        try:
            from core import registro_ferramentas
            app = registro_ferramentas.app()
            if app is not None and hasattr(app, "wake"):
                app.wake(reason="gesto")
        except Exception:
            pass
        if cfg("gestos", PLUGIN_SETTINGS).get("falar", True):
            falar(player, "[GESTO] O usuário te chamou com um gesto de mão. Responda só 'Pois não, senhor?' "
                          "(no idioma da conversa). Não chame nenhuma ferramenta.")
        return "✌ JARVIS chamado"
    if nome == "abrir_fechar":                   # 2.14
        armado, _estado["armado"] = _estado.get("armado"), None
        if armado and time.time() <= armado[1]:
            return rodar_comando(armado[0], player)
        return rodar_comando(comando_fixo(), player)
    return ""


def _laco(player) -> None:
    from plugins._camera_remota import quadro
    try:
        det = _Detector()
    except ImportError:
        _estado.update(ligado=False, erro="falta o mediapipe: python -m pip install mediapipe")
        return
    except Exception as e:
        _estado.update(ligado=False, erro=f"o MediaPipe não iniciou: {e}")
        return
    interp = Interpretador(bool(cfg("gestos", PLUGIN_SETTINGS).get("espelhar", True)))
    t0 = time.monotonic()
    while not _parar.is_set():
        inicio = time.monotonic()
        img, erro = quadro(0, espera_s=3)
        if img is None:
            _estado["erro"] = erro
            time.sleep(2)
            continue
        h, w = img.shape[:2]
        if w > 480:
            import cv2
            img = cv2.resize(img, (480, int(h * 480 / w)))
        try:
            lm = det.mao(img, int((inicio - t0) * 1000))
        except Exception as e:
            _estado["erro"] = str(e)
            lm = None
        for a in interp.alimentar(lm, inicio):
            txt = _executar(a, player)
            if txt:
                _estado["ultimo"] = f"{time.strftime('%H:%M:%S')} {txt}"
                print(f"[Gestos] {txt}")
        time.sleep(max(0.0, 0.08 - (time.monotonic() - inicio)))   # ~12 quadros por segundo
    _estado["ligado"] = False


def ligar(player=None) -> str:
    t = _estado["thread"]
    if t is not None and t.is_alive():
        return "Os gestos já estão ligados."
    try:
        import mediapipe  # noqa: F401
    except ImportError:
        return ("Para os gestos eu preciso do MediaPipe: python -m pip install mediapipe (se o pip não achar versão "
                "para o seu Python, use o Python 3.12).")
    _parar.clear()
    _estado.update(ligado=True, erro="")
    _estado["thread"] = threading.Thread(target=_laco, args=(player,), daemon=True, name="gestos")
    _estado["thread"].start()
    registrar(player, "Gestos ligados.")
    return ("Gestos ligados: mão aberta pausa, deslizar troca de janela, pinça e subir ou descer muda o volume, e o "
            "sinal de paz e amor me chama, e abrir e fechar a mão faz: " + comando_fixo() + ".")


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    try:
        if acao == "ligar":
            return ligar(player)
        if acao == "desligar":
            _parar.set()
            return "Gestos desligados."
        if acao in ("comando", "armar"):          # 2.14
            comando = str((parameters or {}).get("comando") or "").strip()
            if acao == "comando" and not comando:
                return f"Abrir e fechar a mão faz: {comando_fixo()}."
            if not comando:
                return "O que devo fazer quando você abrir e fechar a mão?"
            t = _estado["thread"]
            ligou = "" if (t is not None and t.is_alive()) else " " + ligar(player)
            if acao == "armar":
                _estado["armado"] = (comando, time.time() + 60)
                return f"Pronto, senhor: abra e feche a mão na frente da câmera e eu faço '{comando}'.{ligou}"
            from plugins._comum import salvar_cfg
            salvar_cfg("gestos", {"comando_abrir_fechar": comando})
            return f"Feito: daqui para frente, abrir e fechar a mão faz '{comando}'.{ligou}"
        t = _estado["thread"]
        ativo = t is not None and t.is_alive()
        txt = "Gestos ligados." if ativo else "Gestos desligados."
        if _estado["ultimo"]:
            txt += f" Último: {_estado['ultimo']}."
        if _estado["erro"]:
            txt += f" Problema: {_estado['erro']}."
        return txt
    except Exception as e:
        return f"Os gestos falharam: {e}"


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    if cfg("gestos", PLUGIN_SETTINGS).get("ligar_ao_abrir"):
        print(f"[Gestos] {ligar(player)}")
