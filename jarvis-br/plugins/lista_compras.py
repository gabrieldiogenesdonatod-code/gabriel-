"""
Lista de compras (fork PT-BR 2.17).

    "Jarvis, põe leite, ovos e sabão em pó na lista"
    "Jarvis, o que tem na lista?"            → organizada por seção do mercado
    "Jarvis, já comprei o leite"             "Jarvis, limpa a lista"
    "Jarvis, manda a lista no meu whats"     → para você (ou "para a vó")

Organiza por seção (hortifruti, açougue, padaria, laticínios, limpeza…) na ordem
de um mercado. Fica em memory/lista_compras.json.
"""

from __future__ import annotations

import re
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "lista_compras",
    "brief": "Shopping list by voice, grouped by store section; mark bought; send to WhatsApp.",
    "description": (
        "Shopping list. action='adicionar' with itens (comma separated). action='ver'. action='comprado' with itens. "
        "action='limpar'. action='enviar' (optional para = 'mim' or contact) sends the list by WhatsApp."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "itens": {"type": "STRING"},
                                                    "para": {"type": "STRING"}}, "required": ["action"]},
}

ARQ = MEMORIA / "lista_compras.json"
SECOES = [("Hortifruti", "banana maca laranja limao tomate cebola alho batata cenoura alface fruta verdura legume mamao"),
          ("Açougue", "carne frango peixe linguica bife costela patinho file"),
          ("Padaria", "pao bolo biscoito bolacha torrada"),
          ("Laticínios", "leite queijo iogurte manteiga requeijao presunto ovo ovos margarina"),
          ("Mercearia", "arroz feijao macarrao oleo acucar sal cafe farinha molho milho extrato tempero"),
          ("Bebidas", "agua refrigerante suco cerveja"),
          ("Limpeza", "sabao detergente amaciante desinfetante agua sanitaria esponja vassoura alvejante"),
          ("Higiene", "papel higienico shampoo sabonete pasta escova desodorante fralda absorvente")]


def _n(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()


def secao(item: str) -> str:
    t = _n(item)
    for nome, palavras in SECOES:
        if any(re.search(rf"\b{w}", t) for w in palavras.split()):
            return nome
    return "Outros"


def separar(texto: str) -> list[str]:
    return [x.strip() for x in re.split(r",|;|\be\b|\n", texto or "") if x.strip()]


def formatar(itens: list[str]) -> str:
    ordem = [s for s, _ in SECOES] + ["Outros"]
    grupos: dict[str, list[str]] = {}
    for i in itens:
        grupos.setdefault(secao(i), []).append(i)
    return "\n".join(f"*{s}*\n" + "\n".join(f"  ☐ {i}" for i in grupos[s]) for s in ordem if s in grupos)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "ver").lower()
    lista = ler_json(ARQ, []) or []
    try:
        if a == "adicionar":
            novos = [i for i in separar(p.get("itens")) if _n(i) not in {_n(x) for x in lista}]
            lista += novos
            gravar_json(ARQ, lista)
            return f"Adicionei {', '.join(novos) or 'nada novo'}. A lista tem {len(lista)} itens."
        if a == "comprado":
            tirar = {_n(i) for i in separar(p.get("itens"))}
            novos = [x for x in lista if not any(t in _n(x) for t in tirar)]
            gravar_json(ARQ, novos)
            return f"Tirei {len(lista) - len(novos)} item(ns). Faltam {len(novos)}."
        if a == "limpar":
            gravar_json(ARQ, [])
            return "Lista limpa."
        if not lista:
            return "A lista de compras está vazia."
        texto = formatar(lista)
        if a == "enviar":
            from plugins import whatsapp_conversas as WC
            para = str(p.get("para") or "mim")
            if para.lower() in ("mim", "eu", "me"):
                return WC.run({"action": "para_mim", "texto": "🛒 Lista de compras\n" + texto}, player)
            return WC.run({"action": "mandar", "contato": para, "texto": "🛒 Lista de compras\n" + texto}, player)
        mostrar(player, "LISTA DE COMPRAS", texto.replace("*", ""))
        return f"{len(lista)} itens: " + ", ".join(lista[:12]) + "."
    except Exception as e:
        return f"A lista de compras falhou: {e}"
