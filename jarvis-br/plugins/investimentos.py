"""Investimentos (2.19): contas de renda fixa — CDB líquido de IR, LCI x CDB, juro real, aportes mensais e tempo para dobrar."""
from __future__ import annotations

import math

from plugins._lote2 import P, num1, reais, rodar

PLUGIN = P("investimentos", "Fixed-income math (Brazil): CDB net of income tax (regressive table), LCI vs CDB equivalence, real rate, monthly contributions, time to double.",
           "cdb_liquido | lci_vs_cdb | juro_real | aportes | dobrar",
           "Rates in % per year. cdb_liquido: valor, taxa, dias. lci_vs_cdb: taxa (LCI), dias -> CDB needed. juro_real: taxa, inflacao. "
           "aportes: valor (monthly), inicial, taxa, meses. dobrar: taxa. Calculations only, not advice.",
           "valor taxa dias inflacao inicial meses")


def ir_regressivo(dias: int) -> float:
    return 22.5 if dias <= 180 else 20.0 if dias <= 360 else 17.5 if dias <= 720 else 15.0


def cdb_liquido(valor: float, taxa_aa: float, dias: int) -> tuple[float, float, float]:
    bruto = valor * (1 + taxa_aa / 100) ** (dias / 365) - valor
    ir = bruto * ir_regressivo(dias) / 100
    return bruto, ir, bruto - ir


def futuro(aporte: float, inicial: float, taxa_aa: float, meses: int) -> float:
    i = (1 + taxa_aa / 100) ** (1 / 12) - 1
    return inicial * (1 + i) ** meses + (aporte * meses if i == 0 else aporte * ((1 + i) ** meses - 1) / i)


def _go(p, pl):
    a, v, t, dias = p["action"], num1(p, "valor"), num1(p, "taxa"), int(num1(p, "dias", 365))
    if a == "cdb_liquido":
        b, ir, liq = cdb_liquido(v, t, dias)
        return (f"Em {dias} dias rende {reais(b)} bruto, IR de {ir_regressivo(dias):g}% leva {reais(ir)}, sobra {reais(liq)} "
                f"({liq / v * 100:.2f}% líquido). Confira as regras de IR atuais.")
    if a == "lci_vs_cdb":
        return f"LCI/LCA de {t:g}% ao ano (isenta) equivale a um CDB de {t / (1 - ir_regressivo(dias) / 100):.2f}% ao ano em {dias} dias."
    if a == "juro_real":
        r = ((1 + t / 100) / (1 + num1(p, "inflacao") / 100) - 1) * 100
        return f"Juro real de {r:.2f}% ao ano (acima da inflação)."
    if a == "dobrar":
        if t <= 0:
            return "Qual a taxa ao ano?"
        return f"A {t:g}% ao ano o dinheiro dobra em {math.log(2) / math.log(1 + t / 100):.1f} anos."
    m = int(num1(p, "meses", 12))
    fv, posto = futuro(v, num1(p, "inicial"), t, m), num1(p, "inicial") + v * m
    return f"Em {m} meses você terá {reais(fv)} (colocou {reais(posto)}, rendeu {reais(fv - posto)}, antes do IR)."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("cdb_liquido lci_vs_cdb juro_real aportes dobrar".split(), _go), player)
