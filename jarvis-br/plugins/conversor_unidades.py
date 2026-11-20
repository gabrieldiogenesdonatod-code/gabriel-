"""Conversor de unidades (2.18): comprimento, massa, volume, área, velocidade, dados, tempo, temperatura e cozinha.

Exemplos: converter libras em quilos, polegadas em centímetros, xícaras em ml, Fahrenheit em Celsius,
milhas em quilômetros, GB em MB, psi em bar, km/l em l/100 km.
"""
from __future__ import annotations

from plugins._lote2 import P, norm, numeros, rodar

PLUGIN = P("conversor_unidades", "Unit converter: length, mass, volume, cooking cups/spoons, temperature, speed, data, time, pressure, energy, power, km/l to l/100km.",
           "converter | unidades",
           "Converts units. converter: valor (number), de, para (e.g. 3 xicara -> ml, 100 f -> c, 5 gb -> mb).",
           "valor de para")

U = {  # unidade: (grupo, fator para a base)
    "mm": ("comp", .001), "cm": ("comp", .01), "m": ("comp", 1), "km": ("comp", 1000), "pol": ("comp", .0254),
    "polegada": ("comp", .0254), "pe": ("comp", .3048), "jarda": ("comp", .9144), "milha": ("comp", 1609.344),
    "mg": ("massa", .001), "g": ("massa", 1), "kg": ("massa", 1000), "t": ("massa", 1e6), "lb": ("massa", 453.592),
    "libra": ("massa", 453.592), "oz": ("massa", 28.3495), "arroba": ("massa", 15000),
    "ml": ("vol", 1), "l": ("vol", 1000), "litro": ("vol", 1000), "m3": ("vol", 1e6), "xicara": ("vol", 240),
    "colher": ("vol", 15), "colher_sopa": ("vol", 15), "colher_cha": ("vol", 5), "copo": ("vol", 200),
    "galao": ("vol", 3785.41),
    "m2": ("area", 1), "km2": ("area", 1e6), "hectare": ("area", 1e4), "ha": ("area", 1e4), "alqueire": ("area", 48400),
    "m/s": ("vel", 1), "km/h": ("vel", 1 / 3.6), "mph": ("vel", .44704), "no": ("vel", .514444),
    "b": ("dados", 1), "kb": ("dados", 1024), "mb": ("dados", 1024 ** 2), "gb": ("dados", 1024 ** 3), "tb": ("dados", 1024 ** 4),
    "s": ("tempo", 1), "min": ("tempo", 60), "h": ("tempo", 3600), "dia": ("tempo", 86400), "semana": ("tempo", 604800),
    "pa": ("pressao", 1), "kpa": ("pressao", 1e3), "bar": ("pressao", 1e5), "psi": ("pressao", 6894.757), "atm": ("pressao", 101325),
    "j": ("energia", 1), "kj": ("energia", 1e3), "cal": ("energia", 4.184), "kcal": ("energia", 4184), "wh": ("energia", 3600),
    "kwh": ("energia", 3.6e6), "w": ("potencia", 1), "kw": ("potencia", 1e3), "cv": ("potencia", 735.499), "hp": ("potencia", 745.7),
    "c": ("temp", 0), "f": ("temp", 0), "k": ("temp", 0),
}
APELIDO = {"metro": "m", "metros": "m", "centimetro": "cm", "quilometro": "km", "grama": "g", "gramas": "g",
           "quilo": "kg", "quilos": "kg", "kilo": "kg", "litros": "l", "mililitro": "ml", "xicaras": "xicara",
           "celsius": "c", "fahrenheit": "f", "kelvin": "k", "segundo": "s", "minuto": "min", "minutos": "min",
           "hora": "h", "horas": "h", "dias": "dia", "pes": "pe", "polegadas": "pol", "milhas": "milha"}


def _u(t):
    t = norm(t).replace(" de ", "_").replace(" ", "_").rstrip(".")
    return APELIDO.get(t, t)


def converter(v: float, de: str, para: str) -> float:
    a, b = _u(de), _u(para)
    if {a, b} == {"km/l", "l/100km"}:                       # consumo: um é o inverso do outro
        return 100 / v
    if a not in U or b not in U or U[a][0] != U[b][0]:
        raise ValueError(f"não converto {de} para {para}")
    if U[a][0] == "temp":
        c = {"c": v, "f": (v - 32) * 5 / 9, "k": v - 273.15}[a]
        return {"c": c, "f": c * 9 / 5 + 32, "k": c + 273.15}[b]
    return v * U[a][1] / U[b][1]


def _conv(p, pl):
    v = (numeros(p.get("valor")) or [1])[0]
    r = converter(v, p.get("de"), p.get("para"))
    return f"{v:g} {p.get('de')} = {round(r, 4):g} {p.get('para')}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"converter": _conv, "unidades": lambda p, pl: "Unidades: " + ", ".join(U) + "."}, player)
