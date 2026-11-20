"""
Estado do mundo e central de avisos (fork PT-BR 2.4).

    "Jarvis, o que eu tô fazendo agora?"      (o que ele percebe: jogo, código, edição, chamada, live…)
    "Jarvis, o que eu perdi?"                 (os avisos que ele guardou enquanto você jogava)
    "Jarvis, tem aviso guardado?"

Veja core/estado_mundo.py e core/central_avisos.py.
"""

from __future__ import annotations

from core import central_avisos, estado_mundo

PLUGIN = {
    "name": "estado_mundo",
    "brief": "What is happening right now (gaming, coding, editing, call, live, away, music) and the held-back alerts.",
    "description": (
        "World state and alert center. action='agora' says the time and what the user is doing now (gaming, coding, "
        "editing, on a call, live streaming, watching, away) and whether music is playing — use it to decide how "
        "short to answer; 'perdi' tells the alerts that were held back while he was busy (then clears them); "
        "'pendentes' lists them without clearing. Urgent alerts are always spoken at once; normal ones wait for a "
        "pause; minor ones become a summary."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "agora | perdi | pendentes"}},
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "agora").lower()
    try:
        if acao in ("perdi", "o_que_perdi", "resumo"):
            return central_avisos.o_que_perdi()
        if acao == "pendentes":
            p = central_avisos.pendentes()
            n = len(p["fila"]) + len(p["resumo"])
            if not n:
                return "Nenhum aviso guardado."
            return f"{n} aviso(s) guardado(s): " + "; ".join(i["texto"][:100] for i in (p["fila"] + p["resumo"])[:6])
        return estado_mundo.descrever(estado_mundo.agora(forcar=True))
    except Exception as e:
        return f"Não consegui ler o estado agora: {e}"
