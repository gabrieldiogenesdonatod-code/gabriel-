"""Corrida (2.19): anota corridas e caminhadas, calcula o ritmo, soma a semana, guarda recordes e prevê tempo em outra distância."""
from __future__ import annotations

import time

from plugins._lote2 import P, carregar, guardar, hoje, num1, numeros, rodar

PLUGIN = P("corrida", "Running/walking log: pace, weekly km, records, race time prediction (Riegel), heart-rate zones by age, speed-pace conversion.",
           "registrar | ritmo | semana | recordes | prever | zonas",
           "registrar/ritmo: km, tempo ('28:30' or '1:02:10' or '45 min'). prever: km (target distance). zonas: idade.",
           "km tempo idade")


def minutos(t) -> float:
    """'28:30' → 28.5; '1:02:10' → 62.17; '45 min' → 45. Pura."""
    t = str(t or "")
    if ":" in t:
        partes = [float(x) for x in t.split(":")[:3]]
        return partes[0] * 60 + partes[1] + partes[2] / 60 if len(partes) == 3 else partes[0] + partes[1] / 60
    n = numeros(t)
    if not n:
        return 0.0
    if "h" in t.lower():
        return n[0] * 60 + (n[1] if len(n) > 1 else 0)
    return n[0]


def ritmo(km: float, mins: float) -> str:
    p = mins / km
    return f"{int(p)}:{round((p - int(p)) * 60):02d}/km"


def riegel(mins: float, km: float, alvo_km: float) -> float:
    return mins * (alvo_km / km) ** 1.06


def hms(mins: float) -> str:
    s = round(mins * 60)
    return f"{s // 3600}h{s % 3600 // 60:02d}min" if s >= 3600 else f"{s // 60}min{s % 60:02d}s"


def _go(p, pl):
    a, log = p["action"], carregar("corridas", [])
    km, mins = num1(p, "km"), minutos(p.get("tempo"))
    if a == "zonas":
        fc = 208 - 0.7 * num1(p, "idade", 30)
        nomes = ["leve", "queima de gordura", "aeróbico", "limiar", "máximo"]
        return f"FC máxima estimada {fc:.0f} bpm. " + "; ".join(f"Z{i + 1} {n}: {fc * (0.5 + i * 0.1):.0f}-{fc * (0.6 + i * 0.1):.0f}"
                                                                for i, n in enumerate(nomes)) + ". Estimativa geral, não é avaliação médica."
    if a in ("registrar", "ritmo"):
        if not km or not mins:
            return "Diga a distância em km e o tempo."
        if a == "registrar":
            log.append({"d": hoje(), "km": km, "min": mins})
            guardar("corridas", log[-2000:])
        return f"{km:g} km em {hms(mins)}: ritmo de {ritmo(km, mins)}, {km / mins * 60:.1f} km/h."
    if not log:
        return "Nenhuma corrida anotada."
    if a == "semana":
        lim = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
        sem = [x for x in log if x["d"] >= lim]
        return f"Últimos 7 dias: {len(sem)} treino(s), {sum(x['km'] for x in sem):.1f} km, {hms(sum(x['min'] for x in sem))}."
    melhor = min(log, key=lambda x: x["min"] / x["km"])
    if a == "prever":
        base = max((x for x in log if x["km"] >= 3), key=lambda x: x["km"] / x["min"], default=melhor)
        alvo = km or 10
        t = riegel(base["min"], base["km"], alvo)
        return f"Pelo seu melhor treino ({base['km']:g} km), {alvo:g} km sairiam em cerca de {hms(t)} ({ritmo(alvo, t)})."
    longa = max(log, key=lambda x: x["km"])
    return f"Melhor ritmo: {ritmo(melhor['km'], melhor['min'])} em {melhor['km']:g} km ({melhor['d']}). Mais longa: {longa['km']:g} km. Total: {sum(x['km'] for x in log):.0f} km."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("registrar ritmo semana recordes prever zonas".split(), _go), player)
