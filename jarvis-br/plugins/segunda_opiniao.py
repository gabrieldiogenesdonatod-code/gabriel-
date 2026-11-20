"""
Duas opiniões (fork PT-BR 1.5).

Em respostas IMPORTANTES, um segundo agente — um revisor cético, com
instruções diferentes e sem ver o raciocínio do primeiro — confere a
resposta ANTES de ela chegar até você: aponta erros, riscos e o que faltou,
diz se concorda e entrega a versão corrigida.

O modelo principal chama sozinho em perguntas de saúde, dinheiro, leis,
segurança, ações irreversíveis e decisões de arquitetura — ou quando você pede:

    "Jarvis, pede uma segunda opinião sobre isso"
"""

from __future__ import annotations

from plugins._comum import mostrar

PLUGIN = {
    "name": "segunda_opiniao",
    "brief": "Skeptical second reviewer checks an important draft answer before it is spoken.",
    "description": (
        "Second opinion: BEFORE answering important questions (health, money, legal, security, irreversible actions, "
        "architecture or big technical decisions), call this with pergunta (the user's question) and rascunho (your "
        "draft answer). A skeptical reviewer returns problems found and a corrected answer; then answer the user "
        "with the reviewed version and mention briefly if the reviewer disagreed. Also when the user asks for a "
        "second opinion."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "pergunta": {"type": "STRING"}, "rascunho": {"type": "STRING"}, "area": {"type": "STRING"},
        },
        "required": ["pergunta", "rascunho"],
    },
}

_REVISOR = (
    "Você é um REVISOR CÉTICO e independente. Outro assistente escreveu o rascunho abaixo para a pergunta do usuário. "
    "Procure: erros factuais, contas erradas, riscos não mencionados, suposições frágeis, informação desatualizada, "
    "alternativas melhores e o que deveria ter sido perguntado antes. Seja específico e honesto: se o rascunho estiver "
    "bom, diga que concorda. Em temas de saúde, dinheiro ou leis, lembre de recomendar um profissional quando couber.\n"
    "Responda SÓ JSON: {\"concorda\": true|false, \"problemas\": [\"...\"], \"resposta_revisada\": \"...\"} em "
    "português do Brasil."
)


def revisar(pergunta: str, rascunho: str, area: str = "") -> dict | None:
    from plugins import _ia
    if not _ia.disponivel():
        return None
    r = _ia.perguntar_json(f"{_REVISOR}\n\nÁREA: {area or 'geral'}\nPERGUNTA: {pergunta}\n\nRASCUNHO:\n{rascunho}",
                           inteligente=True, segundos=60)
    return r if isinstance(r, dict) and "resposta_revisada" in r else None


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    pergunta, rascunho = str(p.get("pergunta") or ""), str(p.get("rascunho") or "")
    try:
        if not pergunta or not rascunho:
            return "Preciso da pergunta e do rascunho da resposta."
        r = revisar(pergunta, rascunho, str(p.get("area") or ""))
        if not r:
            return "O revisor não está disponível agora (sem chave de IA ou sem resposta). Responda com o seu rascunho."
        problemas = [str(x) for x in r.get("problemas") or []]
        mostrar(player, "SEGUNDA OPINIÃO", f"PERGUNTA: {pergunta}\n\nRASCUNHO:\n{rascunho}\n\n"
                f"REVISOR: {'concorda' if r.get('concorda') else 'DISCORDA'}\n"
                + "\n".join(f"  • {x}" for x in problemas) + f"\n\nRESPOSTA REVISADA:\n{r['resposta_revisada']}")
        return (f"[SEGUNDA OPINIÃO] O revisor {'concordou' if r.get('concorda') else 'discordou'}. "
                + (f"Problemas: {'; '.join(problemas[:4])}. " if problemas else "")
                + f"Use esta resposta revisada: {r['resposta_revisada']}")
    except Exception as e:
        return f"A segunda opinião falhou: {e}. Responda com o seu rascunho."
