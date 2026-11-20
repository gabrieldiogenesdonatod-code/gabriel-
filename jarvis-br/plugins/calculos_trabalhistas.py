"""Cálculos trabalhistas (2.19): 13º, férias, hora extra e rescisão — valores BRUTOS, só para ter uma ideia antes do holerite."""
from __future__ import annotations

from plugins._lote2 import P, norm, num1, reais, rodar

PLUGIN = P("calculos_trabalhistas", "CLT estimates (gross, before INSS/IRRF): 13th salary, vacation + 1/3, overtime value, termination estimate.",
           "decimo_terceiro | ferias | hora_extra | rescisao",
           "salario always. decimo_terceiro/ferias: meses worked. ferias: vender (days sold, 0-10). hora_extra: horas, adicional (% default 50). "
           "rescisao: dias (worked this month), meses (this year), anos (at the company), tipo (demitido|pedido). Estimates only.",
           "salario meses vender horas adicional dias anos tipo")

AVISO = " Valores brutos e aproximados; confira com o RH ou contador."


def decimo(salario, meses) -> float:
    return salario * min(12, meses) / 12


def ferias(salario, meses=12, vender=0) -> tuple[float, float]:
    base = salario * min(12, meses) / 12
    abono = salario / 30 * vender * 4 / 3
    return base * 4 / 3, abono


def hora_extra(salario, horas, adicional=50, divisor=220) -> float:
    return salario / divisor * (1 + adicional / 100) * horas


def rescisao(salario, dias, meses, anos, demitido=True) -> dict:
    v = {"saldo de salário": salario / 30 * dias, "13º proporcional": decimo(salario, meses),
         "férias proporcionais + 1/3": ferias(salario, meses)[0]}
    if demitido:
        v["aviso prévio indenizado"] = salario / 30 * min(90, 30 + 3 * int(anos))
        v["multa de 40% do FGTS (estimada)"] = salario * 0.08 * (anos * 12 + meses) * 0.4
    return v


def _go(p, pl):
    a, s = p["action"], num1(p, "salario")
    if not s:
        return "Qual o salário bruto?"
    if a == "decimo_terceiro":
        return f"13º de {reais(decimo(s, num1(p, 'meses', 12)))}, pago em duas parcelas." + AVISO
    if a == "ferias":
        f, ab = ferias(s, num1(p, "meses", 12), num1(p, "vender"))
        return f"Férias com 1/3: {reais(f)}" + (f", mais {reais(ab)} pelos dias vendidos" if ab else "") + "." + AVISO
    if a == "hora_extra":
        h = num1(p, "horas", 1)
        return f"{h:g} hora(s) extra(s) a {num1(p, 'adicional', 50):g}% valem {reais(hora_extra(s, h, num1(p, 'adicional', 50)))}." + AVISO
    v = rescisao(s, num1(p, "dias", 30), num1(p, "meses", 12), num1(p, "anos", 1), "pedi" not in norm(p.get("tipo")))
    return "\n".join(f"{k}: {reais(x)}" for k, x in v.items()) + f"\nTotal estimado: {reais(sum(v.values()))}." + AVISO


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("decimo_terceiro ferias hora_extra rescisao".split(), _go), player, "Trabalhista")
