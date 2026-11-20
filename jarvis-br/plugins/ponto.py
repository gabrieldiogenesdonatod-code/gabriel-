"""Ponto (2.19): bate entrada e saída, soma as horas do dia e do mês e guarda o banco de horas contra a sua jornada."""
from __future__ import annotations

import time
from datetime import date

from plugins._lote2 import P, carregar, guardar, hoje, num1, rodar

PLUGIN = P("ponto", "Work time clock: punch in/out, hours today, month total, overtime bank vs daily workday, set workday hours.",
           "bater | hoje | mes | banco | jornada",
           "bater: hora (HH:MM, default now). jornada: valor (hours per day, default 8). mes: mes (aaaa-mm).",
           "hora valor mes")


def horas(batidas: list[str], agora: str | None = None) -> float:
    """Soma dos pares entrada/saída em horas; batida ímpar conta até 'agora'. Pura."""
    def h(t):
        a, b = t.split(":")
        return int(a) + int(b) / 60
    b = list(batidas) + ([agora] if len(batidas) % 2 and agora else [])
    return sum(h(b[i + 1]) - h(b[i]) for i in range(0, len(b) - 1, 2))


def hm(x: float) -> str:
    s = "-" if x < 0 else ""
    m = round(abs(x) * 60)
    return f"{s}{m // 60}h{m % 60:02d}"


def banco(dias: dict, jornada: float) -> float:
    return sum(horas(b) - jornada for d, b in dias.items() if len(b) >= 2 and len(b) % 2 == 0 and d != hoje())


def _go(p, pl):
    a, d = p["action"], carregar("ponto", {"jornada": 8, "dias": {}})
    agora = time.strftime("%H:%M")
    if a == "jornada":
        d["jornada"] = num1(p, "valor", 8)
        guardar("ponto", d)
        return f"Jornada de {d['jornada']:g} horas por dia."
    if a == "bater":
        hora = str(p.get("hora") or agora).strip()[:5]
        bat = d["dias"].setdefault(hoje(), [])
        bat.append(hora)
        guardar("ponto", d)
        return (f"Entrada às {hora}." if len(bat) % 2 else f"Saída às {hora}. Hoje: {hm(horas(bat))}.")
    if a == "hoje":
        bat = d["dias"].get(hoje(), [])
        if not bat:
            return "Ainda não bateu o ponto hoje."
        feito = horas(bat, agora)
        return f"Batidas: {', '.join(bat)}. Trabalhou {hm(feito)}; " + (f"faltam {hm(d['jornada'] - feito)}." if feito < d["jornada"]
                                                                       else f"passou {hm(feito - d['jornada'])} da jornada.")
    if a == "banco":
        return f"Banco de horas: {hm(banco(d['dias'], d['jornada']))}."
    mes = str(p.get("mes") or date.today().strftime("%Y-%m"))
    doMes = {k: v for k, v in d["dias"].items() if k.startswith(mes)}
    return f"{mes}: {len(doMes)} dia(s), {hm(sum(horas(b) for b in doMes.values() if len(b) % 2 == 0))} trabalhadas." if doMes else "Sem registros nesse mês."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("bater hoje mes banco jornada".split(), _go), player)
