"""Calculadora de obra (2.19): quanto comprar de tinta, piso, tijolo e concreto para uma reforma, já com a perda."""
from __future__ import annotations

import math

from plugins._lote2 import P, num1, numeros, rodar

PLUGIN = P("calculadora_obra", "Renovation material calculator: paint litres/cans, floor tiles and boxes, bricks, concrete (cement bags, sand, gravel), with waste margin.",
           "tinta | piso | tijolos | concreto",
           "area in m² (or largura x comprimento in m; walls: comprimento x altura). tinta: demaos (2), rendimento (m² per litre, 10). "
           "piso: peca ('60x60' cm), caixa (m² per box), perda (%). tijolos: peca ('19x19' face cm). concreto: espessura (cm).",
           "area largura comprimento altura demaos rendimento peca caixa perda espessura")


def area(p) -> float:
    """m² direto, ou comprimento x largura (piso) / comprimento x altura (parede)."""
    return num1(p, "area") or num1(p, "comprimento") * (num1(p, "largura") or num1(p, "altura"))


def latas(litros: float) -> str:
    """Combinação de latas de 18 L, 3,6 L e 0,9 L que cobre a quantidade. Pura."""
    g, resto = divmod(litros, 18)
    m = math.ceil(resto / 3.6) if resto > 0.9 else 0
    q = 1 if 0 < resto <= 0.9 else 0
    if m >= 5:
        g, m = g + 1, 0
    partes = [f"{int(n)} de {t}" for n, t in ((g, "18 L"), (m, "3,6 L"), (q, "0,9 L")) if n]
    return " + ".join(partes) or "1 de 0,9 L"


def pecas(m2: float, a_cm: float, b_cm: float, perda: float = 10, junta_cm: float = 0) -> int:
    return math.ceil(m2 * (1 + perda / 100) / (((a_cm + junta_cm) / 100) * ((b_cm + junta_cm) / 100)))


def _go(p, pl):
    a, m2 = p["action"], area(p)
    if not m2:
        return "Qual a área em metros quadrados (ou largura e comprimento)?"
    if a == "tinta":
        litros = m2 * num1(p, "demaos", 2) / num1(p, "rendimento", 10)
        return f"{m2:g} m² em {num1(p, 'demaos', 2):g} demãos: {litros:.1f} litros. Compre {latas(litros)}."
    lados = numeros(p.get("peca"))
    perda = num1(p, "perda", 10)
    if a == "piso":
        la, lb = (lados + [60, 60])[:2] if len(lados) >= 2 else (60, 60)
        n, total = pecas(m2, la, lb, perda), m2 * (1 + perda / 100)
        cx = num1(p, "caixa")
        return f"{total:.1f} m² com {perda:g}% de perda: {n} peças de {la:g}x{lb:g}" + (f", {math.ceil(total / cx)} caixa(s)." if cx else ".")
    if a == "tijolos":
        la, lb = (lados + [19, 19])[:2] if len(lados) >= 2 else (19, 19)
        return f"{pecas(m2, la, lb, perda, 1)} tijolos de {la:g}x{lb:g} para {m2:g} m² de parede (junta de 1 cm, {perda:g}% de perda)."
    vol = m2 * num1(p, "espessura", 10) / 100
    return (f"{vol:.2f} m³ de concreto (traço 1:2:3): cerca de {math.ceil(vol * 7)} sacos de cimento de 50 kg, "
            f"{vol * 0.56:.2f} m³ de areia e {vol * 0.84:.2f} m³ de brita. Estimativa; confirme com o pedreiro.")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("tinta piso tijolos concreto".split(), _go), player)
