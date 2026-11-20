"""
Uma trava só para abrir, ligar, parar e fechar a placa de som (fork PT-BR 2.8.1).

Por que o JARVIS podia fechar sozinho por causa do som
    O PortAudio — a biblioteca por trás do sounddevice — não aguenta duas
    threads mexendo na placa AO MESMO TEMPO (abrir, iniciar, parar, fechar).
    No Windows isso não dá erro do Python: o programa inteiro cai na hora,
    sem mensagem (access violation no portaudio). No JARVIS isso acontecia:
      • ao reconectar com o Gemini, a saída de som antiga fecha numa thread
        (2.7.4) enquanto a sessão nova já abre o microfone e a saída;
      • os plugins tocam efeitos, vozes e alarmes (sd.play, sd.rec) de outras
        threads, ao mesmo tempo que a voz do JARVIS.

O que este módulo faz
    `instalar()` (o main.py chama logo depois de importar o sounddevice)
    embrulha o __init__ (abrir), start, stop, abort e close de TODOS os streams
    do sounddevice — inclusive os criados por sd.play()/sd.rec() nos plugins —
    com a mesma trava. Ler e escrever o áudio continua livre: só o ciclo de
    vida da placa espera a vez.
"""

from __future__ import annotations

import functools
import threading

TRAVA = threading.RLock()
METODOS = ("__init__", "start", "stop", "abort", "close")
_estado = {"instalado": False}


def _embrulhar(fn):
    @functools.wraps(fn)
    def com_trava(*args, **kwargs):
        with TRAVA:
            return fn(*args, **kwargs)
    com_trava._placa_som = True           # não embrulha duas vezes
    return com_trava


def instalar(sd=None) -> bool:
    """Põe a trava nos streams do sounddevice. True se instalou (ou já estava)."""
    if _estado["instalado"]:
        return True
    try:
        if sd is None:
            import sounddevice as sd      # noqa: PLW0127 — sem PortAudio isso já falha aqui
        base = sd._StreamBase
    except Exception as e:
        print(f"[PlacaSom] sem trava (sounddevice indisponível): {e}")
        return False
    for nome in METODOS:
        fn = getattr(base, nome, None)
        if callable(fn) and not getattr(fn, "_placa_som", False):
            setattr(base, nome, _embrulhar(fn))
    _marcar_som_de_plugin(sd)
    _estado["instalado"] = True
    return True


def _marcar_som_de_plugin(sd) -> None:
    """3.2 (anti-eco): sd.play() dos plugins avisa quanto tempo vai tocar — o microfone não manda
    esse som para o modelo (senão ele "ouve" o alarme ou a voz que o plugin tocou)."""
    tocar = getattr(sd, "play", None)
    if not callable(tocar) or getattr(tocar, "_anti_eco", False):
        return

    @functools.wraps(tocar)
    def play(data, samplerate=None, *args, **kwargs):
        try:
            from core import anti_eco
            taxa = samplerate or getattr(sd.default, "samplerate", None) or 44100
            anti_eco.get().marcar_audio_plugin(len(data) / float(taxa))
        except Exception:
            pass
        return tocar(data, samplerate, *args, **kwargs)
    play._anti_eco = True
    sd.play = play


def instalada() -> bool:
    return bool(_estado["instalado"])
