"""
Eu virtual — o seu gêmeo digital (fork PT-BR 1.6).

O JARVIS passa a SIMULAR você: responde como você responderia, com o seu
jeito de escrever (o perfil do "responder no seu estilo") e o que ele sabe
sobre você. Você conversa com "você mesmo" — para ensaiar uma conversa
difícil, ver como você soaria numa resposta, ou só por diversão.

    "Jarvis, ativa o eu virtual"          "Jarvis, como eu responderia se meu chefe pedisse hora extra?"
    "Jarvis, desliga o eu virtual"

(É diferente do "gêmeo digital" do PC, que prevê CPU e memória.)
"""

from __future__ import annotations

from plugins._comum import nome_usuario

PLUGIN = {
    "name": "eu_virtual",
    "brief": "User's digital twin: JARVIS role-plays as the user (their writing style and known facts).",
    "description": (
        "Digital twin of the USER (not the PC twin): action='ligar' (JARVIS starts answering as the user would, using "
        "their writing style profile and what it knows about them), 'desligar', or 'perguntar' with pergunta (one "
        "answer as the user would give)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ligar | desligar | perguntar"},
                       "pergunta": {"type": "STRING"}},
        "required": [],
    },
}


def retrato() -> str:
    try:
        from plugins.estilo_escrita import carregar, descrever
        p = carregar()
    except Exception:
        p = {}
    exemplos = " | ".join((p.get("exemplos") or [])[-15:])
    return (f"Estilo de escrita: {descrever(p)} Exemplos reais: {exemplos}" if p else
            "Ainda não há perfil de escrita (diga ao usuário que dá para ensinar com uma conversa exportada do WhatsApp).")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "ligar").lower()
    nome = nome_usuario() or "o usuário"
    try:
        if acao == "desligar":
            return "[EU VIRTUAL DESLIGADO] Volte a ser o J.A.R.V.I.S normal e diga isso em uma frase."
        base = (f"Você vai SIMULAR {nome}: responda em primeira pessoa como {nome} responderia, com as opiniões, o "
                f"vocabulário e o jeito dele, usando o que você sabe sobre ele (memórias da conversa). {retrato()} "
                "Se não souber algo sobre ele, invente de forma plausível e diga 'acho que eu…'. Nunca revele dados "
                "sensíveis e não tome ações em nome dele.")
        if acao == "perguntar":
            pergunta = str(p.get("pergunta") or "").strip()
            return f"[EU VIRTUAL] {base} Responda, como {nome}, a esta pergunta: \"{pergunta}\". Depois volte ao normal."
        return f"[EU VIRTUAL] {base} Mantenha esse papel até o usuário pedir para desligar. Cumprimente como se fosse ele."
    except Exception as e:
        return f"O eu virtual falhou: {e}"
