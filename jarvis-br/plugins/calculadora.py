"""Calculadora por voz (2.18): conta, porcentagem, regra de três e estatística. Sem eval: só aritmética."""
from __future__ import annotations

import ast
import math
import operator as op
import statistics as st

from plugins._lote2 import P, numeros, rodar

PLUGIN = P("calculadora", "Safe calculator: expressions, percent, rule of three, mean/median/stdev of numbers.",
           "conta | porcentagem | regra_de_tres | estatistica",
           "Math. conta: expressao ('2^10 + raiz(16)'). porcentagem: valor + texto ('15% de 200', 'de 80 para 100'). "
           "regra_de_tres: valor 'a b c' (a está para b como c está para x). estatistica: valor = list of numbers.",
           "expressao valor")

_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow,
        ast.Mod: op.mod, ast.FloorDiv: op.floordiv, ast.USub: op.neg, ast.UAdd: op.pos}
_FUN = {"raiz": math.sqrt, "sqrt": math.sqrt, "sen": math.sin, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log10, "ln": math.log, "abs": abs, "round": round, "fat": math.factorial}
_CON = {"pi": math.pi, "e": math.e}


def calcular(expr: str) -> float:
    t = str(expr).lower().replace("^", "**").replace("x", "*").replace("÷", "/").replace(",", ".")
    t = t.replace("vezes", "*").replace("mais", "+").replace("menos", "-").replace("dividido por", "/")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 1000:
                raise ValueError("expoente grande demais")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUN:
            return _FUN[n.func.id](*[ev(a) for a in n.args])
        if isinstance(n, ast.Name) and n.id in _CON:
            return _CON[n.id]
        raise ValueError("só aceito números, + - * / ^ % e raiz/sen/cos/log")
    return ev(ast.parse(t, mode="eval"))


def fmt(v: float) -> str:
    v = round(v, 6)
    return str(int(v)) if float(v).is_integer() else f"{v:.6g}".replace(".", ",")


def porcentagem(texto: str) -> str:
    n, t = numeros(texto), str(texto).lower()
    if len(n) < 2:
        return "Diga dois números, ex.: '15% de 200' ou 'de 80 para 100'."
    a, b = n[0], n[1]
    if "para" in t:
        return f"Variação de {fmt((b - a) / a * 100)}%."
    if "%" in t or " de " in t:
        return f"{fmt(a)}% de {fmt(b)} = {fmt(a * b / 100)}."
    return f"{fmt(a)} é {fmt(a / b * 100)}% de {fmt(b)}."


def regra3(a, b, c) -> float:
    return b * c / a


def estatistica(vals: list[float]) -> dict:
    return {"n": len(vals), "soma": sum(vals), "media": st.mean(vals), "mediana": st.median(vals),
            "min": min(vals), "max": max(vals), "desvio": st.pstdev(vals) if len(vals) > 1 else 0.0}


def _conta(p, pl):
    e = p.get("expressao") or p.get("valor")
    return f"{e} = {fmt(calcular(e))}"


def _r3(p, pl):
    n = numeros(p.get("valor") or p.get("expressao"))
    return f"x = {fmt(regra3(*n[:3]))}" if len(n) >= 3 else "Preciso de três números: a, b e c."


def _est(p, pl):
    v = numeros(p.get("valor") or p.get("expressao"))
    if not v:
        return "Me diga os números."
    s = estatistica(v)
    return ", ".join(f"{k} {fmt(x)}" for k, x in s.items()) + "."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"conta": _conta, "porcentagem": lambda p, pl: porcentagem(p.get("valor") or p.get("expressao")),
                              "regra_de_tres": _r3, "estatistica": _est}, player, "Calculadora")
