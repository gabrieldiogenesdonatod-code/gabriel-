"""
Microfone reservado (fork PT-BR 2.4).

Quando um plugin precisa gravar a SUA voz (take do estúdio de rap, recado em
áudio da cápsula do tempo), ele reserva o microfone por alguns segundos: o
JARVIS continua com o microfone aberto, mas não manda esse áudio para o
modelo — assim ele não "responde" o rap nem o recado. A reserva sempre tem
prazo; se o plugin travar, o microfone volta sozinho.

    from core import microfone
    with microfone.reservado_por("estúdio", 60):
        audio = microfone.gravar(30)
"""

from __future__ import annotations

import contextlib
import threading
import time

TAXA = 44100
_lock = threading.Lock()
_estado = {"ate": 0.0, "motivo": ""}


def reservar(motivo: str, segundos: float) -> None:
    with _lock:
        _estado.update(ate=time.time() + max(1.0, min(900.0, float(segundos))), motivo=motivo)


def liberar() -> None:
    with _lock:
        _estado.update(ate=0.0, motivo="")


def reservado() -> bool:
    with _lock:
        return time.time() < _estado["ate"]


def motivo() -> str:
    with _lock:
        return _estado["motivo"] if time.time() < _estado["ate"] else ""


@contextlib.contextmanager
def reservado_por(motivo_: str, segundos: float):
    reservar(motivo_, segundos)
    try:
        yield
    finally:
        liberar()


def esperar_jarvis_calar(maximo_s: float = 12.0, folga_s: float = 0.8) -> None:
    """Espera o JARVIS terminar a frase (para a voz dele não entrar na gravação)."""
    fim = time.time() + maximo_s
    try:
        from core import registro_ferramentas
        app = registro_ferramentas.app()
    except Exception:
        app = None
    time.sleep(1.0)
    while time.time() < fim and app is not None and getattr(app, "_is_speaking", False):
        time.sleep(0.2)
    time.sleep(folga_s)


def gravar(segundos: float, taxa: int = TAXA, parar_no_silencio: bool = False, silencio_s: float = 3.0,
           limite: float = 0.012):
    """Grava do microfone padrão (mono float32). Com parar_no_silencio, para depois de você falar e calar."""
    import numpy as np
    import sounddevice as sd
    if not parar_no_silencio:
        a = sd.rec(int(segundos * taxa), samplerate=taxa, channels=1, dtype="float32")
        sd.wait()
        return a[:, 0]
    blocos: list = []
    estado = {"falou": False, "quieto_desde": time.time(), "fim": False}

    def cb(indata, frames, _t, _s):
        blocos.append(indata[:, 0].copy())
        nivel = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        if nivel > limite:
            estado["falou"], estado["quieto_desde"] = True, time.time()
        elif estado["falou"] and time.time() - estado["quieto_desde"] > silencio_s:
            estado["fim"] = True
    inicio = time.time()
    with sd.InputStream(samplerate=taxa, channels=1, dtype="float32", callback=cb):
        while not estado["fim"] and time.time() - inicio < segundos:
            time.sleep(0.1)
    return np.concatenate(blocos) if blocos else np.zeros(0, "float32")
