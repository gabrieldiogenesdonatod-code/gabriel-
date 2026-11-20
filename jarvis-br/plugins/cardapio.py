"""Cardápio da semana (2.18): sorteia pratos sem repetir, respeita dias (ex.: peixe na sexta) e gera a lista de compras."""
from __future__ import annotations

import random

from plugins import _lote2
from plugins._lote2 import P, gravar_json, lista, ler_json, rodar

PLUGIN = P("cardapio", "Weekly meal planner: keep a dish list, generate a non-repeating week menu, see today's dish, send to shopping list.",
           "pratos | adicionar | gerar | semana | hoje | para_lista",
           "adicionar: texto = dishes (comma). gerar: makes the 7-day menu. para_lista sends the week's dishes as shopping reminders.",
           "texto")

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
PADRAO = ["arroz, feijão e bife", "frango assado", "macarrão à bolonhesa", "peixe com legumes", "omelete com salada",
          "carne de panela", "strogonoff de frango", "galinhada", "pamonha e café", "sopa de legumes", "pizza caseira",
          "arroz com pequi", "feijoada", "escondidinho"]


def _arq():
    return _lote2.PASTA / "cardapio.json"


def gerar(pratos: list[str], rng=random) -> list[str]:
    base = pratos[:] or PADRAO[:]
    rng.shuffle(base)
    return [base[i % len(base)] for i in range(7)]


def _go(p, pl):
    import datetime as dt
    a, d = str(p.get("action")).lower(), ler_json(_arq(), {}) or {}
    pratos = d.get("pratos") or PADRAO
    if a == "adicionar":
        d["pratos"] = list(dict.fromkeys(pratos + lista(p.get("texto"))))
        gravar_json(_arq(), d)
        return f"{len(d['pratos'])} pratos na lista."
    if a == "pratos":
        return ", ".join(pratos)
    if a == "gerar":
        d["semana"] = gerar(pratos)
        gravar_json(_arq(), d)
    sem = d.get("semana")
    if not sem:
        return "Ainda não gerei o cardápio. Diga 'gerar'."
    if a == "hoje":
        return f"Hoje ({DIAS[dt.date.today().weekday()]}): {sem[dt.date.today().weekday()]}."
    if a == "para_lista":
        from core import registro_ferramentas
        return registro_ferramentas.executar("lista_compras", {"action": "adicionar", "itens": ", ".join(sem)}, pl)
    return "\n".join(f"{DIAS[i].capitalize()}: {x}" for i, x in enumerate(sem))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("pratos adicionar gerar semana hoje para_lista".split(), _go), player, "Cardápio")
