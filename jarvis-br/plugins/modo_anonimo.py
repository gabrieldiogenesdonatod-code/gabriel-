"""
Modo anônimo (3.2): converse sem deixar rastro no PC e sem o Gemini receber as suas memórias.

    "Jarvis, modo anônimo"     "Jarvis, sai do modo anônimo"     "Jarvis, estou no modo anônimo?"

Detalhes do que é e do que não é gravado: core/anonimo.py.
"""

from __future__ import annotations

from core import anonimo
from plugins._lote2 import P, rodar

PLUGIN = P("modo_anonimo", "Incognito mode: restart the session without the user's memories and record nothing of the "
                           "conversation (no memory, usage diary or session summary).",
           "ligar | desligar | status",
           "Incognito/anonymous mode. ligar: restarts the session without memories; nothing of the conversation is saved. "
           "desligar: back to normal (restarts the session with memories). status.", "")


def _reconectar(motivo: str) -> None:
    try:
        from core import registro_ferramentas
        registro_ferramentas.reconectar(motivo, manter_conversa=False)
    except Exception:
        pass
    import sys
    cel = sys.modules.get("jarvis_celular")               # no celular: a conversa em memória recomeça
    try:
        if cel is not None and cel.MOTOR is not None:
            cel.MOTOR.historico.clear()
    except Exception:
        pass


def _ligar(p, pl):
    if anonimo.ativo():
        return "O modo anônimo já está ligado."
    anonimo.definir(True)
    _reconectar("modo anônimo")
    return ("Modo anônimo ligado: recomecei a conversa sem as suas memórias e nada do que você falar fica gravado no PC. "
            "Listas e lembretes que você pedir de propósito continuam valendo. Para sair: 'sai do modo anônimo'.")


def _desligar(p, pl):
    if not anonimo.ativo():
        return "O modo anônimo já está desligado."
    anonimo.definir(False)
    _reconectar("fim do modo anônimo")
    return "Modo anônimo desligado: as suas memórias voltaram e a conversa volta a ser registrada normalmente."


def _status(p, pl):
    return ("Modo anônimo LIGADO: nada da conversa é gravado e o Gemini não recebe as suas memórias."
            if anonimo.ativo() else "Modo anônimo desligado.")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"ligar": _ligar, "desligar": _desligar, "status": _status}, player)
