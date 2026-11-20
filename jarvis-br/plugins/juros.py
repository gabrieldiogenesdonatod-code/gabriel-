"""Juros e parcelas (2.18): simples, composto, parcela fixa (Price), quanto falta para juntar e à vista x parcelado."""
from __future__ import annotations

from plugins._lote2 import P, numeros, reais, rodar

PLUGIN = P("juros", "Interest math: simple/compound, installment (Price), cash vs installments, monthly saving needed.",
           "composto | simples | parcela | sac | avista_ou_parcelado | quanto_guardar",
           "Finance math. valor=principal, taxa=% per month, meses. avista_ou_parcelado: valor=cash price, parcela, meses, "
           "taxa=what money earns per month. quanto_guardar: valor=goal, meses, taxa. sac: valor, taxa, meses (SAC vs Price).",
           "valor taxa meses parcela")


def composto(c, i, n):
    return c * (1 + i) ** n


def parcela_price(pv, i, n):
    return pv / n if i == 0 else pv * i / (1 - (1 + i) ** -n)


def valor_presente_parcelas(pmt, i, n):
    return pmt * n if i == 0 else pmt * (1 - (1 + i) ** -n) / i


def aporte_mensal(meta, i, n):
    return meta / n if i == 0 else meta * i / ((1 + i) ** n - 1)


def sac(pv, i, n) -> tuple[float, float, float]:
    """(primeira parcela, última parcela, juros totais) na amortização constante."""
    am = pv / n
    return am + pv * i, am + am * i, i * pv * (n + 1) / 2


def _x(p, k, d=0.0):
    n = numeros(p.get(k))
    return n[0] if n else d


def _go(p, pl):
    a = str(p.get("action")).lower()
    c, i, n = _x(p, "valor"), _x(p, "taxa") / 100, int(_x(p, "meses", 1))
    if a == "composto":
        m = composto(c, i, n)
        return f"{reais(c)} a {i*100:g}% ao mês por {n} meses vira {reais(m)} (juros {reais(m - c)})."
    if a == "simples":
        return f"Juros simples: {reais(c * i * n)}; total {reais(c * (1 + i * n))}."
    if a == "parcela":
        pm = parcela_price(c, i, n)
        return f"{n}x de {reais(pm)} (total {reais(pm * n)}, juros {reais(pm * n - c)})."
    if a == "quanto_guardar":
        return f"Guarde {reais(aporte_mensal(c, i, n))} por mês por {n} meses para chegar a {reais(c)}."
    if a == "sac":
        pri, ult, js = sac(c, i, n)
        price = parcela_price(c, i, n) * n - c
        return (f"SAC em {n}x: começa em {reais(pri)} e termina em {reais(ult)}, juros de {reais(js)}. "
                f"Na Price a parcela fixa seria {reais(parcela_price(c, i, n))}, com {reais(price)} de juros ({reais(price - js)} a mais).")
    pmt = _x(p, "parcela")
    vp = valor_presente_parcelas(pmt, i, n)
    melhor = "parcelado" if vp < c else "à vista"
    return f"As {n} parcelas de {reais(pmt)} valem hoje {reais(vp)} contra {reais(c)} à vista: compensa {melhor}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys(("composto", "simples", "parcela", "sac", "avista_ou_parcelado", "quanto_guardar"), _go), player)
