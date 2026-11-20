"""
JARVIS vendo a sua tela em tempo real (fork PT-BR 2.2).

    "Jarvis, olha minha tela"               (liga por 10 minutos)
    "Jarvis, olha minha tela por 30 minutos"
    "Jarvis, o que você acha desse código?" / "por que esse erro?" / "qual dessas camisetas fica melhor?"
    "Jarvis, para de olhar a tela"

Enquanto está ligado, o JARVIS recebe a tela uns 1 quadro por segundo pelo canal
de vídeo do Gemini Live (o mesmo que a câmera usa). Ele não fala sozinho: só
olha, e responde quando você pergunta, já sabendo o que está na tela, sem
precisar de print. Quadros iguais não são reenviados; desliga sozinho no fim
do tempo. Cuidado com senhas e conversas na tela enquanto estiver ligado.
"""

from __future__ import annotations

import time

from plugins._comum import registrar

PLUGIN = {
    "name": "tela_ao_vivo",
    "brief": "Live screen sharing with JARVIS: streams the screen (~1 fps) into the session so it can follow along "
             "and answer about what is on screen.",
    "description": (
        "Live screen view. action='ligar' (optional minutos, default 10, max 60) streams the user's screen into the "
        "conversation about once per second; after that, answer questions about the screen from what you see, without "
        "calling screen capture tools. Do not comment unprompted. action='desligar' stops; 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status"},
                       "minutos": {"type": "NUMBER"}},
        "required": [],
    },
}


def _app():
    try:
        from core import registro_ferramentas
        return registro_ferramentas.app()
    except Exception:
        return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "ligar").lower()
    app = _app()
    if app is None or not hasattr(app, "tela_ao_vivo"):
        return "A tela ao vivo só funciona com o JARVIS aberto e conectado ao Gemini Live."
    try:
        estado = getattr(app, "_tela_viva", None) or {}
        if acao == "desligar":
            app.tela_ao_vivo(False)
            registrar(player, "👁 Tela ao vivo desligada.")
            return "Parei de olhar a tela."
        if acao == "status":
            falta = estado.get("ate", 0) - time.time()
            return (f"Estou vendo a sua tela; desligo em {falta / 60:.0f} min ({estado.get('enviados', 0)} quadros)."
                    if falta > 0 else "Não estou olhando a tela agora.")
        minutos = max(1.0, min(60.0, float(p.get("minutos") or 10)))
        erro = app.tela_ao_vivo(True, minutos)
        if erro:
            return f"Não deu para ligar a tela ao vivo: {erro}."
        registrar(player, f"👁 Vendo a tela em tempo real por {minutos:g} min (diga 'para de olhar a tela').")
        return (f"[TELA AO VIVO] Ligado por {minutos:g} minutos: a partir de agora você recebe a tela do usuário em tempo "
                "real. Diga em UMA frase curta que está vendo a tela e espere ele perguntar; não descreva nada sem ser "
                "perguntado.")
    except Exception as e:
        return f"A tela ao vivo falhou: {e}"
