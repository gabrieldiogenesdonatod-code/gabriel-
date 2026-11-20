"""Cron (2.18): explica uma expressão cron em português e mostra as próximas execuções."""
from __future__ import annotations

from datetime import datetime, timedelta

from plugins._lote2 import P, rodar

PLUGIN = P("cron_explica", "Cron expressions: explain '*/15 9-18 * * 1-5' in Portuguese and list the next run times.",
           "explicar | proximas",
           "explicar/proximas: expressao (5 fields: min hour day month weekday). proximas: quantidade (default 5).",
           "expressao quantidade")

CAMPOS = [("minuto", 0, 59), ("hora", 0, 23), ("dia", 1, 31), ("mês", 1, 12), ("dia da semana", 0, 6)]
SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"]


def expandir(campo: str, lo: int, hi: int) -> set[int]:
    vals: set[int] = set()
    for parte in campo.split(","):
        base, _, passo = parte.partition("/")
        passo = int(passo or 1)
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            a, b = map(int, base.split("-"))
        else:
            a = b = int(base)
            if passo > 1:
                b = hi
        vals |= set(range(a, b + 1, passo))
    return {7 % 7 if v == 7 and hi == 6 else v for v in vals}


def explicar(expr: str) -> str:
    f = expr.split()
    if len(f) != 5:
        raise ValueError("preciso de 5 campos: minuto hora dia mês dia-da-semana")
    partes = []
    for (nome, lo, hi), c in zip(CAMPOS, f):
        if c == "*":
            continue
        if c.startswith("*/"):
            partes.append(f"a cada {c[2:]} {nome}(s)")
        else:
            v = sorted(expandir(c, lo, hi))
            txt = ", ".join(SEMANA[x] for x in v) if nome == "dia da semana" else ", ".join(map(str, v))
            partes.append(f"{nome} {txt}" if len(v) < 8 else f"{nome} de {v[0]} a {v[-1]}")
    return "Roda " + ("; ".join(partes) if partes else "todo minuto") + "."


def proximas(expr: str, n: int = 5, agora: datetime | None = None) -> list[datetime]:
    if len(expr.split()) != 5:
        raise ValueError("preciso de 5 campos: minuto hora dia mês dia-da-semana")
    sets = [expandir(c, lo, hi) for c, (_, lo, hi) in zip(expr.split(), CAMPOS)]
    t = (agora or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=1)
    out = []
    for _ in range(366 * 24 * 60):
        if t.minute in sets[0] and t.hour in sets[1] and t.day in sets[2] and t.month in sets[3] and \
                (t.weekday() + 1) % 7 in sets[4]:
            out.append(t)
            if len(out) >= n:
                break
        t += timedelta(minutes=1)
    return out


def run(parameters, player=None, session_memory=None):
    e = lambda p: str(p.get("expressao") or "").strip()  # noqa: E731
    return rodar(parameters, {
        "explicar": lambda p, pl: explicar(e(p)),
        "proximas": lambda p, pl: "\n".join(f"{d:%d/%m %H:%M} ({SEMANA[(d.weekday() + 1) % 7]})"
                                            for d in proximas(e(p), int(p.get("quantidade") or 5)))}, player, "Cron")
