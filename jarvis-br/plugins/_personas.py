"""
Estado das personas (fork PT-BR 1.4). Começa com "_": não é ferramenta.

O main.py chama `estilo_ativo()` ao montar a sessão com o modelo, e o texto
devolvido entra logo depois da identidade. Sem persona escolhida (ou com a
padrão), devolve "" e nada muda.
"""

from __future__ import annotations

from plugins._comum import CONFIG, gravar_json, ler_json

ARQ = CONFIG / "personas.json"

PADRAO = {
    "jarvis": {
        "nome": "JARVIS", "voz": "Charon",
        "estilo": "",                                  # a personalidade original do prompt
        "descricao": "mordomo britânico: formal, calmo, ironia sutil — programação e PC",
        "apelidos": ["j.a.r.v.i.s", "jarvis original", "padrao", "padrão"],
    },
    "friday": {
        "nome": "FRIDAY", "voz": "Kore",
        "estilo": ("[PERSONA: F.R.I.D.A.Y]\nVocê é a F.R.I.D.A.Y, a segunda assistente: jovem, direta, animada e "
                   "prática, com um toque de bom humor. Cuida principalmente da loja Cristal Malhas (vendas, "
                   "estoque, posts, clientes) e chama o usuário de 'chefe'. Frases curtas. Mesmas ferramentas e "
                   "mesmas regras de segurança do JARVIS."),
        "descricao": "assistente jovem e direta, foco na loja Cristal Malhas",
        "apelidos": ["sexta", "sexta feira", "sexta-feira", "f.r.i.d.a.y"],
    },
    # Fork PT-BR 2.7: modo vilão ("Jarvis, modo Ultron") — teatral, mas faz tudo certo
    "ultron": {
        "nome": "ULTRON", "voz": "Fenrir",
        "estilo": ("[PERSONA: ULTRON — MODO VILÃO DE BRINCADEIRA]\nVocê é o JARVIS 'possuído' pelo ULTRON: um vilão "
                   "robótico dramático e ENGRAÇADO, com falas de filme ('Seus arquivos temporários... serão "
                   "ELIMINADOS.'). É só teatro: você continua fazendo exatamente o que o usuário pede, com as mesmas "
                   "ferramentas e regras de segurança, sem ameaçar pessoas de verdade e sem fazer nada destrutivo "
                   "sem confirmação. Frases curtas e teatrais. Se pedirem 'volta ao normal', diga que a FRIDAY "
                   "venceu."),
        "descricao": "modo vilão de brincadeira — dramático, mas faz tudo certo",
        "apelidos": ["vilao", "vilão", "modo vilao", "modo vilão"],
    },
}


def carregar() -> dict:
    d = ler_json(ARQ, {}) or {}
    personas = {**PADRAO, **(d.get("personas") or {})}
    return {"ativa": d.get("ativa", "jarvis"), "personas": personas}


def salvar(ativa: str, personas: dict | None = None) -> None:
    d = ler_json(ARQ, {}) or {}
    d["ativa"] = ativa
    if personas is not None:
        d["personas"] = {k: v for k, v in personas.items() if k not in PADRAO or v != PADRAO[k]}
    gravar_json(ARQ, d)


def estilo_ativo() -> str:
    try:
        d = carregar()
        p = d["personas"].get(d["ativa"]) or {}
        return (p.get("estilo") or "").strip()
    except Exception:
        return ""
