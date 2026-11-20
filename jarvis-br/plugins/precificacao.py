"""Precificação da loja (2.18): preço pelo custo e margem, taxa da maquininha, margem real e ponto de equilíbrio."""
from __future__ import annotations

from plugins._lote2 import P, numeros, reais, rodar

PLUGIN = P("precificacao", "Store pricing: price from cost + target margin incl. card fee and taxes, real margin of a price, break-even.",
           "preco | margem | equilibrio | taxas",
           "preco: custo, margem (%), taxa (card fee %, default 0), imposto (% default 0; MEI often 0). margem: custo, preco, "
           "taxa, imposto. equilibrio: valor = fixed monthly costs, margem (%). taxas: preco -> net per payment type.",
           "custo margem preco taxa imposto valor")

TAXAS = {"débito": 1.6, "crédito à vista": 3.2, "crédito 3x": 6.0, "crédito 6x": 9.0, "pix": 0.0}   # médias aproximadas


def _x(p, k, d=0.0):
    n = numeros(p.get(k))
    return n[0] if n else d


def preco_ideal(custo, margem, taxa=0.0, imposto=0.0) -> float:
    """Preço para sobrar 'margem'% do preço depois de custo, taxa e imposto (markup divisor)."""
    div = 1 - (margem + taxa + imposto) / 100
    if div <= 0:
        raise ValueError("margem + taxas passam de 100%")
    return custo / div


def margem_real(custo, preco, taxa=0.0, imposto=0.0) -> float:
    return (preco * (1 - (taxa + imposto) / 100) - custo) / preco * 100


def _go(p, pl):
    a = str(p.get("action")).lower()
    c, m, t, i = _x(p, "custo"), _x(p, "margem", 50), _x(p, "taxa"), _x(p, "imposto")
    if a == "preco":
        pr = preco_ideal(c, m, t, i)
        return f"Venda por {reais(pr)} (sugestão redonda {reais(round(pr) - 0.10 if pr > 10 else pr)}); markup {pr / c:.2f}x."
    if a == "margem":
        pr = _x(p, "preco")
        mr = margem_real(c, pr, t, i)
        return f"Sobra {reais(pr * mr / 100)} por peça: margem real {mr:.1f}%."
    if a == "equilibrio":
        return f"Precisa vender {reais(_x(p, 'valor') / (m / 100))} por mês para empatar."
    pr = _x(p, "preco")
    return "Taxas médias (confira as da sua maquininha): " + "; ".join(
        f"{k} recebe {reais(pr * (1 - v / 100))}" for k, v in TAXAS.items()) + "."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("preco margem equilibrio taxas".split(), _go), player)
