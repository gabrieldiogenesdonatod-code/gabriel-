"""
HUD 3.9 no JARVIS (fork PT-BR 3.9.1) — o painel J.A.R.V.I.S animado e clicável com os números reais do PC.

    "Jarvis, abre o HUD"                    "Jarvis, abre o HUD 3.9 em janela" (sem tela cheia)
    "Jarvis, abre o painel do Homem de Ferro" / "abre a tela futurista"
    "Jarvis, fecha o HUD"                   "Jarvis, qual o endereço do HUD?"

Também pelo botão  🛰  HUD 3.9  na gaveta de controles. Detalhes: hud39/__init__.py.
"""
from __future__ import annotations

from plugins._lote2 import P, norm, rodar

PLUGIN = P("hud39", "HUD 3.9: animated, clickable J.A.R.V.I.S dashboard with live PC data (system, network, GPU, processes).",
           "abrir | fechar | endereco",
           "Opens the animated J.A.R.V.I.S HUD 3.9 window (Iron Man style screen) with real-time CPU, RAM, disk, network, "
           "GPU, processes and 'about the system'; its buttons open folders, control music, and send commands back to JARVIS. "
           "Use for 'abre o HUD', 'abre o HUD 3.9', 'tela futurista', 'painel do homem de ferro'. modo: 'janela' for a "
           "normal window instead of full screen. Do NOT use for the detailed task-manager style monitor (that is the "
           "📊 MONITOR panel) or for switching the face/core centrepiece of the main window.",
           "modo")


def _abrir(p, player):
    import hud39
    tela_cheia = "janela" not in norm(p.get("modo"))
    if player is not None:
        url = hud39.abrir_do_jarvis(player, tela_cheia=tela_cheia)
    else:
        url = hud39.abrir(tela_cheia=tela_cheia)
    return f"HUD 3.9 aberto{' em tela cheia' if tela_cheia else ''}. Endereço: {url}"


def _fechar(p, player):
    import hud39
    if not hud39.endereco():
        return "O HUD 3.9 não está aberto."
    hud39.parar()
    return "HUD 3.9 desligado. Pode fechar a janela dele."


def _endereco(p, player):
    import hud39
    return f"O HUD 3.9 está em {hud39.endereco()}" if hud39.endereco() else "O HUD 3.9 não está aberto."


def run(parameters: dict, player=None, session_memory=None) -> str:
    return rodar(parameters, {"abrir": _abrir, "fechar": _fechar, "endereco": _endereco}, player, "HUD 3.9")
