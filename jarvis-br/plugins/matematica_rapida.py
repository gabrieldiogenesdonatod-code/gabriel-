"""Matemática rápida (2.18): treino de conta de cabeça (ou tabuada para crianças) com tempo e recorde."""
from __future__ import annotations

import random
import time

from plugins import _lote2
from plugins._lote2 import P, gravar_json, ler_json, numeros, rodar

PLUGIN = P("matematica_rapida", "Mental math drill game (also times tables for kids): question, answer, speed, streak and record.",
           "pergunta | responder | recorde | tabuada",
           "pergunta: nivel (1-3). responder: valor. tabuada: valor = number -> full times table.", "nivel valor")


def _arq():
    return _lote2.PASTA / "matematica.json"


def gerar(nivel: int, rng=random) -> tuple[str, int]:
    lim = {1: 10, 2: 50, 3: 200}.get(nivel, 50)
    op = rng.choice("+-x" if nivel > 1 else "+-")
    a, b = rng.randint(2, lim), rng.randint(2, lim if op != "x" else max(10, lim // 5))
    if op == "-" and b > a:
        a, b = b, a
    return f"{a} {op} {b}", (a + b if op == "+" else a - b if op == "-" else a * b)


def _go(p, pl):
    a, e = str(p.get("action")).lower(), ler_json(_arq(), {}) or {"seq": 0, "recorde": 0}
    if a == "tabuada":
        n = int((numeros(p.get("valor")) or [2])[0])
        return "\n".join(f"{n} x {i} = {n * i}" for i in range(1, 11))
    if a == "recorde":
        return f"Sequência atual {e['seq']}, recorde {e['recorde']}."
    if a == "responder" and "resp" in e:
        dt = time.time() - e.get("t0", time.time())
        ok = (numeros(p.get("valor")) or [None])[0] == e["resp"]
        e["seq"] = e["seq"] + 1 if ok else 0
        e["recorde"] = max(e["recorde"], e["seq"])
        msg = f"Certo em {dt:.1f}s! Sequência {e['seq']}." if ok else f"Errou, era {e['resp']}. Sequência zerada."
        e.pop("resp")
        gravar_json(_arq(), e)
        return msg + " Diga 'próxima'."
    q, r = gerar(int((numeros(p.get("nivel")) or [e.get("nivel", 2)])[0]))
    e.update(resp=r, t0=time.time(), nivel=int((numeros(p.get("nivel")) or [e.get("nivel", 2)])[0]))
    gravar_json(_arq(), e)
    return f"Quanto é {q}?"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"pergunta": _go, "proxima": _go, "responder": _go, "recorde": _go, "tabuada": _go}, player)
