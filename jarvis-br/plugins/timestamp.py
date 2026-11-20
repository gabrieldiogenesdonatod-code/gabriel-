"""Timestamp (2.19): converte entre data e epoch (segundos ou milissegundos), mostra a hora atual em ISO e a diferença entre dois."""
from __future__ import annotations

import time
from datetime import datetime

from plugins._lote2 import P, numeros, rodar

PLUGIN = P("timestamp", "Unix timestamps for devs: now (epoch s/ms, ISO), epoch to date (auto-detects ms), date to epoch, difference between two epochs.",
           "agora | de_epoch | para_epoch | diferenca",
           "de_epoch: valor. para_epoch: data ('dd/mm/aaaa hh:mm'). diferenca: valor ('epoch1 epoch2').", "valor data")


def de_epoch(v: float) -> datetime:
    return datetime.fromtimestamp(v / 1000 if v > 1e11 else v)


def para_epoch(texto: str) -> int:
    n = [int(x) for x in numeros(str(texto).replace("/", " ").replace(":", " ").replace("-", " "))]
    if len(n) < 3:
        raise ValueError("use 'dd/mm/aaaa hh:mm'")
    d, m, a = (n[2], n[1], n[0]) if n[0] > 31 else (n[0], n[1], n[2])
    return int(datetime(a if a > 99 else a + 2000, m, d, *(n[3:6])).timestamp())


def duracao(s: float) -> str:
    s = int(abs(s))
    return f"{s // 86400}d {s % 86400 // 3600}h {s % 3600 // 60}min {s % 60}s"


def _go(p, pl):
    a, n = p["action"], numeros(p.get("valor"))
    if a == "agora":
        t = time.time()
        return f"Epoch {int(t)} (ms {int(t * 1000)}), ISO {datetime.now().astimezone().isoformat(timespec='seconds')}."
    if a == "de_epoch":
        return f"{de_epoch(n[0]):%d/%m/%Y %H:%M:%S} (hora local)." if n else "Qual o número?"
    if a == "para_epoch":
        e = para_epoch(p.get("data") or p.get("valor"))
        return f"Epoch {e} (ms {e * 1000})."
    if len(n) < 2:
        return "Diga os dois timestamps."
    x, y = (v / 1000 if v > 1e11 else v for v in n[:2])
    return f"Diferença de {duracao(y - x)} ({y - x:.0f} s)."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("agora de_epoch para_epoch diferenca".split(), _go), player)
