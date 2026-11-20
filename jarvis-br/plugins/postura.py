"""
Detector de cansaço e postura (fork PT-BR 1.5).

Pela webcam (de tempos em tempos, poucos segundos), o JARVIS compara você
com a sua postura "boa", calibrada uma vez:

    CURVADO    o rosto desceu e/ou chegou bem mais perto da tela;
    TORTO      a cabeça está inclinada há vários minutos;
    BOCEJOS    a boca abre e o rosto "estica" por alguns segundos (contados
               numa amostra de 8 s a cada 5 min);
    SEM PAUSA  pela linha do tempo: 90 min seguidos no PC sem sair.

Avisa com calma ("Senhor, endireite as costas") e, quando é cansaço, sugere
uma pausa (ou um Pomodoro de pausa). Nada é gravado: só números.

    "Jarvis, liga o detector de postura"   → ele pede para calibrar
    "Jarvis, calibra a postura"            (sente-se direito e olhe para a tela)
    "Jarvis, como está minha postura?"     "Jarvis, desliga o detector de postura"

Usa a mesma câmera e o mesmo detector de rosto do reconhecimento facial
(OpenCV, YuNet). Começa desligado.
"""

from __future__ import annotations

import math
import statistics
import threading
import time

from plugins._comum import MEMORIA, cfg, falar, gravar_json, ler_json, salvar_cfg

