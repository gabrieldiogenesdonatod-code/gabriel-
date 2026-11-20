"""Geometria (2.19): área e volume das formas, círculo, Pitágoras, triângulo pelos três lados e graus ↔ radianos."""
from __future__ import annotations

import math

from plugins._lote2 import P, norm, numeros, rodar

PLUGIN = P("geometria", "Geometry: area and volume of shapes, circle, Pythagoras, triangle from 3 sides (area, angles, type), degrees/radians.",
           "area | volume | circulo | pitagoras | triangulo | graus_rad",
           "valor = numbers in order. area: forma (retangulo a b | triangulo base altura | circulo r | trapezio B b h | losango D d). "
           "volume: forma (cubo a | caixa a b c | cilindro r h | esfera r | cone r h). pitagoras: 'cateto cateto' or forma=cateto 'hipotenusa cateto'. "
           "graus_rad: valor, forma (graus|rad = unit of the input).",
           "forma valor")

AREA = {"ret": lambda a, b=None: a * (b if b is not None else a), "qua": lambda a: a * a, "tri": lambda b, h: b * h / 2,
        "cir": lambda r: math.pi * r * r, "tra": lambda B, b, h: (B + b) * h / 2, "los": lambda D, d: D * d / 2}
VOLUME = {"cub": lambda a: a ** 3, "cai": lambda a, b, c: a * b * c, "par": lambda a, b, c: a * b * c,
          "cil": lambda r, h: math.pi * r * r * h, "esf": lambda r: 4 / 3 * math.pi * r ** 3, "con": lambda r, h: math.pi * r * r * h / 3}


def triangulo(a, b, c) -> dict:
    if a + b <= c or a + c <= b or b + c <= a:
        raise ValueError("esses lados não fecham um triângulo")
    s = (a + b + c) / 2
    ang = [math.degrees(math.acos((y * y + z * z - x * x) / (2 * y * z))) for x, y, z in ((a, b, c), (b, a, c), (c, a, b))]
    tipo = "equilátero" if a == b == c else "isósceles" if len({a, b, c}) == 2 else "escaleno"
    return {"perimetro": 2 * s, "area": math.sqrt(s * (s - a) * (s - b) * (s - c)), "angulos": ang,
            "tipo": tipo + (" retângulo" if any(abs(x - 90) < 1e-6 for x in ang) else "")}


def g(v: float) -> str:
    return f"{v:.4g}".replace(".", ",")


def _go(p, pl):
    a, n, f = p["action"], numeros(p.get("valor")), norm(p.get("forma"))[:3]
    if not n:
        return "Quais são as medidas?"
    if a in ("area", "volume"):
        tab = AREA if a == "area" else VOLUME
        if f not in tab:
            return "Formas: " + ("retângulo, quadrado, triângulo, círculo, trapézio, losango." if a == "area"
                                 else "cubo, caixa, cilindro, esfera, cone.")
        return f"{'Área' if a == 'area' else 'Volume'} = {g(tab[f](*n[:tab[f].__code__.co_argcount]))}."
    if a == "circulo":
        return f"Raio {g(n[0])}: diâmetro {g(2 * n[0])}, circunferência {g(2 * math.pi * n[0])}, área {g(math.pi * n[0] ** 2)}."
    if a == "pitagoras":
        if f == "cat":
            return f"Cateto = {g(math.sqrt(max(n) ** 2 - min(n) ** 2))}."
        return f"Hipotenusa = {g(math.hypot(n[0], n[1]))}."
    if a == "triangulo":
        t = triangulo(*n[:3])
        return f"Triângulo {t['tipo']}: perímetro {g(t['perimetro'])}, área {g(t['area'])}, ângulos " + ", ".join(f"{x:.1f}°" for x in t["angulos"]) + "."
    return f"{g(n[0])} rad = {g(math.degrees(n[0]))}°." if f == "rad" else f"{g(n[0])}° = {g(math.radians(n[0]))} rad."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("area volume circulo pitagoras triangulo graus_rad".split(), _go), player)
