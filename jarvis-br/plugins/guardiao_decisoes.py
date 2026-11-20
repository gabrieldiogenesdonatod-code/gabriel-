"""
Guardião de decisões — plugin de voz (ideia 12, fork PT-BR 1.4).

    "Jarvis, é seguro apagar a pasta Temp?"        → avalia e explica
    "Jarvis, sempre me pergunte antes de desligar"  → regra sua
    "Jarvis, pode organizar os downloads sozinho"   → regra sua
    "Jarvis, nunca feche o OBS"                     → regra sua
    "Jarvis, quais são as suas regras?"

A avaliação em si está em plugins/_guardiao.py e é usada também pelas
habilidades combináveis, pelo criador de ferramentas e pelo laboratório.
"""

from __future__ import annotations

from plugins import _guardiao as g

PLUGIN = {
    "name": "guardiao_decisoes",
    "brief": "Evaluate risk of an action; set or list the user's safety rules.",
    "description": (
        "Decision guard: evaluates risk, reversibility, impact and permissions of an action "
        "before doing it. action='avaliar' with descricao (what would be done) and optionally "
        "ferramenta for 'é seguro…?', 'tem risco…?'. action='regra' with tipo = perguntar | "
        "sozinho | nunca and termo, for 'sempre me pergunte antes de X', 'pode fazer X sozinho', "
        "'nunca faça X'. action='regras' lists them; action='remover' (termo) deletes a rule."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "avaliar | regra | regras | remover"},
            "descricao": {"type": "STRING"}, "ferramenta": {"type": "STRING"},
            "tipo": {"type": "STRING"}, "termo": {"type": "STRING"},
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "avaliar").lower()
    try:
        if a == "avaliar":
            return g.avaliar(str(p.get("ferramenta") or ""), {}, str(p.get("descricao") or "")).texto()
        if a == "regra":
            return g.definir_regra(str(p.get("tipo") or ""), str(p.get("termo") or ""))
        if a == "regras":
            pol = g.politica()
            partes = [f"{rot}: {', '.join(pol.get(k, [])) or 'nenhuma'}" for k, rot in
                      (("sempre_perguntar", "Sempre pergunto antes de"), ("pode_sozinho", "Faço sozinho"),
                       ("nunca", "Nunca faço"))]
            return ". ".join(partes) + ". Fora isso, sigo o risco de cada ação."
        if a == "remover":
            termo = str(p.get("termo") or "").strip()
            pol = g.politica()
            achou = False
            for k in ("sempre_perguntar", "pode_sozinho", "nunca"):
                if termo in pol.get(k, []):
                    pol[k].remove(termo)
                    achou = True
            if achou:
                from plugins._comum import gravar_json
                gravar_json(g.ARQ_POLITICA, pol)
                return f"Regra sobre '{termo}' removida."
            return f"Não há regra sobre '{termo}'."
        return "Use avaliar, regra, regras ou remover."
    except Exception as e:
        return f"O guardião falhou: {e}"
