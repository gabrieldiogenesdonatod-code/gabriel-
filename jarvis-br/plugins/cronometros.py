"""Cronômetros e timers nomeados (2.18): vários ao mesmo tempo, com voltas; o timer avisa por voz.

Exemplos: "põe um timer de 10 minutos para o bolo", "temporizador de 45 segundos", "quanto falta no timer",
"cronômetro para a corrida", "marca uma volta". Os timers continuam contando se o JARVIS reiniciar.
"""
from __future__ import annotations

import threading
import time

from plugins import _lote2
from plugins._lote2 import P, avisar, carregar, guardar, norm, numeros, rodar

PLUGIN = P("cronometros", "Named stopwatches with laps and several countdown timers at once that announce by voice.",
           "timer | timers | cancelar | iniciar | volta | parar",
           "timer: nome + tempo ('10 min', '1h30', '45 s'). timers lists. cancelar: nome. "
           "iniciar/volta/parar: named stopwatch (nome).",
           "nome tempo")

_TIMERS: dict[str, tuple[float, threading.Timer]] = {}
_CRONO: dict[str, dict] = {}


def segundos(t: str) -> int:
    t = norm(t).replace("e ", " ")
    n = numeros(t)
    if not n:
        return 0
    if "h" in t and len(n) > 1:
        return int(n[0] * 3600 + n[1] * 60)
    if "h" in t:
        return int(n[0] * 3600)
    if "min" in t and len(n) > 1:
        return int(n[0] * 60 + n[1])
    if "s" in t and "min" not in t:
        return int(n[0])
    return int(n[0] * 60)


def mmss(s: float) -> str:
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _gravar() -> None:
    guardar("timers", {k: f for k, (f, _) in _TIMERS.items()})


def _armar(nome: str, fim: float, pl=None) -> None:
    def tocar():
        _TIMERS.pop(norm(nome), None)
        _gravar()
        from core import registro_ferramentas
        avisar(pl or registro_ferramentas.player(), f"Timer '{nome}' acabou!", "TIMER")
    t = threading.Timer(max(1.0, fim - time.time()), tocar)
    t.daemon = True
    t.start()
    _TIMERS[norm(nome)] = (fim, t)


def restaurar() -> int:
    """2.19: timers que estavam contando quando o JARVIS fechou voltam a contar (os vencidos avisam em 5 s)."""
    if getattr(_lote2, "_timers_restaurados", False):
        return 0
    _lote2._timers_restaurados = True
    pendentes = carregar("timers", {})
    for nome, fim in pendentes.items():
        _armar(nome, max(fim, time.time() + 5))
    return len(pendentes)


def _timer(p, pl):
    s, nome = segundos(p.get("tempo")), str(p.get("nome") or "timer")
    if s <= 0:
        return "Quanto tempo?"
    _armar(nome, time.time() + s, pl)
    _gravar()
    return f"Timer '{nome}' de {mmss(s)} ligado."


def _timers(p, pl):
    agora = time.time()
    return "; ".join(f"{k}: faltam {mmss(f - agora)}" for k, (f, _) in _TIMERS.items()) or "Nenhum timer."


def _cancelar(p, pl):
    x = _TIMERS.pop(norm(p.get("nome") or "timer"), None)
    if x:
        x[1].cancel()
        _gravar()
    return "Cancelado." if x else "Não achei esse timer."


def _crono(p, pl):
    a, k = str(p.get("action")).lower(), norm(p.get("nome") or "principal")
    c = _CRONO.get(k)
    if a == "iniciar":
        _CRONO[k] = {"t0": time.time(), "voltas": []}
        return f"Cronômetro '{k}' rodando."
    if not c:
        return "Esse cronômetro não está rodando."
    dt = time.time() - c["t0"]
    if a == "volta":
        c["voltas"].append(dt)
        return f"Volta {len(c['voltas'])}: {mmss(dt)}."
    _CRONO.pop(k)
    return f"Parado em {mmss(dt)}" + (f", {len(c['voltas'])} volta(s)." if c["voltas"] else ".")


try:
    restaurar()
except Exception:
    pass


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"timer": _timer, "timers": _timers, "cancelar": _cancelar,
                              "iniciar": _crono, "volta": _crono, "parar": _crono}, player)
