"""
Modo debate (fork PT-BR 1.6).

Você dá uma opinião e o JARVIS defende o lado OPOSTO, com bons argumentos,
um ponto por vez, educado e sem apelar. No fim, ele mostra os melhores
argumentos dos dois lados e onde a sua posição ficou mais forte ou mais fraca.
Ótimo para treinar argumentação (e para entrevistas, provas e redação).

    "Jarvis, modo debate: eu acho que o home office é melhor"
    "Jarvis, encerra o debate"
"""

from __future__ import annotations

import time

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "modo_debate",
    "brief": "Debate mode: JARVIS argues the opposite side of the user's opinion, then summarizes both sides.",
    "description": (
        "Debate practice. action='comecar' with opiniao (the user's position); after each user argument call "
        "action='argumento' with texto (verbatim); action='encerrar' gives the final summary."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "comecar | argumento | encerrar"},
                       "opiniao": {"type": "STRING"}, "texto": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "debate.json"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "comecar").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        if acao == "comecar":
            opiniao = str(p.get("opiniao") or "").strip()
            if not opiniao:
                return "Qual é a sua opinião? Eu defendo o contrário."
            d = {"opiniao": opiniao, "argumentos": [], "inicio": time.time()}
            gravar_json(_ARQ, d)
            return (f"[DEBATE] O usuário defende: \"{opiniao}\". Defenda com convicção o lado OPOSTO, em português do "
                    "Brasil: um argumento forte por vez (até 3 frases), com dado ou exemplo concreto quando souber, sem "
                    "ofensas e sem concordar fácil. Depois de cada argumento do usuário, chame modo_debate "
                    "action='argumento' com o texto dele e rebata. Comece com seu primeiro argumento.")
        if not d.get("opiniao"):
            return "Não há debate em andamento."
        if acao == "argumento":
            d["argumentos"].append(str(p.get("texto") or ""))
            gravar_json(_ARQ, d)
            return "[DEBATE] Rebata esse argumento com um contra-argumento forte (até 3 frases) e faça uma pergunta difícil."
        if acao == "encerrar":
            from plugins import _ia
            resumo = ""
            if _ia.disponivel() and d["argumentos"]:
                resumo = _ia.perguntar(
                    f"Debate sobre: \"{d['opiniao']}\". Argumentos do usuário: " + " | ".join(d["argumentos"]) +
                    ". Faça um balanço justo em português do Brasil: os 2 melhores argumentos do usuário, os 2 melhores do "
                    "lado oposto, o ponto mais fraco da posição dele e como reforçá-lo. Até 8 frases.", True, 60) or ""
            mostrar(player, f"DEBATE: {d['opiniao'][:60]}", resumo or "\n".join(f"• {a}" for a in d["argumentos"]))
            gravar_json(_ARQ, {})
            return "[DEBATE ENCERRADO] " + (resumo or "Agradeça pelo debate e faça um balanço justo dos dois lados em 3 frases.")
        return "Ações: comecar, argumento, encerrar."
    except Exception as e:
        return f"O modo debate falhou: {e}"
