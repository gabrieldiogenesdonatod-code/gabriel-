"""
Modo Sentinela (fork PT-BR 1.5).

Quando você sai, a webcam vigia o PC. Se alguém mexer — um rosto que não é
o seu, ou movimento na frente da tela — o JARVIS tira uma FOTO, manda para o
seu celular (push do ntfy com a imagem), registra o evento e, se você quiser,
fala com a pessoa ("Este computador está sendo monitorado") e te LIGA.

QUANDO LIGA
    • "Jarvis, ativa a sentinela" / "desativa a sentinela";
    • sozinha (configurável): ao bloquear o Windows, quando a sua chave
      (celular/pulseira) sai de perto ou quando o geofence diz que você saiu.
QUANDO DESLIGA
    • você volta: desbloqueia o Windows, a câmera te reconhece, a chave volta;
    • "desativa a sentinela".
No fim ela conta quantas vezes disparou (e o relatório de "quando voltar"
também mostra).

Fotos ficam em memory/sentinela/ (apagadas depois de 30 dias). Precisa do
OpenCV (o mesmo do reconhecimento facial). Sem rosto cadastrado, QUALQUER
rosto dispara.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from plugins._comum import MEMORIA, cfg, falar, registrar

PLUGIN = {
    "name": "sentinela",
    "brief": "Sentinel mode: webcam watches the PC while the owner is away; photo to phone on intrusion.",
    "description": (
        "Sentinel mode: while the owner is away the webcam watches; an unknown face or movement in front of "
        "the PC triggers a photo sent to the phone, an event log and optionally a warning voice and a phone "
        "call. action='ativar' | 'desativar' | 'status' | 'fotos' (list recent captures)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ativar | desativar | status | fotos"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "sentinela",
    "title": "Sentinela",
    "fields": [
        {"key": "auto", "label": "Ligar sozinha", "type": "choice",
         "choices": ["ao bloquear o Windows", "quando a chave/geofence disser que saí", "nunca"],
         "default": "quando a chave/geofence disser que saí"},
        {"key": "movimento", "label": "Disparar com movimento mesmo sem rosto", "type": "toggle", "default": True},
        {"key": "falar", "label": "Avisar a pessoa em voz alta", "type": "toggle", "default": True},
        {"key": "ligar", "label": "Me ligar quando disparar (plugin de ligação)", "type": "toggle", "default": False},
    ],
}

PASTA = MEMORIA / "sentinela"
_estado = {"ativa": False, "desde": 0.0, "disparos": 0, "ultima_foto": "", "motivo": "", "vigia_rosto": False}
_parar = threading.Event()
_iniciado = threading.Event()
ARMAR_S = 30            # tempo para você sair da frente da câmera antes de ela começar a vigiar


def _sim(v) -> bool:
    return str(v).strip().lower() not in ("false", "0", "nao", "não", "off")


# ── análise de quadros (pura com numpy) ────────────────────────────────────────
def movimento(anterior, atual, limiar: int = 25) -> float:
    """Fração de pixels que mudaram entre dois quadros em tons de cinza reduzidos."""
    import numpy as np
    if anterior is None or atual is None or anterior.shape != atual.shape:
        return 0.0
    dif = np.abs(atual.astype("int16") - anterior.astype("int16"))
    return float((dif > limiar).mean())


def _cinza_pequeno(frame):
    import cv2
    pequeno = cv2.resize(frame, (160, 120))
    return cv2.GaussianBlur(cv2.cvtColor(pequeno, cv2.COLOR_BGR2GRAY), (5, 5), 0)


# ── laço ───────────────────────────────────────────────────────────────────────
def _disparar(player, frame, motivo: str) -> None:
    import cv2
    PASTA.mkdir(parents=True, exist_ok=True)
    arq = PASTA / f"{datetime.now():%Y%m%d_%H%M%S}.jpg"
    cv2.imwrite(str(arq), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    _estado["disparos"] += 1
    _estado["ultima_foto"] = str(arq)
    c = cfg("sentinela", PLUGIN_SETTINGS)
    try:
        from plugins import _monitor_db
        _monitor_db.gravar_evento("seguranca", f"Sentinela: {motivo} (foto {arq.name})")
    except Exception:
        pass
    from plugins._notificar import notificar
    notificar(player, f"Sentinela: {motivo} às {datetime.now():%H:%M}. A foto está no seu celular e em memory/sentinela.",
              titulo="SENTINELA", falar_agora=False, foto=arq,
              prioridade="urgent" if _sim(c.get("ligar", False)) else "high")
    if _sim(c.get("falar", True)):
        falar(player, "[SENTINELA] Há alguém mexendo no computador enquanto o dono está fora. Diga, em voz firme e "
                      "educada, em UMA frase: este computador está sendo monitorado e o dono já foi avisado. "
                      "Não chame nenhuma ferramenta.")


def _laco(player) -> None:
    try:
        import cv2  # noqa: F401
        from plugins import reconhecimento_facial as rf
    except Exception as e:
        registrar(player, f"Sentinela: preciso do OpenCV ({e}).")
        _estado["ativa"] = False
        return
    try:
        det, rec = rf._ensure_models(player)
    except Exception:
        det = rec = None
    dono = rf._load_owner()
    limite = rf._threshold()
    cap = rf._open_camera()
    if cap is None:
        registrar(player, "Sentinela: não consegui abrir a câmera.")
        _estado["ativa"] = False
        return
    c = cfg("sentinela", PLUGIN_SETTINGS)
    anterior, seguidos, ultimo_disparo, pendente = None, 0, 0.0, None
    armada_em = time.time() + ARMAR_S
    try:
        while not _parar.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(1)
                continue
            agora = time.time()
            cinza = _cinza_pequeno(frame)
            mov = movimento(anterior, cinza)
            anterior = cinza
            if agora < armada_em:                             # você ainda está saindo
                time.sleep(0.5)
                continue
            motivo = ""
            rostos = rf._faces(det, frame) if det is not None and mov > 0.002 else []
            if rostos:
                if dono is not None and rec is not None:
                    notas = [rf._score(dono, rf._signature(rec, frame, f)) for f in rostos]
                    if max(notas) >= limite:                  # é você voltando: cancela qualquer alarme
                        seguidos, pendente = 0, None
                        try:                                  # e conta como verificação (desliga a sentinela)
                            from core import verificacao
                            verificacao.confiar("rosto")
                        except Exception:
                            pass
                        time.sleep(0.5)
                        continue
                    motivo = "um rosto desconhecido na frente do PC"
                else:
                    motivo = "alguém na frente do PC"
            elif _sim(c.get("movimento", True)) and mov > 0.04:
                seguidos += 1
                if seguidos >= 3 and pendente is None:        # ~1,5 s de movimento seguido:
                    pendente = (agora, frame.copy())          # espera 4 s para ver se é você
            else:
                seguidos = 0
            if not motivo and pendente is not None and agora - pendente[0] >= 4:
                motivo, frame = "movimento na frente do PC", pendente[1]
            if motivo and agora - ultimo_disparo > 120:
                ultimo_disparo, seguidos, pendente = agora, 0, None
                _disparar(player, frame, motivo)
            time.sleep(0.5)
    finally:
        cap.release()


def ativar(player, motivo: str = "pedido") -> str:
    if _estado["ativa"]:
        return "A sentinela já está ativa."
    try:
        from plugins import reconhecimento_facial as rf
        _estado["vigia_rosto"] = bool(rf._watch_thread and rf._watch_thread.is_alive())
        if _estado["vigia_rosto"]:
            rf.stop_watching()                                # a câmera fica com a sentinela
    except Exception:
        _estado["vigia_rosto"] = False
    _parar.clear()
    _estado.update(ativa=True, desde=time.time(), disparos=0, motivo=motivo)
    if motivo == "pedido":
        # você mandou vigiar = você vai sair: a sessão confiável acaba aqui, para ninguém
        # usar comandos sensíveis (nem desligar a sentinela) sem provar que é você.
        try:
            from core import verificacao
            verificacao.encerrar("sentinela ligada")
        except Exception:
            pass
    threading.Thread(target=_laco, args=(player,), daemon=True, name="sentinela").start()
    registrar(player, f"Sentinela ativa ({motivo}).")
    return (f"Sentinela armando: em {ARMAR_S} segundos começo a vigiar. Se alguém mexer no PC, eu tiro uma foto "
            "e mando para o seu celular. Quando eu reconhecer o seu rosto, ela desliga sozinha.")


def desativar(player, motivo: str = "pedido") -> str:
    if not _estado["ativa"]:
        return "A sentinela não estava ativa."
    _parar.set()
    _estado["ativa"] = False
    if _estado.get("vigia_rosto"):
        try:
            from plugins import reconhecimento_facial as rf
            time.sleep(1.5)
            rf.start_watching(player)
        except Exception:
            pass
    n = _estado["disparos"]
    registrar(player, f"Sentinela desligada ({motivo}): {n} disparo(s).")
    return f"Sentinela desligada. {'Ela disparou ' + str(n) + ' vez(es); as fotos estão em memory/sentinela.' if n else 'Nada aconteceu enquanto você esteve fora.'}"


def _ao_evento(player):
    def ouvir(evento: str, detalhe: str) -> None:
        c = cfg("sentinela", PLUGIN_SETTINGS)
        auto = str(c.get("auto") or "")
        if evento == "bloqueou" and auto.startswith("ao bloquear"):
            ativar(player, "Windows bloqueado")
        elif evento in ("chave_saiu", "geofence_saiu") and auto != "nunca":
            ativar(player, "você saiu")
        elif evento in ("desbloqueou", "chave_voltou", "geofence_chegou") and _estado["ativa"]:
            threading.Thread(target=desativar, args=(player, "você voltou"), daemon=True).start()
        elif evento == "confiou" and detalhe == "rosto" and _estado["ativa"]:
            threading.Thread(target=desativar, args=(player, "reconheci você"), daemon=True).start()
    return ouvir


def _limpar_antigas(dias: int = 30) -> None:
    if PASTA.exists():
        limite = time.time() - dias * 86400
        for f in PASTA.glob("*.jpg"):
            if f.stat().st_mtime < limite:
                f.unlink(missing_ok=True)


def on_session_start(player) -> None:
    if _iniciado.is_set():
        return
    _iniciado.set()
    try:
        from core import verificacao
        verificacao.ao_mudar(_ao_evento(player))
        verificacao.iniciar_vigia()
    except Exception as e:
        print(f"[Sentinela] {e}")
    _limpar_antigas()


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    try:
        if acao == "ativar":
            return ativar(player)
        if acao == "desativar":
            return desativar(player)
        if acao == "fotos":
            fotos = sorted(PASTA.glob("*.jpg"))[-10:] if PASTA.exists() else []
            if not fotos:
                return "Nenhuma foto da sentinela."
            from plugins._comum import abrir_no_sistema
            abrir_no_sistema(str(fotos[-1]))
            return f"{len(fotos)} foto(s) recentes; abri a última ({fotos[-1].stem})."
        if _estado["ativa"]:
            return f"Sentinela ativa desde as {datetime.fromtimestamp(_estado['desde']):%H:%M}, {_estado['disparos']} disparo(s)."
        return "Sentinela desligada."
    except Exception as e:
        return f"A sentinela falhou: {e}"
