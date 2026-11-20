"""Álgebra (2.19): Bhaskara, MDC e MMC, fatoração em primos, frações, PA e PG, combinações e sistema de duas equações."""
from __future__ import annotations

import math
import re
from fractions import Fraction

from plugins._lote2 import P, numeros, rodar

PLUGIN = P("algebra", "School algebra: quadratic roots (Bhaskara), GCD/LCM, prime factorization, fraction arithmetic, arithmetic/geometric progressions, combinations, 2x2 linear system.",
           "bhaskara | mdc_mmc | fatorar | fracao | pa | pg | combinatoria | sistema",
           "valor = numbers. bhaskara: 'a b c'. fracao: texto like '3/4 + 2/5'. pa/pg: 'first ratio n'. combinatoria: 'n k'. "
           "sistema: 'a b c d e f' for ax+by=c, dx+ey=f.",
           "valor texto")


def bhaskara(a, b, c) -> tuple[float, list[float]]:
    delta = b * b - 4 * a * c
    if delta < 0:
        return delta, []
    r = sorted({(-b - math.sqrt(delta)) / (2 * a), (-b + math.sqrt(delta)) / (2 * a)})
    return delta, r


def fatores(n: int) -> list[int]:
    out, d = [], 2
    while d * d <= n:
        while n % d == 0:
            out.append(d)
            n //= d
        d += 1
    return out + ([n] if n > 1 else [])


def fracao(texto: str) -> Fraction:
    m = re.fullmatch(r"\s*(-?\d+)\s*/\s*(\d+)\s*(?:([+\-*x×:÷])\s*(-?\d+)\s*/\s*(\d+))?\s*", texto)
    if not m:
        raise ValueError("use '3/4 + 2/5' ou '18/24'")
    x = Fraction(int(m.group(1)), int(m.group(2)))
    if not m.group(3):
        return x
    y, op = Fraction(int(m.group(4)), int(m.group(5))), m.group(3)
    return x + y if op == "+" else x - y if op == "-" else x * y if op in "*x×" else x / y


def g(v: float) -> str:
    return f"{v:.4g}".replace(".", ",")


def _go(p, pl):
    a, n = p["action"], numeros(p.get("valor") or p.get("texto"))
    if a == "fracao":
        f = fracao(str(p.get("texto") or p.get("valor") or ""))
        return f"{f.numerator}/{f.denominator}" + (f" (= {g(float(f))})" if f.denominator != 1 else "")
    if a == "bhaskara":
        d, r = bhaskara(*n[:3])
        return f"Delta = {g(d)}. " + ("Sem raízes reais." if not r else "Raízes: " + " e ".join(g(x) for x in r) + ".")
    ints = [int(x) for x in n]
    if a == "mdc_mmc":
        return f"MDC {math.gcd(*ints)}, MMC {math.lcm(*ints)}."
    if a == "fatorar":
        f = fatores(ints[0])
        return f"{ints[0]} é primo." if len(f) == 1 else f"{ints[0]} = " + " × ".join(map(str, f))
    if a in ("pa", "pg"):
        a1, r, k = n[0], n[1], int(n[2])
        an = a1 + (k - 1) * r if a == "pa" else a1 * r ** (k - 1)
        sn = (a1 + an) * k / 2 if a == "pa" else (a1 * k if r == 1 else a1 * (r ** k - 1) / (r - 1))
        return f"Termo {k} = {g(an)}; soma dos {k} primeiros = {g(sn)}."
    if a == "combinatoria":
        nn, k = ints[0], ints[1] if len(ints) > 1 else 0
        return f"Combinações C({nn},{k}) = {math.comb(nn, k)}; arranjos A({nn},{k}) = {math.perm(nn, k)}; {nn}! = {math.factorial(nn)}."
    a1, b1, c1, a2, b2, c2 = n[:6]
    det = a1 * b2 - a2 * b1
    return "Sistema sem solução única." if det == 0 else f"x = {g((c1 * b2 - c2 * b1) / det)}, y = {g((a1 * c2 - a2 * c1) / det)}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("bhaskara mdc_mmc fatorar fracao pa pg combinatoria sistema".split(), _go), player)
