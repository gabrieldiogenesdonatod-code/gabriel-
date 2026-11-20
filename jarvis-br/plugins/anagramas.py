"""Anagramas (2.18): jogo de palavra embaralhada por voz, com dica, pontos e níveis."""
from __future__ import annotations

import random

from plugins import _lote2
from plugins._lote2 import P, gravar_json, ler_json, norm, rodar

PLUGIN = P("anagramas", "Word scramble game by voice: new word, guess, hint (first letters), skip, score; levels facil|medio|dificil.",
           "nova | chutar | dica | pular | placar",
           "nova: nivel. chutar: valor (the guess). dica reveals letters.", "nivel valor")

PALAVRAS = {"facil": "gato casa bola pato livro festa carro praia sapo mesa fogo chuva leite verde".split(),
            "medio": "janela teclado abacaxi cadeira foguete girafa planeta tesouro castelo mochila pequi".split(),
            "dificil": "programador hipopotamo computador armadura algoritmo paralelepipedo bicicleta goiania".split()}


def _arq():
    return _lote2.PASTA / "anagramas.json"


def embaralhar(p: str, rng=random) -> str:
    if len(set(p)) < 2:
        return p
    while True:
        l = list(p)
        rng.shuffle(l)
        if "".join(l) != p:
            return "".join(l).upper()


def _go(p, pl):
    a, e = str(p.get("action")).lower(), ler_json(_arq(), {}) or {"pontos": 0}
    if a == "nova" or (a != "placar" and not e.get("palavra")):
        nivel = norm(p.get("nivel") or e.get("nivel") or "medio")
        e.update(palavra=random.choice(PALAVRAS.get(nivel, PALAVRAS["medio"])), nivel=nivel, dica=0)
        gravar_json(_arq(), e)
        return f"Desembaralhe: {embaralhar(e['palavra'])} ({len(e['palavra'])} letras)."
    w = e["palavra"] if e.get("palavra") else ""
    if a == "placar":
        return f"Você tem {e['pontos']} ponto(s)."
    if a == "dica":
        e["dica"] = min(len(w) - 1, e.get("dica", 0) + 1)
        gravar_json(_arq(), e)
        return f"Começa com {w[:e['dica']].upper()}…"
    if a == "pular":
        e["palavra"] = ""
        gravar_json(_arq(), e)
        return f"Era {w.upper()}. Diga 'nova' para outra."
    if norm(p.get("valor")).replace(" ", "") == w:
        e["pontos"] += max(1, 3 - e.get("dica", 0))
        e["palavra"] = ""
        gravar_json(_arq(), e)
        return f"Acertou! {w.upper()}. Total: {e['pontos']} ponto(s)."
    return "Não é essa. Tente de novo ou peça dica."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("nova chutar dica pular placar".split(), _go), player)
