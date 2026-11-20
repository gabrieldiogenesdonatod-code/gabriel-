"""Bingo (2.19): o JARVIS canta as pedras sem repetir, confere quem gritou bingo e gera as cartelas para imprimir."""
from __future__ import annotations

import random

from plugins._lote2 import P, carregar, guardar, num1, numeros, pagina, rodar

PLUGIN = P("bingo", "Bingo caller (75 balls): new game, draw without repeats ('B 12'), check a claimed bingo, drawn so far, printable cards.",
           "novo | sortear | conferir | sorteados | cartelas",
           "conferir: numeros (the winner's numbers). cartelas: quantidade (printable 5x5 cards).", "numeros quantidade")


def letra(n: int) -> str:
    return "BINGO"[(n - 1) // 15]


def cartela(rng=random) -> list[list]:
    cols = [rng.sample(range(i * 15 + 1, i * 15 + 16), 5) for i in range(5)]
    cols[2][2] = "★"
    return [[cols[c][l] for c in range(5)] for l in range(5)]


def _go(p, pl):
    a, e = p["action"], carregar("bingo", {"sorteados": []})
    s = e["sorteados"]
    if a == "novo":
        guardar("bingo", {"sorteados": []})
        return "Bingo novo! Diga 'sortear' para cantar a primeira pedra."
    if a == "sortear":
        resto = [n for n in range(1, 76) if n not in s]
        if not resto:
            return "Todas as 75 pedras já saíram."
        n = random.choice(resto)
        s.append(n)
        guardar("bingo", e)
        return f"{letra(n)} {n}! ({len(s)}ª pedra)"
    if a == "sorteados":
        return ", ".join(f"{letra(n)}{n}" for n in sorted(s)) or "Nenhuma pedra saiu ainda."
    if a == "conferir":
        nums = [int(x) for x in numeros(p.get("numeros"))]
        falta = [n for n in nums if n not in s]
        if not nums:
            return "Diga os números da cartela."
        return "BINGO válido! 🎉" if not falta else f"Ainda não: {', '.join(map(str, falta))} não saiu(saíram)."
    q = max(1, min(60, int(num1(p, "quantidade", 4))))
    html = "".join("<table style='display:inline-table;margin:10px'><tr>" + "".join(f"<th>{c}</th>" for c in "BINGO") + "</tr>" +
                   "".join("<tr>" + "".join(f"<td style='width:44px;height:44px;font-size:20px'>{x}</td>" for x in l) + "</tr>"
                           for l in cartela()) + "</table>" for _ in range(q))
    return f"{q} cartela(s) prontas para imprimir: {pagina('Bingo', 'Cartelas de bingo', html)}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("novo sortear conferir sorteados cartelas".split(), _go), player)
