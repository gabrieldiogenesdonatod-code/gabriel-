"""Filmes e séries para ver (2.18): lista, episódio onde parou, nota, e sorteio do que ver hoje."""
from __future__ import annotations

import random

from plugins._lote2 import Colecao, P, numeros, rodar

PLUGIN = P("watchlist", "Movies/series/anime to watch: add, track season/episode, rate, mark watched, pick one at random.",
           "adicionar | episodio | assisti | nota | lista | sortear | apagar",
           "adicionar: nome, tipo (filme|serie|anime). episodio: nome, valor ('T2E5'). assisti/nota: nome, valor (0-10). "
           "sortear: tipo optional.",
           "nome tipo valor")

W = Colecao("watchlist")


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), p.get("nome")
    if a == "adicionar":
        W.por(nome, {"tipo": str(p.get("tipo") or "filme").lower(), "ep": "", "visto": False, "nota": None})
        return f"'{nome}' na lista."
    pend = [w for w in W.tudo().values() if not w["visto"]]
    if a == "lista":
        return "\n".join(f"{w['nome']} ({w['tipo']}{' ' + w['ep'] if w['ep'] else ''})" for w in pend) or "Lista vazia."
    if a == "sortear":
        t = str(p.get("tipo") or "").lower()
        op = [w for w in pend if not t or w["tipo"] == t]
        return f"Hoje: {random.choice(op)['nome']}." if op else "Nada pendente."
    w = W.pegar(nome)
    if not w:
        return "Não está na lista."
    if a == "apagar":
        W.tirar(nome)
        return "Removido."
    if a == "episodio":
        w["ep"] = str(p.get("valor") or "").upper().replace(" ", "")
    elif a == "assisti":
        w["visto"] = True
    if a in ("assisti", "nota") and numeros(p.get("valor")):
        w["nota"] = numeros(p.get("valor"))[0]
    W.por(w["nome"], w)
    return f"{w['nome']}: " + ("visto" if w["visto"] else f"parou em {w['ep'] or 'início'}") + \
        (f", nota {w['nota']:g}." if w["nota"] is not None else ".")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("adicionar episodio assisti nota lista sortear apagar".split(), _go), player, "Watchlist")
