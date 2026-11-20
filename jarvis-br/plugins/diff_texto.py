"""Diff de texto (2.19): compara dois textos ou dois arquivos e mostra o que mudou e o quanto são parecidos."""
from __future__ import annotations

import difflib

from plugins._lote2 import P, rodar
from plugins.conversor_dados import _ler

PLUGIN = P("diff_texto", "Compare two texts or files: unified diff of changed lines, counts of added/removed lines, similarity %.",
           "comparar | semelhanca", "a and b = text or file paths.", "a b")


def resumo(a: str, b: str) -> tuple[int, int, list[str]]:
    linhas = list(difflib.unified_diff(a.splitlines(), b.splitlines(), "antes", "depois", lineterm="", n=1))
    mais = sum(1 for l in linhas if l.startswith("+") and not l.startswith("+++"))
    menos = sum(1 for l in linhas if l.startswith("-") and not l.startswith("---"))
    return mais, menos, linhas


def _go(p, pl):
    a, b = _ler(str(p.get("a") or ""))[0], _ler(str(p.get("b") or ""))[0]
    sem = difflib.SequenceMatcher(None, a, b).ratio() * 100
    if p["action"] == "semelhanca":
        return f"Os textos são {sem:.1f}% parecidos."
    mais, menos, linhas = resumo(a, b)
    if not linhas:
        return "Os dois são idênticos."
    return f"{mais} linha(s) a mais, {menos} a menos ({sem:.0f}% parecidos).\n" + "\n".join(linhas[:60])


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"comparar": _go, "semelhanca": _go}, player, "Diff")
