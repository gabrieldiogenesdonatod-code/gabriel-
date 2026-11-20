"""Analisador de log (2.19): resume um arquivo de log — quantos erros e avisos, as mensagens que mais se repetem e os últimos erros."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from plugins._lote2 import P, num1, rodar

PLUGIN = P("log_analisador", "Log file analyzer: counts by level, most repeated error messages, last N errors, search a term, time span.",
           "resumo | erros | buscar", "arquivo = log path. erros: quantidade (default 10). buscar: texto.", "arquivo quantidade texto")

NIVEL = re.compile(r"\b(CRITICAL|FATAL|ERROR|ERRO|WARN(?:ING)?|AVISO|INFO|DEBUG)\b|Traceback \(most recent call last\)", re.I)
DATA = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?|\d{2}/\d{2}/\d{4} \d{2}:\d{2}")
RUIM = ("CRITICAL", "FATAL", "ERROR", "ERRO", "TRACEBACK")


def nivel(l: str) -> str:
    m = NIVEL.search(l)
    if not m:
        return ""
    t = m.group(0).upper()
    return "TRACEBACK" if t.startswith("TRACEBACK") else "WARNING" if t.startswith(("WARN", "AVISO")) else "ERROR" if t == "ERRO" else t


def resumir(linhas: list[str]) -> dict:
    """Contagem por nível, mensagens de erro mais repetidas (sem números) e período. Pura."""
    cont, msgs = Counter(), Counter()
    for l in linhas:
        n = nivel(l)
        if n:
            cont[n] += 1
        if n in RUIM:
            msgs[re.sub(r"\d+", "N", DATA.sub("", l)).strip()[:110]] += 1
    datas = [m.group(0) for l in linhas for m in [DATA.search(l)] if m]
    return {"niveis": dict(cont), "top": msgs.most_common(5), "inicio": datas[0] if datas else "", "fim": datas[-1] if datas else ""}


def _go(p, pl):
    arq = Path(str(p.get("arquivo") or "").strip().strip('"')).expanduser()
    if not arq.is_file():
        return "Não achei esse arquivo de log."
    linhas = arq.read_text(encoding="utf-8", errors="ignore").splitlines()[-200_000:]
    a = p["action"]
    if a == "erros":
        ruins = [l[:200] for l in linhas if nivel(l) in RUIM]
        return "\n".join(ruins[-int(num1(p, "quantidade", 10)):]) or "Nenhum erro no log."
    if a == "buscar":
        q = str(p.get("texto") or "").lower()
        achou = [l[:200] for l in linhas if q and q in l.lower()]
        return f"{len(achou)} linha(s) com '{q}'.\n" + "\n".join(achou[-5:]) if achou else "Nada encontrado."
    r = resumir(linhas)
    periodo = f" De {r['inicio']} a {r['fim']}." if r["inicio"] else ""
    return (f"{len(linhas)} linhas.{periodo} " + (", ".join(f"{k}: {v}" for k, v in sorted(r["niveis"].items())) or "Sem níveis reconhecidos") +
            "." + ("\nMais repetidos:\n" + "\n".join(f"{n}x {m}" for m, n in r["top"]) if r["top"] else ""))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"resumo": _go, "erros": _go, "buscar": _go}, player, "Log")
