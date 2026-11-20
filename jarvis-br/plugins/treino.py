"""Treino (2.18): anota séries, recordes por exercício, volume da semana e sugere carga (progressão)."""
from __future__ import annotations

import time

from plugins import _lote2
from plugins._lote2 import P, gravar_json, hoje, ler_json, norm, numeros, rodar

PLUGIN = P("treino", "Workout log: sets x reps x kg, personal records, weekly volume, next-load suggestion, estimated 1RM.",
           "anotar | recordes | semana | proxima | 1rm",
           "anotar: exercicio, valor ('4x10 40kg'). recordes. semana. proxima: exercicio -> load suggestion. "
           "1rm: valor ('100kg 5 reps', Epley).",
           "exercicio valor")


def _arq():
    return _lote2.PASTA / "treino.json"


def ler_serie(t: str) -> tuple[int, int, float]:
    n = numeros(str(t).lower().replace("x", " "))
    if len(n) >= 3:
        return int(n[0]), int(n[1]), n[2]
    if len(n) == 2:
        return 1, int(n[0]), n[1]
    raise ValueError("use '4x10 40kg'")


def um_rm(kg: float, reps: int) -> float:
    return kg * (1 + reps / 30)


def _go(p, pl):
    a, log = str(p.get("action")).lower(), ler_json(_arq(), []) or []
    ex = norm(p.get("exercicio"))
    if a == "1rm":
        n = numeros(p.get("valor"))
        return f"1RM estimado: {um_rm(n[0], int(n[1])):.1f} kg." if len(n) > 1 else "Diga carga e repetições."
    if a == "anotar":
        s, r, kg = ler_serie(p.get("valor"))
        log.append({"d": hoje(), "ex": ex, "s": s, "r": r, "kg": kg})
        gravar_json(_arq(), log[-3000:])
        pr = max((x["kg"] for x in log if x["ex"] == ex), default=kg)
        return f"Anotado {ex}: {s}x{r} {kg:g} kg." + (" Novo recorde!" if kg >= pr and len(log) > 1 else "")
    if a == "recordes":
        prs: dict = {}
        for x in log:
            prs[x["ex"]] = max(prs.get(x["ex"], 0), x["kg"])
        return "; ".join(f"{k}: {v:g} kg" for k, v in prs.items()) or "Nada anotado."
    if a == "semana":
        lim = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
        vol = sum(x["s"] * x["r"] * x["kg"] for x in log if x["d"] >= lim)
        dias = len({x["d"] for x in log if x["d"] >= lim})
        return f"Últimos 7 dias: {dias} treino(s), volume {vol:,.0f} kg.".replace(",", ".")
    ult = [x for x in log if x["ex"] == ex]
    if not ult:
        return "Sem histórico desse exercício."
    u = ult[-1]
    sug = u["kg"] * 1.025 if u["r"] >= 10 else u["kg"]
    return f"Último: {u['s']}x{u['r']} {u['kg']:g} kg. Sugestão: {sug:.1f} kg" + ("." if sug > u["kg"] else ", busque mais repetições.")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("anotar recordes semana proxima 1rm".split(), _go), player)
