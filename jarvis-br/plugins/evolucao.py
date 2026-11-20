"""
JARVIS que evolui sozinho (fork PT-BR 2.4) — veja core/evolucao.py.

    "Jarvis, o que você aprendeu sobre o meu jeito?"
    "Jarvis, para de experimentar" / "volta a experimentar"
    "Jarvis, sempre responde curto"          (fixa um jeito)
    "Jarvis, esquece o que você aprendeu"     (zera o placar; pede confirmação)
"""

from __future__ import annotations

from core import evolucao as E
from plugins._comum import confirmar

PLUGIN = {
    "name": "evolucao",
    "brief": "Self-evolving style: A/B tests answer length, tone and order, learns from the user's reactions.",
    "description": (
        "JARVIS's self-evolution of HOW it answers (length, tone, order), learned from the user's reactions "
        "(interruptions, corrections, repeats, praise). action='relatorio' tells what it learned; 'pausar' stops "
        "experimenting (keeps the winners); 'retomar' resumes; 'fixar' with variante (curta, completa, formal, "
        "descontraido, resposta_antes, passos_antes) locks one style; 'soltar' removes the locks; 'zerar' forgets "
        "everything learned (asks confirmation)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "relatorio | pausar | retomar | fixar | soltar | zerar"},
                       "variante": {"type": "STRING"}},
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "relatorio").lower()
    try:
        if acao == "pausar":
            E.ligar(False)
            return "Parei de experimentar: a partir da próxima conversa uso só o jeito que funcionou melhor."
        if acao == "retomar":
            E.ligar(True)
            return "Voltei a testar jeitos diferentes, discretamente."
        if acao == "fixar":
            return E.fixar(str(p.get("variante") or ""))
        if acao == "soltar":
            d = E.dados()
            d["fixo"], d["desde"] = {}, 0.0
            E._salvar(d)
            return "Tirei as preferências fixas: volto a aprender sozinho."
        if acao == "zerar":
            return confirmar("evolucao_zerar", "Zerar a evolução", "Esquecer tudo o que aprendi sobre o seu jeito "
                             "preferido de resposta?", lambda: (E.zerar(), "Zerei o que eu tinha aprendido.")[1])
        return E.relatorio()
    except Exception as e:
        return f"A evolução falhou: {e}"
