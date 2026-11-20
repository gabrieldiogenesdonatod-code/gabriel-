"""Explorar JSON (2.19): mostra a estrutura de um JSON grande, pega um valor pelo caminho (a.b[0].c) e procura onde algo aparece."""
from __future__ import annotations

import json
import re

from plugins._lote2 import P, rodar
from plugins.conversor_dados import _ler

PLUGIN = P("explorar_json", "Explore a big JSON (text or file): structure tree with types, get a value by path (a.b[0].c), find where a key/value appears.",
           "estrutura | caminho | buscar", "texto = JSON or file path. caminho: caminho ('usuarios[0].nome'). buscar: valor.",
           "texto caminho valor")


def estrutura(d, prof: int = 3, recuo: int = 0) -> list[str]:
    esp = "  " * recuo
    if isinstance(d, dict):
        out = []
        for k, v in list(d.items())[:25]:
            tipo = f"lista[{len(v)}]" if isinstance(v, list) else "objeto" if isinstance(v, dict) else type(v).__name__
            out.append(f"{esp}{k}: {tipo}")
            if prof > 1 and isinstance(v, (dict, list)):
                out += estrutura(v, prof - 1, recuo + 1)
        return out
    if isinstance(d, list) and d:
        return estrutura(d[0], prof, recuo) if isinstance(d[0], (dict, list)) else [f"{esp}itens: {type(d[0]).__name__}"]
    return []


def pegar(d, caminho: str):
    for parte in re.findall(r"[^.\[\]]+", caminho):
        d = d[int(parte)] if isinstance(d, list) else d[parte]
    return d


def achar(d, q: str, onde: str = "") -> list[str]:
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            c = f"{onde}.{k}" if onde else str(k)
            if q in str(k).lower():
                out.append(c)
            out += achar(v, q, c)
    elif isinstance(d, list):
        for i, v in enumerate(d[:500]):
            out += achar(v, q, f"{onde}[{i}]")
    elif q in str(d).lower():
        out.append(f"{onde} = {str(d)[:60]}")
    return out


def _go(p, pl):
    d, a = json.loads(_ler(str(p.get("texto") or ""))[0]), p["action"]
    if a == "estrutura":
        topo = f"lista com {len(d)} item(ns)" if isinstance(d, list) else f"objeto com {len(d)} chave(s)" if isinstance(d, dict) else type(d).__name__
        return topo + "\n" + "\n".join(estrutura(d)[:80])
    if a == "caminho":
        try:
            v = pegar(d, str(p.get("caminho") or ""))
        except (KeyError, IndexError, ValueError, TypeError):
            return "Esse caminho não existe no JSON."
        return json.dumps(v, indent=2, ensure_ascii=False)[:1500]
    r = achar(d, str(p.get("valor") or p.get("caminho") or "").lower())
    return f"{len(r)} lugar(es):\n" + "\n".join(r[:30]) if r else "Não aparece no JSON."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"estrutura": _go, "caminho": _go, "buscar": _go}, player, "JSON")
