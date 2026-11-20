"""Caça-palavras (2.19): gera um caça-palavras para imprimir com as palavras que você escolher (ou de um tema) — bom para crianças e aulas."""
from __future__ import annotations

import html
import random

from plugins._lote2 import P, lista, norm, num1, pagina, rodar

PLUGIN = P("caca_palavras", "Printable word-search puzzle generator (HTML) from your words or a theme; easy (→ ↓) or hard (diagonals and reversed).",
           "gerar | temas",
           "gerar: palavras (comma list) or tema (animais|frutas|escola|natal|programacao), tamanho (grid, default 12), nivel (facil|dificil).",
           "palavras tema tamanho nivel")

TEMAS = {"animais": "gato cachorro elefante girafa macaco tucano jacare coruja peixe cavalo",
         "frutas": "banana manga abacaxi laranja morango goiaba caju melancia uva pequi",
         "escola": "caderno lapis borracha professor recreio mochila livro tesoura regua lousa",
         "natal": "presente estrela arvore sino ceia anjo vela familia presepio rena",
         "programacao": "python variavel funcao classe lista laco teste codigo servidor bug"}
FACIL, DIFICIL = [(0, 1), (1, 0)], [(0, 1), (1, 0), (1, 1), (-1, 1), (0, -1), (-1, 0)]


def gerar(palavras: list[str], n: int = 12, dificil: bool = False, rng=random) -> tuple[list[list[str]], list[str]]:
    """Grade n×n e as palavras que couberam. Pura (com rng)."""
    g = [[""] * n for _ in range(n)]
    postas = []
    for w in sorted({norm(x).replace(" ", "").replace("-", "").upper() for x in palavras if x.strip()}, key=len, reverse=True):
        if not 2 <= len(w) <= n:
            continue
        for _ in range(300):
            dl, dc = rng.choice(DIFICIL if dificil else FACIL)
            l0, c0 = rng.randrange(n), rng.randrange(n)
            pos = [(l0 + dl * i, c0 + dc * i) for i in range(len(w))]
            if all(0 <= l < n and 0 <= c < n and g[l][c] in ("", w[i]) for i, (l, c) in enumerate(pos)):
                for i, (l, c) in enumerate(pos):
                    g[l][c] = w[i]
                postas.append(w)
                break
    return [[x or rng.choice("ABCDEFGHIJLMNOPRSTUV") for x in linha] for linha in g], postas


def _go(p, pl):
    if p["action"] == "temas":
        return "Temas: " + ", ".join(TEMAS) + ". Ou diga as suas palavras."
    palavras = lista(p.get("palavras")) or TEMAS.get(norm(p.get("tema")), TEMAS["animais"]).split()
    n = max(8, min(20, int(num1(p, "tamanho", 12))))
    grade, postas = gerar(palavras, n, norm(p.get("nivel")).startswith("dif"))
    corpo = ("<table>" + "".join("<tr>" + "".join(f"<td style='width:26px;height:26px;font:18px monospace'>{c}</td>" for c in l) + "</tr>"
                                 for l in grade) + "</table><p><b>Encontre:</b> " + html.escape(", ".join(postas)) + "</p>")
    return f"Caça-palavras {n}x{n} com {len(postas)} palavra(s) pronto para imprimir: {pagina('Passatempos', 'Caça-palavras', corpo)}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"gerar": _go, "temas": _go}, player)
