"""
Conselheiro de decisão (fork PT-BR 1.6).

Você descreve a escolha ("aceito o emprego ou continuo na loja?") e o
JARVIS monta: as opções, prós e contras de cada uma, riscos, cenários
"e se…", perguntas que você ainda não respondeu e uma matriz com notas pelos
critérios que importam para VOCÊ (com pesos). Ele não decide por você:
mostra o mapa.

    "Jarvis, me ajuda a decidir entre comprar um notebook ou montar um PC"
    "Jarvis, critérios: preço peso 3, desempenho peso 2, portabilidade peso 1"
    "Jarvis, notas: notebook preço 6 desempenho 7 portabilidade 10; PC preço 8 desempenho 9 portabilidade 2"
"""

from __future__ import annotations

import re

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "conselheiro_decisao",
    "brief": "Decision advisor: options, pros/cons, risks, what-if scenarios and a weighted criteria matrix.",
    "description": (
        "Decision advisor (never decides for the user): action='analisar' with decisao (the choice described; AI maps "
        "options, pros/cons, risks, what-if scenarios, open questions); 'criterios' with texto ('preço peso 3, "
        "desempenho peso 2'); 'notas' with texto ('opção A preço 6 desempenho 7; opção B preço 8 desempenho 9'); "
        "'resultado' (weighted ranking)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "analisar | criterios | notas | resultado"},
                       "decisao": {"type": "STRING"}, "texto": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "decisao.json"


def ler_criterios(texto: str) -> dict[str, float]:
    """'preço peso 3, desempenho 2' → {'preço': 3, 'desempenho': 2} (pura)."""
    saida = {}
    for parte in re.split(r"[,;\n]+", texto or ""):
        m = re.match(r"\s*([\wÀ-ÿ ]+?)\s*(?:peso|=|:)?\s*(\d+(?:[.,]\d+)?)\s*$", parte)
        if m:
            saida[m.group(1).strip().lower()] = float(m.group(2).replace(",", "."))
    return saida


def ler_notas(texto: str, criterios: list[str]) -> dict[str, dict[str, float]]:
    """'notebook preço 6 desempenho 7; PC preço 8 desempenho 9' → {opção: {critério: nota}} (pura)."""
    saida: dict[str, dict[str, float]] = {}
    for bloco in re.split(r"[;\n]+", texto or ""):
        if not bloco.strip():
            continue
        posicoes = sorted((bloco.lower().find(c), c) for c in criterios if bloco.lower().find(c) >= 0)
        if not posicoes:
            continue
        opcao = bloco[:posicoes[0][0]].strip(" :-") or f"opção {len(saida) + 1}"
        notas = {}
        for c in criterios:
            m = re.search(re.escape(c) + r"\s*[:=]?\s*(\d+(?:[.,]\d+)?)", bloco.lower())
            if m:
                notas[c] = float(m.group(1).replace(",", "."))
        saida[opcao] = notas
    return saida


def ranking(criterios: dict[str, float], notas: dict[str, dict[str, float]]) -> list[tuple[str, float]]:
    """Média ponderada de 0 a 10 por opção, da melhor para a pior (pura)."""
    total = sum(criterios.values()) or 1
    res = [(op, sum(n.get(c, 0) * w for c, w in criterios.items()) / total) for op, n in notas.items()]
    return sorted(res, key=lambda x: -x[1])


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "analisar").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        if acao == "analisar":
            decisao = str(p.get("decisao") or "").strip()
            if not decisao:
                return "Qual é a decisão?"
            d = {"decisao": decisao, "criterios": {}, "notas": {}}
            gravar_json(_ARQ, d)
            from plugins import _ia
            if not _ia.disponivel():
                return ("Vamos montar juntos: diga os critérios com pesos (ex.: preço peso 3, tempo peso 2) e depois as notas "
                        "de 0 a 10 de cada opção. (Com a chave do Gemini eu também listo prós, contras e cenários.)")
            r = _ia.perguntar_json(
                "Ajude a pessoa a pensar (não decida por ela). Decisão: " + decisao + "\nResponda SÓ JSON {\"opcoes\": "
                "[{\"nome\": \"\", \"pros\": [], \"contras\": [], \"riscos\": []}], \"cenarios_e_se\": [\"E se ...? → ...\"], "
                "\"perguntas\": [\"o que ela precisa responder para decidir\"], \"criterios_sugeridos\": [\"\"]} em português "
                "do Brasil, concreto e curto.", True, 60)
            if not isinstance(r, dict) or not r.get("opcoes"):
                return "Não consegui montar a análise agora."
            linhas = []
            for o in r["opcoes"]:
                linhas += [f"■ {o.get('nome')}"] + [f"   + {x}" for x in o.get("pros", [])] + \
                    [f"   − {x}" for x in o.get("contras", [])] + [f"   ⚠ {x}" for x in o.get("riscos", [])] + [""]
            linhas += ["E SE…"] + [f"  {x}" for x in r.get("cenarios_e_se", [])] + ["", "PERGUNTAS PARA VOCÊ"] + \
                [f"  ? {x}" for x in r.get("perguntas", [])]
            mostrar(player, f"DECISÃO: {decisao[:60]}", "\n".join(linhas))
            crit = ", ".join(r.get("criterios_sugeridos", [])[:5])
            return (f"Mapeei {len(r['opcoes'])} opção(ões) com prós, contras, riscos e cenários (no painel). Antes de "
                    f"decidir, pense: {'; '.join(r.get('perguntas', [])[:2])}. Se quiser a matriz, diga os pesos dos "
                    f"critérios" + (f" (sugestão: {crit})" if crit else "") + ".")
        if acao == "criterios":
            d["criterios"] = ler_criterios(str(p.get("texto") or ""))
            gravar_json(_ARQ, d)
            if not d["criterios"]:
                return "Não entendi. Exemplo: preço peso 3, desempenho peso 2."
            return "Critérios: " + ", ".join(f"{c} (peso {w:g})" for c, w in d["criterios"].items()) + \
                ". Agora diga as notas de 0 a 10 de cada opção."
        if acao == "notas":
            d.setdefault("notas", {}).update(ler_notas(str(p.get("texto") or ""), list(d.get("criterios", {}))))
            gravar_json(_ARQ, d)
            acao = "resultado"
        if acao == "resultado":
            if not d.get("criterios") or not d.get("notas"):
                return "Faltam os critérios ou as notas."
            rank = ranking(d["criterios"], d["notas"])
            mostrar(player, "MATRIZ DE DECISÃO", "\n".join(f"{op:<25} {nota:4.1f}" for op, nota in rank))
            diferenca = rank[0][1] - rank[1][1] if len(rank) > 1 else 10
            return ("Pelos seus pesos: " + ", ".join(f"{op} {nota:.1f}" for op, nota in rank) + ". "
                    + ("Ficou apertado: o que pesa mais para você no coração? Isso também conta." if diferenca < 0.8
                       else f"{rank[0][0]} se sai melhor nos critérios que você escolheu."))
        return "Ações: analisar, criterios, notas, resultado."
    except Exception as e:
        return f"O conselheiro falhou: {e}"
