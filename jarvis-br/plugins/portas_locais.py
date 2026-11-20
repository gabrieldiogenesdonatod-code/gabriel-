"""Portas locais (2.18): quem está usando a porta 3000/8000/5000, porta livre para o servidor e lista de portas abertas."""
from __future__ import annotations

import socket

from plugins._comum import WIN, rodar as executar
from plugins._lote2 import P, numeros, rodar

PLUGIN = P("portas_locais", "Local ports for dev: is a port in use and by which process, find a free port, list listening ports.",
           "quem_usa | livre | abertas",
           "quem_usa: porta. livre: porta (start, default 8000). abertas lists listening TCP ports.", "porta")


def em_uso(porta: int) -> bool:
    with socket.socket() as s:
        s.settimeout(.3)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def livre(inicio: int = 8000) -> int:
    for p in range(inicio, inicio + 200):
        if not em_uso(p):
            return p
    return 0


def _escutando() -> list[tuple[int, str]]:
    try:
        import psutil
        out = []
        for c in psutil.net_connections("tcp"):
            if c.status == "LISTEN" and c.laddr:
                try:
                    nome = psutil.Process(c.pid).name() if c.pid else "?"
                except Exception:
                    nome = "?"
                out.append((c.laddr.port, nome))
        return sorted(set(out))
    except Exception:
        return portas_do_netstat(executar(["netstat", "-ano"] if WIN else ["ss", "-ltn"])[1])


def portas_do_netstat(txt: str) -> list[tuple[int, str]]:
    """Linhas LISTEN/LISTENING do netstat (Windows) ou ss (Linux) → portas."""
    import re
    out = set()
    for linha in txt.splitlines():
        if "LISTEN" in linha.upper():
            m = re.search(r"[:\]](\d{2,5})\s", linha)
            if m:
                out.add((int(m.group(1)), "?"))
    return sorted(out)


def _go(p, pl):
    a, porta = str(p.get("action")).lower(), int((numeros(p.get("porta")) or [8000])[0])
    if a == "livre":
        return f"Porta livre: {livre(porta)}."
    lst = _escutando()
    if a == "abertas":
        return ", ".join(f"{pt} ({n})" for pt, n in lst[:40]) or "Não consegui listar (instale psutil)."
    if not em_uso(porta):
        return f"A porta {porta} está livre."
    quem = [n for pt, n in lst if pt == porta]
    return f"A porta {porta} está em uso" + (f" por {quem[0]}." if quem else ".")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("quem_usa livre abertas".split(), _go), player)
