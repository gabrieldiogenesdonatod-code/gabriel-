"""Notas da escola (2.19): média ponderada, quanto precisa tirar na prova que falta e quantas faltas ainda pode ter."""
from __future__ import annotations

import math

from plugins._lote2 import P, num1, numeros, rodar

PLUGIN = P("notas_escola", "School grades: weighted average, grade needed on the remaining exam to pass, absences allowed (75% attendance rule).",
           "media | preciso | faltas",
           "media: notas ('7 8,5 6'), pesos (optional). preciso: notas, pesos (of those), peso_final, alvo (default 6). "
           "faltas: aulas (total classes), faltei.",
           "notas pesos peso_final alvo aulas faltei")


def media(notas: list[float], pesos: list[float] | None = None) -> float:
    pesos = pesos if pesos and len(pesos) == len(notas) else [1] * len(notas)
    return sum(n * w for n, w in zip(notas, pesos)) / sum(pesos)


def preciso(notas, pesos, peso_final, alvo=6.0) -> float:
    pesos = pesos if pesos and len(pesos) == len(notas) else [1] * len(notas)
    return (alvo * (sum(pesos) + peso_final) - sum(n * w for n, w in zip(notas, pesos))) / peso_final


def faltas_permitidas(aulas: int) -> int:
    return math.floor(aulas * 0.25)


def _go(p, pl):
    a, notas, pesos = p["action"], numeros(p.get("notas")), numeros(p.get("pesos"))
    if a == "faltas":
        aulas, f = int(num1(p, "aulas")), int(num1(p, "faltei"))
        lim = faltas_permitidas(aulas)
        return f"Em {aulas} aulas o limite é {lim} falta(s) (25%). Você tem {f}: " + (f"ainda pode faltar {lim - f}." if f <= lim else "já passou do limite.")
    if not notas:
        return "Quais são as notas?"
    if a == "media":
        return f"Média {media(notas, pesos):.2f}".replace(".", ",") + "."
    alvo = num1(p, "alvo", 6)
    n = preciso(notas, pesos, num1(p, "peso_final", 1), alvo)
    if n <= 0:
        return f"Já passou: mesmo com zero a média fica acima de {alvo:g}."
    return f"Precisa tirar {n:.1f} para fechar com média {alvo:g}.".replace(".", ",", 1) if n <= 10 else \
        f"Precisaria de {n:.1f}, acima de 10: não dá só com essa prova."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"media": _go, "preciso": _go, "faltas": _go}, player)
