"""
Modo "me ensina errado" (fork PT-BR 1.6).

O JARVIS explica um assunto com UM erro proposital escondido. Você precisa
achar o erro. Ótimo para estudar de verdade (e para treinar o olho crítico).

    "Jarvis, me ensina errado sobre listas em Python"
    "Jarvis, o erro é que a lista não começa no 1"      "Jarvis, desisto, qual era o erro?"
    "Jarvis, qual meu placar no ensina errado?"

Com a chave do Gemini, qualquer assunto; sem ela, um banco de explicações prontas.
"""

from __future__ import annotations

import random
import re
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json

PLUGIN = {
    "name": "ensina_errado",
    "brief": "Teaches a topic with one deliberate hidden mistake; the user must find it; keeps score.",
    "description": (
        "'Teach me wrong' study game: action='comecar' with tema (returns an explanation containing ONE deliberate "
        "error — read it naturally, never reveal the error); action='palpite' with palpite (the user's guess of what is "
        "wrong); action='revelar' (gives up); action='placar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "comecar | palpite | revelar | placar"},
                       "tema": {"type": "STRING"}, "palpite": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "ensina_errado.json"
BANCO = [
    {"tema": "listas em python", "texto": "Em Python, uma lista guarda vários valores em ordem. O primeiro item fica na "
     "posição 1, então lista[1] devolve o primeiro elemento. Dá para adicionar itens com append e remover com remove.",
     "erro": "O primeiro item fica na posição 0 (lista[0]), não na 1.", "chaves": ["0", "zero", "posicao 0", "indice 0"]},
    {"tema": "fotossíntese", "texto": "Na fotossíntese, as plantas usam a luz do sol, a água e o oxigênio do ar para "
     "produzir glicose, e liberam gás carbônico.", "erro": "Elas usam gás carbônico e liberam oxigênio (é o contrário).",
     "chaves": ["gas carbonico", "co2", "liberam oxigenio", "contrario", "invertido"]},
    {"tema": "http", "texto": "Quando você digita um site, o navegador manda um pedido HTTP. O código 404 significa que o "
     "servidor caiu, e o 200 significa que deu tudo certo.", "erro": "404 é 'não encontrado'; servidor com erro é 500.",
     "chaves": ["nao encontrado", "not found", "500", "pagina nao existe"]},
    {"tema": "brasil", "texto": "O Brasil é o maior país da América do Sul, sua capital é o Rio de Janeiro desde 1960 e a "
     "língua oficial é o português.", "erro": "A capital é Brasília desde 1960.", "chaves": ["brasilia"]},
    {"tema": "git", "texto": "No Git, 'git commit' manda as suas mudanças direto para o GitHub, e 'git push' só salva no "
     "seu PC.", "erro": "É o contrário: commit salva no repositório local; push manda para o GitHub.",
     "chaves": ["contrario", "commit salva", "local", "push manda", "invertido"]},
    {"tema": "água", "texto": "A água ferve a 100 °C no nível do mar e congela a 10 °C. Por isso o gelo flutua.",
     "erro": "A água congela a 0 °C (e o gelo flutua por ser menos denso).", "chaves": ["0", "zero", "densidade", "denso"]},
]


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def acertou(palpite: str, chaves: list[str]) -> bool:
    t = _dobrar(palpite)
    return any(re.search(rf"(?<!\w){re.escape(_dobrar(c))}(?!\w)", t) for c in chaves)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "comecar").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("acertos", 0)
        d.setdefault("rodadas", 0)
        if acao == "comecar":
            tema = str(p.get("tema") or "").strip()
            from plugins import _ia
            item = None
            if _ia.disponivel() and tema:
                r = _ia.perguntar_json(
                    f"Explique '{tema}' em 3 a 5 frases para um estudante, colocando UM erro factual proposital e plausível "
                    "no meio (não exagerado). Responda SÓ JSON {\"texto\": \"explicação com o erro\", \"erro\": \"qual é o erro "
                    "e o certo\", \"chaves\": [\"3 a 6 palavras que alguém diria ao achar o erro\"]} em português do Brasil.",
                    True, 45)
                if isinstance(r, dict) and r.get("texto") and r.get("erro"):
                    item = {"tema": tema, "texto": str(r["texto"]), "erro": str(r["erro"]),
                            "chaves": [str(x) for x in r.get("chaves") or []]}
            if not item:
                candidatos = [b for b in BANCO if tema and _dobrar(tema) in _dobrar(b["tema"])] or BANCO
                item = random.choice(candidatos)
            d["atual"] = item
            d["rodadas"] += 1
            gravar_json(_ARQ, d)
            return (f"[ME ENSINA ERRADO] Leia esta explicação com naturalidade, SEM dar pistas do erro, e desafie o "
                    f"usuário a achar o erro: \"{item['texto']}\"")
        atual = d.get("atual")
        if acao == "placar":
            return f"Você achou {d['acertos']} erro(s) em {d['rodadas']} rodada(s)."
        if not atual:
            return "Não há rodada em andamento. Diga 'me ensina errado sobre …'."
        if acao == "palpite":
            palpite = str(p.get("palpite") or "")
            ok = acertou(palpite, atual.get("chaves") or [])
            if not ok:                                        # a IA confere palpites com outras palavras
                from plugins import _ia
                if _ia.disponivel():
                    r = _ia.perguntar_json(f"O erro era: {atual['erro']}. O aluno disse: {palpite}. Ele achou o erro? "
                                           'Responda SÓ JSON {"achou": true|false}', False, 15)
                    ok = bool(isinstance(r, dict) and r.get("achou"))
            if ok:
                d["acertos"] += 1
                d.pop("atual", None)
                gravar_json(_ARQ, d)
                return f"[ACERTOU] Parabenize! O erro era: {atual['erro']} Placar: {d['acertos']}/{d['rodadas']}."
            return "[AINDA NÃO] Diga que não é isso e dê uma pista pequena, sem entregar o erro."
        if acao == "revelar":
            d.pop("atual", None)
            gravar_json(_ARQ, d)
            return f"O erro era: {atual['erro']}"
        return "Ações: comecar, palpite, revelar, placar."
    except Exception as e:
        return f"O 'me ensina errado' falhou: {e}"
