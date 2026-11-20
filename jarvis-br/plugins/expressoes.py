"""
Expressões do rosto (fork PT-BR 2.14).

    "Jarvis, fica feliz"            "Jarvis, faz cara de surpresa"
    "Jarvis, fica triste por 10 segundos"
    "Sexta, faz cara de desconfiada"
    "Jarvis, quais caras você sabe fazer?"
    "Jarvis, para de mudar de cara sozinho" / "pode mudar de cara sozinho"

O rosto do HUD e o rosto flutuante mostram a emoção (o da SEXTA também, quando
ela é a persona ativa). Sem pedido nenhum, o rosto já muda sozinho conforme o
que ele fala; aqui é para pedir uma cara de propósito ou desligar isso.

Emoções: feliz, animado, triste, surpresa, sério, bravo, desconfiado,
pensativo, envergonhado e neutro. A lógica fica em core/emocoes.py.
"""

from __future__ import annotations

from plugins._comum import cfg, salvar_cfg

PLUGIN = {
    "name": "expressoes",
    "brief": "Set the face's emotion (happy, sad, surprised, serious, angry, suspicious, thoughtful, shy…).",
    "description": (
        "Facial expression of JARVIS's (or FRIDAY's) holographic face. action='mostrar' with emocao = feliz | animado | "
        "triste | surpresa | serio | raiva | desconfiado | pensativo | envergonhado | neutro and optional segundos, "
        "for 'fica feliz', 'faz cara de surpresa', 'fica triste'. You MAY call it yourself to react with emotion when "
        "something is really good, sad or surprising (the face also reacts to your words automatically). "
        "action='listar' lists them. action='automatico' with valor ligar/desligar turns the automatic reaction to "
        "speech on or off."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "mostrar | listar | automatico"},
            "emocao": {"type": "STRING"}, "segundos": {"type": "NUMBER"}, "valor": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "expressoes",
    "title": "Expressões do rosto",
    "fields": [
        {"key": "automatico", "label": "O rosto muda de expressão sozinho conforme o que ele fala", "type": "toggle",
         "default": True},
    ],
}


def _aplicar_config() -> None:
    from core import emocoes
    emocoes.AUTOMATICO["ligado"] = bool(cfg("expressoes", PLUGIN_SETTINGS).get("automatico", True))


def on_session_start(player) -> None:
    try:
        _aplicar_config()
    except Exception as e:
        print(f"[Expressões] {e}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    from core import emocoes
    p = parameters or {}
    acao = str(p.get("action") or "mostrar").lower()
    try:
        if acao == "listar":
            return "Sei fazer: " + ", ".join(emocoes.NOMES[k] for k in emocoes.EMOCOES) + "."
        if acao == "automatico":
            ligar = not str(p.get("valor") or "ligar").lower().startswith(("deslig", "off", "não", "nao", "para"))
            salvar_cfg("expressoes", {"automatico": ligar})
            emocoes.AUTOMATICO["ligado"] = ligar
            return ("Pronto: meu rosto muda sozinho conforme o que eu falo." if ligar else
                    "Pronto: só mudo de expressão quando você pedir.")
        nome = str(p.get("emocao") or "").strip()
        emo = emocoes.normalizar(nome)
        if emo is None:
            return f"Não conheço a cara '{nome}'. Sei fazer: " + ", ".join(emocoes.NOMES.values()) + "."
        try:
            segundos = float(p.get("segundos") or 6)
        except (TypeError, ValueError):
            segundos = 6.0
        emocoes.definir(emo, max(1.0, min(600.0, segundos)))
        return f"[ROSTO] Expressão {emocoes.NOMES[emo]} no rosto por {int(segundos)} s. Responda curto, combinando com ela."
    except Exception as e:
        return f"As expressões falharam: {e}"
