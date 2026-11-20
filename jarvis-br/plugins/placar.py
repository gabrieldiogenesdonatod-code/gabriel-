"""Placar (2.18): marca pontos de truco, dominó, futebol de mesa ou qualquer jogo; avisa quem venceu ao bater a meta."""
from __future__ import annotations

from plugins import _lote2
from plugins._lote2 import P, gravar_json, ler_json, lista, norm, numeros, rodar

PLUGIN = P("placar", "Scoreboard for any game (truco, dominó, cards): players/teams, add/remove points, target score winner, history of matches.",
           "novo | ponto | ver | desfazer | historico",
           "novo: nomes (comma), meta (e.g. 12 for truco). ponto: nome, valor (default 1, negative removes).",
           "nomes meta nome valor")


def _arq():
    return _lote2.PASTA / "placar.json"


def _ver(e):
    return " x ".join(f"{k} {v:g}" for k, v in e["pts"].items()) + (f" (até {e['meta']:g})" if e.get("meta") else "")


def _go(p, pl):
    a, e = str(p.get("action")).lower(), ler_json(_arq(), {}) or {}
    if a == "novo":
        nomes = lista(p.get("nomes")) or ["Nós", "Eles"]
        e.update(pts={n: 0 for n in nomes}, meta=(numeros(p.get("meta")) or [0])[0], log=[])
        gravar_json(_arq(), e)
        return f"Placar novo: {_ver(e)}."
    if a == "historico":
        return "\n".join(e.get("hist", [])[-10:]) or "Sem partidas terminadas."
    if not e.get("pts"):
        return "Comece um placar com 'novo'."
    if a == "desfazer" and e.get("log"):
        n, v = e["log"].pop()
        e["pts"][n] -= v
    elif a == "ponto":
        alvo = next((k for k in e["pts"] if norm(k) == norm(p.get("nome"))), None)
        if not alvo:
            return f"Quem? {', '.join(e['pts'])}."
        v = (numeros(p.get("valor")) or [1])[0]
        e["pts"][alvo] += v
        e["log"].append([alvo, v])
        if e.get("meta") and e["pts"][alvo] >= e["meta"]:
            e.setdefault("hist", []).append(f"{alvo} venceu — {_ver(e)}")
            fim = f"{alvo} VENCEU! {_ver(e)}."
            e["pts"] = {k: 0 for k in e["pts"]}
            e["log"] = []
            gravar_json(_arq(), e)
            return fim + " Placar zerado para a próxima."
    gravar_json(_arq(), e)
    return _ver(e) + "."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("novo ponto ver desfazer historico".split(), _go), player)
