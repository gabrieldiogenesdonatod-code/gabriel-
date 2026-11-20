"""
Modo "explica pra uma criança" (fork PT-BR 2.9/2.10).

Pega qualquer assunto difícil e pede pro cérebro explicar com palavras simples,
uma comparação do dia a dia e um exemplo — do jeito que você explicaria pra uma
criança (ou pra quem é leigo total no assunto).

    "Jarvis, me explica o que é blockchain como se eu tivesse 8 anos."
    "Jarvis, explica pra criança: por que o céu é azul?"
    "Jarvis, explica isso aí mais simples ainda."      (nível 'bebê')

Não precisa de internet nem de nada novo: é só um jeito de pedir a resposta. A
idade muda o tom (5, 8, 12 anos ou 'leigo adulto'). Sem a chave do Gemini, ele
avisa que precisa do cérebro ligado pra responder.
"""

from __future__ import annotations

import re
import unicodedata

PLUGIN = {
    "name": "explica_crianca",
    "brief": "Explain-like-I'm-a-kid: explains any hard topic with simple words, an everyday analogy and an example.",
    "description": (
        "Explains a hard topic in the simplest possible way — like to a child or a total beginner — with an everyday "
        "analogy and a small example. Use for 'explica como se eu tivesse X anos', 'explica pra criança', 'explica "
        "isso bem simples', 'mais simples ainda', 'me explica de um jeito fácil'. action='explicar' with assunto "
        "(the topic or text, in the user's words) and optional idade (5, 8, 12, or 'adulto' for a lay adult). "
        "'mais_simples' with assunto makes it even simpler than before. Returns an instruction for the brain; "
        "always pass the topic in the user's own words."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "explicar | mais_simples"},
            "assunto": {"type": "STRING", "description": "the topic/text to explain, in the user's words"},
            "idade": {"type": "STRING", "description": "5 | 8 | 12 | adulto (optional; default 8)"},
        },
        "required": ["assunto"],
    },
}

NIVEIS = {
    5: ("uma criança de 5 anos", "só palavras bem simples e curtas, como numa historinha; nada de número ou termo "
        "técnico"),
    8: ("uma criança de 8 anos", "palavras simples e uma comparação com coisa de criança (brinquedo, escola, comida)"),
    12: ("um pré-adolescente de 12 anos", "linguagem simples, mas pode usar um termo técnico se explicar ele na hora"),
    99: ("um adulto leigo, que nunca ouviu falar do assunto", "sem jargão; se usar um termo técnico, explique entre "
         "parênteses"),
}


def ler_idade(idade, padrao: int = 8) -> int:
    """'5', 'cinco anos', 'adulto', 'bebê', 'leigo' → a chave de NIVEIS (pura)."""
    t = unicodedata.normalize("NFKD", str(idade or "").lower()).encode("ascii", "ignore").decode()
    if any(w in t for w in ("adulto", "leigo", "burro", "zero")):
        return 99
    if any(w in t for w in ("bebe", "3 anos", "tres anos", "bem simples", "simples ainda", "mais simples")):
        return 5
    m = re.search(r"\b(\d{1,2})\b", t)
    if m:
        n = int(m.group(1))
        return min((k for k in NIVEIS if k >= n), default=99)
    for pal, n in (("cinco", 5), ("oito", 8), ("doze", 12), ("dez", 12)):
        if pal in t:
            return n
    return padrao


def limpar_assunto(assunto: str) -> str:
    t = " ".join(str(assunto or "").split())
    t = re.sub(r"(?i)^(jarvis[,:]?\s*)?(me )?(explica|explique|o que (é|e)|que (é|e))\b"
               r"( (isso|aquilo|pra crian[çc]a|mais simples|de novo|melhor))?\s*[:,-]?\s*", "", t, count=1).strip()
    t = re.sub(r"(?i)\s*(como se eu tivesse.*|pra uma crian[çc]a.*|pra crian[çc]a.*|bem simples.*)$", "", t).strip()
    return (t or " ".join(str(assunto or "").split())).strip(" ?.")


def instrucao(assunto: str, idade: int, ainda_mais: bool = False) -> str:
    quem, como = NIVEIS.get(idade, NIVEIS[8])
    reforco = " Foi pedido para ficar AINDA mais simples que antes, então capriche na facilidade." if ainda_mais else ""
    return (f"[EXPLICA FÁCIL] Explique \"{assunto}\" para {quem}. Use {como}. Estrutura: (1) uma frase dizendo o que "
            f"é, (2) uma comparação com algo do dia a dia começando com 'é tipo...', (3) um exemplo rápido. No "
            f"máximo 5 frases curtas, em português do Brasil, tom gentil e animado, sem enrolação.{reforco} "
            "Responda direto ao usuário; não chame nenhuma ferramenta.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "explicar").strip().lower()
    assunto = limpar_assunto(p.get("assunto") or p.get("texto") or "")
    if len(assunto) < 2:
        return "O que você quer que eu explique?"
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return ("Pra explicar eu preciso do cérebro (Gemini) ligado — coloque a chave em ⚙ MOTOR & "
                    "PROVEDORES. Aí eu explico qualquer coisa do jeito mais simples.")
    except Exception:
        pass
    idade = ler_idade(p.get("idade"), padrao=5 if "mais_simples" in acao or "simples" in acao else 8)
    return instrucao(assunto, idade, ainda_mais="mais" in acao)
