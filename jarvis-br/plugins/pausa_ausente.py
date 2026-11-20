"""
Pausa quando você sai (fork PT-BR 1.9).

    "Jarvis, liga a pausa automática"     "Jarvis, desliga a pausa automática"

Com a webcam: se ninguém aparece por 10 segundos e há som tocando, o JARVIS
pausa o vídeo ou a música (tecla de mídia). Quando você volta para a frente do
PC, ele continua de onde parou. Se você mesmo der play enquanto está longe
(pelo celular, por exemplo), ele não mexe mais até você voltar.

Usa o detector de rostos que já vem no opencv (sem baixar nada) e a mesma
câmera da Central e dos gestos. A luz da webcam fica acesa enquanto está ligado.
"""

from __future__ import annotations

import threading
import time

from plugins._comum import cfg, registrar

PLUGIN = {
    "name": "pausa_ausente",
    "brief": "Pauses video/music when the user leaves the webcam's view and resumes when they come back.",
    "description": ("Auto-pause when away: with the webcam, if nobody is seen for N seconds while sound is playing, it "
                    "pauses media and resumes on return. action='ligar' | 'desligar' | 'status'."),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status"}},
                   "required": []},
}

PLUGIN_SETTINGS = {
    "namespace": "pausa_ausente",
    "title": "Pausa quando você sai",
    "fields": [
        {"key": "segundos", "label": "Segundos sem ninguém para pausar", "type": "text", "default": "10"},
        {"key": "ligar_ao_abrir", "label": "Ligar quando o JARVIS abrir", "type": "toggle", "default": False},
    ],
}


class Presenca:
    """Decide pausar/retomar (pura, nos testes)."""

    VOLTOU_QUADROS = 2

    def __init__(self, ausente_s: float = 10.0):
        self.ausente_s = ausente_s
        self.visto = time.monotonic()
        self.seguidos = 0
        self.pausei = False
        self.pausado_em = 0.0

    def atualizar(self, tem_rosto: bool, tocando: bool | None, t: float) -> str:
        if tem_rosto:
            self.seguidos += 1
            self.visto = t
            if self.pausei and self.seguidos >= self.VOLTOU_QUADROS:
                self.pausei = False
                return "retomar"
            return ""
        self.seguidos = 0
        if self.pausei:
            if tocando and t - self.pausado_em > 4:            # alguém deu play de longe: não brigar
                self.pausei = False
            return ""
        if t - self.visto >= self.ausente_s and tocando:
            self.pausei, self.pausado_em = True, t
            return "pausar"
        return ""


_estado = {"thread": None, "ultimo": "", "erro": ""}
_parar = threading.Event()
_iniciou = threading.Event()


def _detector():
    import cv2
    base = cv2.data.haarcascades
    return cv2.CascadeClassifier(base + "haarcascade_frontalface_default.xml"), \
        cv2.CascadeClassifier(base + "haarcascade_profileface.xml")


def tem_rosto(img, detectores) -> bool:
    import cv2
    h, w = img.shape[:2]
    if w > 320:
        img = cv2.resize(img, (320, int(h * 320 / w)))
    cinza = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    for d in detectores:
        if len(d.detectMultiScale(cinza, scaleFactor=1.15, minNeighbors=4, minSize=(36, 36))):
            return True
    return len(detectores[1].detectMultiScale(cv2.flip(cinza, 1), 1.15, 4, minSize=(36, 36))) > 0


def _laco(player) -> None:
    from plugins import _midia
    from plugins._camera_remota import quadro
    try:
        detectores = _detector()
    except Exception as e:
        _estado["erro"] = f"opencv indisponível: {e}"
        return
    try:
        seg = float(str(cfg("pausa_ausente", PLUGIN_SETTINGS).get("segundos") or 10).replace(",", "."))
    except ValueError:
        seg = 10.0
    p = Presenca(max(3.0, seg))
    while not _parar.is_set():
        img, erro = quadro(0, espera_s=3)
        if img is None:
            _estado["erro"] = erro
            time.sleep(3)
            continue
        rosto = tem_rosto(img, detectores)
        if rosto:                                              # 2.4: o estado do mundo sabe se tem alguém
            _estado["visto"] = time.time()
        tocando = None if rosto and not p.pausei else _midia.tocando(amostras=4)
        r = p.atualizar(rosto, tocando, time.monotonic())
        if r:
            _midia.tecla("play_pause")
            _estado["ultimo"] = f"{time.strftime('%H:%M:%S')} {'pausei (você saiu)' if r == 'pausar' else 'continuei'}"
            registrar(player, f"Pausa automática: {_estado['ultimo']}.")
        time.sleep(0.8)


def presente_agora() -> bool | None:
    """2.4: True/False se a câmera está vigiando; None se não está."""
    t = _estado.get("thread")
    if t is None or not t.is_alive():
        return None
    return time.time() - float(_estado.get("visto") or 0) < 30


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    t = _estado["thread"]
    ativo = t is not None and t.is_alive()
    if acao == "ligar":
        if ativo:
            return "A pausa automática já está ligada."
        try:
            import cv2  # noqa: F401
        except ImportError:
            return "Preciso do opencv: python -m pip install opencv-python"
        _parar.clear()
        _estado["thread"] = threading.Thread(target=_laco, args=(player,), daemon=True, name="pausa_ausente")
        _estado["thread"].start()
        return "Pausa automática ligada: se você sair da frente da câmera com algo tocando, eu pauso e continuo na volta."
    if acao == "desligar":
        _parar.set()
        return "Pausa automática desligada."
    txt = "Pausa automática ligada." if ativo else "Pausa automática desligada."
    if _estado["ultimo"]:
        txt += f" Última: {_estado['ultimo']}."
    if _estado["erro"]:
        txt += f" Problema: {_estado['erro']}."
    return txt


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    if cfg("pausa_ausente", PLUGIN_SETTINGS).get("ligar_ao_abrir"):
        print(f"[PausaAusente] {run({'action': 'ligar'}, player)}")
