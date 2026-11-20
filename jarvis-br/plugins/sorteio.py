"""Sorteios (2.18): nome, times equilibrados, amigo secreto, moeda, dados e número."""
from __future__ import annotations

import random

from plugins._lote2 import P, carregar, guardar, lista, norm, numeros, rodar

PLUGIN = P("sorteio", "Random draws: pick names, split teams, secret santa, coin flip, dice, random number.",
           "nome | times | amigo_secreto | quem_tirei | moeda | dados | numero",
           "Draws. nome/times/amigo_secreto: nomes (comma list), quantidade (winners or number of teams). "
           "quem_tirei: nomes = who is asking (told only to that person). dados: valor like '2d6'. numero: valor 'min max'.",
           "nomes quantidade valor")


def times(nomes: list[str], n: int, rng=random) -> list[list[str]]:
    nomes = nomes[:]
    rng.shuffle(nomes)
    return [nomes[i::n] for i in range(max(1, n))]


def amigo_secreto(nomes: list[str], rng=random) -> dict[str, str]:
    """Ciclo único embaralhado: ninguém tira a si mesmo."""
    if len(nomes) < 2:
        raise ValueError("precisa de pelo menos 2 pessoas")
    ordem = nomes[:]
    rng.shuffle(ordem)
    return {ordem[i]: ordem[(i + 1) % len(ordem)] for i in range(len(ordem))}


def _go(p, pl):
    a = str(p.get("action")).lower()
    nomes, q = lista(p.get("nomes")), int((numeros(p.get("quantidade")) or [1])[0])
    if a == "moeda":
        return random.choice(["Cara.", "Coroa."])
    if a == "dados":
        t = str(p.get("valor") or "1d6").lower()
        qtd, _, lados = t.partition("d")
        qtd, lados = int(qtd or 1), int(lados or 6)
        r = [random.randint(1, lados) for _ in range(min(qtd, 50))]
        return f"{r} = {sum(r)}."
    if a == "numero":
        n = numeros(p.get("valor")) or [1, 100]
        lo, hi = (int(n[0]), int(n[1])) if len(n) > 1 else (1, int(n[0]))
        return f"{random.randint(min(lo, hi), max(lo, hi))}."
    if a == "quem_tirei":
        par = carregar("amigo_secreto", {})
        eu = next((k for k in par if norm(k) == norm(p.get("nomes"))), None)
        return f"{eu}, você tirou {par[eu]}. Não conte para ninguém!" if eu else "Não achei esse nome no sorteio."
    if not nomes:
        return "Me diga os nomes."
    if a == "times":
        return "\n".join(f"Time {i + 1}: {', '.join(t)}" for i, t in enumerate(times(nomes, max(2, q))))
    if a == "amigo_secreto":
        guardar("amigo_secreto", amigo_secreto(nomes))
        return (f"Sorteio feito para {len(nomes)} pessoas e guardado em segredo. Cada um me pergunta em particular: "
                "'quem eu tirei?' e diz o próprio nome.")
    return "Sorteado(s): " + ", ".join(random.sample(nomes, min(q, len(nomes)))) + "."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("nome times amigo_secreto quem_tirei moeda dados numero".split(), _go), player, "Sorteio")