PLUGIN = {
    "name": "postura",
    "brief": "Webcam posture and tiredness coach: slouching, head tilt, yawns, no breaks; suggests pauses.",
    "description": (
        "Posture and tiredness detector using the webcam a few seconds at a time (slouching, leaning in, head tilt, "
        "yawns) plus time without breaks from the timeline; gently warns and suggests pauses. action='ligar', "
        "'desligar', 'calibrar' (user sits upright), 'status' ('how is my posture?')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ligar | desligar | calibrar | status"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "postura",
    "title": "Postura e cansaço",
    "fields": [
        {"key": "ligado", "label": "Vigiar postura e cansaço pela câmera", "type": "toggle", "default": False},
        {"key": "intervalo", "label": "Olhar a cada (segundos)", "type": "text", "default": "60"},
        {"key": "pausa_min", "label": "Sugerir pausa depois de (minutos seguidos)", "type": "text", "default": "90"},
    ],
}

_ARQ = MEMORIA / "postura.json"
_estado = {"ruins": 0, "bocejos": [], "ultimo_aviso": {}, "ultimo": None}
_iniciado = threading.Event()


# ── medidas (puras) ────────────────────────────────────────────────────────────
def medidas(face, largura: int, altura: int) -> dict:
    """Do vetor do YuNet [x, y, w, h, olhoD(x,y), olhoE(x,y), nariz, bocaD, bocaE, nota]."""
    x, y, w, h = (float(v) for v in face[:4])
    odx, ody, oex, oey = (float(v) for v in face[4:8])
    bdx, bdy, bex, bey = (float(v) for v in face[10:14])
    return {"centro_y": (y + h / 2) / altura, "tamanho": h / altura,
            "inclinacao": math.degrees(math.atan2(oey - ody, oex - odx)),
            "proporcao": h / max(w, 1.0), "boca": math.hypot(bex - bdx, bey - bdy) / max(w, 1.0)}


def avaliar(m: dict, base: dict) -> list[str]:
    """Problemas desta olhada em relação à postura calibrada (pura)."""
    prob = []
    if m["centro_y"] - base["centro_y"] > 0.08 or m["tamanho"] > base["tamanho"] * 1.28:
        prob.append("curvado")
    if abs(m["inclinacao"] - base["inclinacao"]) > 12:
        prob.append("torto")
    return prob


def eh_bocejo(serie: list[dict], base: dict) -> bool:
    """Numa amostra de quadros: rosto 'esticado' e boca estreita por ≥ 4 quadros seguidos."""
    seguidos = 0
    for m in serie:
        if m["proporcao"] > base["proporcao"] * 1.12 and m["boca"] < base["boca"] * 0.9:
            seguidos += 1
            if seguidos >= 4:
                return True
        else:
            seguidos = 0
    return False


# ── câmera ─────────────────────────────────────────────────────────────────────
def olhar(quadros: int = 3, intervalo: float = 0.0) -> list[dict]:
    from plugins import reconhecimento_facial as rf
    det, _rec = rf._ensure_models(None)
    saida = []
    with rf._lock:
        cap = rf._open_camera()
        if cap is None:
            return []
        try:
            for _ in range(quadros):
                ok, frame = cap.read()
                if ok and frame is not None:
                    rostos = rf._faces(det, frame)
                    if rostos:
                        maior = max(rostos, key=lambda f: f[2] * f[3])
                        saida.append(medidas(maior, frame.shape[1], frame.shape[0]))
                if intervalo:
                    time.sleep(intervalo)
        finally:
            cap.release()
    return saida


def media(ms: list[dict]) -> dict:
    return {k: statistics.median(m[k] for m in ms) for k in ms[0]} if ms else {}


def calibrar() -> str:
    ms = olhar(6, 0.2)
    if len(ms) < 3:
        return "Não consegui ver o seu rosto direito. Olhe para a tela e tente de novo."
    gravar_json(_ARQ, {"base": media(ms), "calibrado": time.time()})
    return "Calibrado: essa é a sua postura boa. Vou avisar quando você sair muito dela."


def _avisar(player, chave: str, intervalo_min: float, instrucao: str) -> None:
    if time.time() - _estado["ultimo_aviso"].get(chave, 0) < intervalo_min * 60:
        return
    _estado["ultimo_aviso"][chave] = time.time()
    falar(player, f"[POSTURA] {instrucao} Seja gentil, UMA frase curta. Não chame nenhuma ferramenta.")


def minutos_sem_pausa(focos: list[dict], agora: float, pausa_s: float = 300) -> float:
    """Minutos desde a última pausa de ≥ 5 min: ausência registrada OU buraco sem registro
    (PC desligado/suspenso). Pura."""
    inicio, fim_ant = None, None
    for f in sorted(focos, key=lambda x: x["inicio"]):
        if f.get("atividade") == "ausente":
            if f["fim"] - f["inicio"] >= pausa_s:
                inicio, fim_ant = None, f["fim"]
            continue
        if inicio is None or (fim_ant is not None and f["inicio"] - fim_ant >= pausa_s):
            inicio = f["inicio"]
        fim_ant = max(fim_ant or 0.0, f["fim"])
    return (agora - inicio) / 60 if inicio is not None else 0.0


def _minutos_sem_pausa() -> float:
    try:
        from plugins import _monitor_db
        return minutos_sem_pausa(_monitor_db.focos(time.time() - 6 * 3600), time.time())
    except Exception:
        return 0.0


def _laco(player) -> None:
    time.sleep(120)
    ultima_amostra = 0.0
    while True:
        c = cfg("postura", PLUGIN_SETTINGS)
        try:
            intervalo = max(30.0, float(str(c.get("intervalo") or 60)))
        except ValueError:
            intervalo = 60.0
        try:
            base = (ler_json(_ARQ, {}) or {}).get("base")
            from plugins.linha_do_tempo import ocioso_segundos
            if str(c.get("ligado", False)).lower() in ("true", "1", "sim") and base and ocioso_segundos() < 120:
                amostra = time.time() - ultima_amostra >= 300
                ms = olhar(32, 0.25) if amostra else olhar(3)
                if amostra:
                    ultima_amostra = time.time()
                    if eh_bocejo(ms, base):
                        _estado["bocejos"].append(time.time())
                if ms:
                    m = media(ms)
                    prob = avaliar(m, base)
                    _estado["ultimo"] = (time.time(), prob)
                    _estado["ruins"] = _estado["ruins"] + 1 if prob else 0
                    if _estado["ruins"] >= 3:
                        _avisar(player, "postura", 20, "O usuário está há alguns minutos " +
                                ("curvado ou perto demais da tela" if "curvado" in prob else "com a cabeça inclinada")
                                + ". Lembre-o de ajeitar a postura.")
                _estado["bocejos"] = [t for t in _estado["bocejos"] if time.time() - t < 3600]
                try:
                    limite = float(str(c.get("pausa_min") or 90))
                except ValueError:
                    limite = 90.0
                if len(_estado["bocejos"]) >= 3:
                    _avisar(player, "cansaco", 45, "O usuário bocejou várias vezes na última hora. Sugira uma pausa "
                                                   "curta (água, alongar), e ofereça um Pomodoro de pausa.")
                elif _minutos_sem_pausa() >= limite:
                    _avisar(player, "pausa", 45, f"O usuário está há mais de {int(limite)} minutos seguidos no PC. "
                                                 "Sugira uma pausa de 5 minutos.")
        except Exception as e:
            print(f"[Postura] {e}")
        time.sleep(intervalo)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="postura").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    try:
        if acao == "calibrar":
            return calibrar()
        if acao == "ligar":
            salvar_cfg("postura", {"ligado": True})
            if not (ler_json(_ARQ, {}) or {}).get("base"):
                return "Ligado. Agora sente-se com a postura boa, olhe para a tela e diga 'calibra a postura'."
            return "Detector de postura ligado. Vou olhar de vez em quando, sem gravar nada."
        if acao == "desligar":
            salvar_cfg("postura", {"ligado": False})
            return "Detector de postura desligado."
        base = (ler_json(_ARQ, {}) or {}).get("base")
        if not base:
            return "Ainda não calibrei. Sente-se direito e diga 'calibra a postura'."
        ms = olhar(3)
        if not ms:
            return "Não consegui te ver na câmera agora."
        prob = avaliar(media(ms), base)
        sem_pausa = _minutos_sem_pausa()
        return ((f"Você está {' e '.join(prob)}." if prob else "Sua postura está boa.")
                + (f" Bocejos na última hora: {len(_estado['bocejos'])}." if _estado["bocejos"] else "")
                + (f" Você está há {sem_pausa:.0f} min sem pausa." if sem_pausa >= 30 else ""))
    except Exception as e:
        return f"O detector de postura falhou: {e}"
