"""Horas de freela (2.18): liga/desliga o relógio por cliente, valor por hora e quanto faturar no mês."""
from __future__ import annotations

import time

from plugins import _lote2
from plugins._lote2 import P, gravar_json, ler_json, norm, numeros, reais, rodar

PLUGIN = P("horas_freela", "Freelance time tracking per client: start/stop clock, add hours manually, hourly rate, monthly invoice total.",
           "comecar | parar | adicionar | valor_hora | relatorio",
           "comecar/parar: cliente. adicionar: cliente, horas. valor_hora: cliente, valor. relatorio: mes (aaaa-mm, default current).",
           "cliente horas valor mes")


def _arq():
    return _lote2.PASTA / "freela.json"


def relatorio(d: dict, mes: str) -> list[tuple[str, float, float]]:
    out = []
    for c, info in d.get("clientes", {}).items():
        h = sum(x["h"] for x in d.get("log", []) if x["c"] == c and x["d"].startswith(mes))
        if h:
            out.append((c, h, h * info.get("hora", 0)))
    return out


def _go(p, pl):
    a, d = str(p.get("action")).lower(), ler_json(_arq(), {}) or {}
    d.setdefault("clientes", {}), d.setdefault("log", [])
    c = norm(p.get("cliente") or "geral")
    d["clientes"].setdefault(c, {"hora": 0})
    msg = ""
    if a == "comecar":
        d["rodando"] = {"c": c, "t0": time.time()}
        msg = f"Relógio de {c} ligado."
    elif a == "parar":
        r = d.pop("rodando", None)
        if not r:
            return "Nenhum relógio ligado."
        h = (time.time() - r["t0"]) / 3600
        d["log"].append({"c": r["c"], "h": round(h, 2), "d": time.strftime("%Y-%m-%d")})
        msg = f"{r['c']}: +{h:.2f} h."
    elif a == "adicionar":
        h = (numeros(p.get("horas")) or [0])[0]
        d["log"].append({"c": c, "h": h, "d": time.strftime("%Y-%m-%d")})
        msg = f"{c}: +{h:g} h."
    elif a == "valor_hora":
        d["clientes"][c]["hora"] = (numeros(p.get("valor")) or [0])[0]
        msg = f"{c}: {reais(d['clientes'][c]['hora'])} por hora."
    else:
        mes = str(p.get("mes") or time.strftime("%Y-%m"))
        r = relatorio(d, mes)
        msg = "\n".join(f"{c}: {h:.1f} h = {reais(v)}" for c, h, v in r) + \
              f"\nTotal {mes}: {reais(sum(v for *_, v in r))}" if r else "Nenhuma hora nesse mês."
    gravar_json(_arq(), d)
    return msg


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("comecar parar adicionar valor_hora relatorio".split(), _go), player, "Freela")
