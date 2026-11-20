"""Rodízio de tarefas da casa (2.18): divide lavar louça, lixo, varrer… entre as pessoas e gira toda semana."""
from __future__ import annotations

from datetime import date

from plugins import _lote2
from plugins._lote2 import P, gravar_json, ler_json, lista, norm, rodar

PLUGIN = P("rodizio_tarefas", "Household chores rotation: people and chores, who does what this week (rotates weekly), one person's chores.",
           "configurar | semana | de_quem | proxima",
           "configurar: pessoas (comma), tarefas (comma). semana: this week's split. de_quem: pessoa. proxima: next week.",
           "pessoas tarefas pessoa")


def _arq():
    return _lote2.PASTA / "rodizio.json"


def divisao(pessoas: list[str], tarefas: list[str], semana: int) -> dict[str, list[str]]:
    out = {p: [] for p in pessoas}
    for i, t in enumerate(tarefas):
        out[pessoas[(i + semana) % len(pessoas)]].append(t)
    return out


def _go(p, pl):
    a, e = str(p.get("action")).lower(), ler_json(_arq(), {}) or {}
    if a == "configurar":
        e = {"pessoas": lista(p.get("pessoas")), "tarefas": lista(p.get("tarefas"))}
        gravar_json(_arq(), e)
        return f"{len(e['pessoas'])} pessoa(s), {len(e['tarefas'])} tarefa(s)."
    if not e.get("pessoas"):
        return "Configure primeiro: pessoas e tarefas."
    sem = date.today().isocalendar()[1] + (a == "proxima")
    d = divisao(e["pessoas"], e["tarefas"], sem)
    if a == "de_quem":
        k = next((x for x in d if norm(x) == norm(p.get("pessoa"))), None)
        return f"{k}: {', '.join(d[k]) or 'folga'}." if k else "Essa pessoa não está no rodízio."
    return "\n".join(f"{k}: {', '.join(v) or 'folga'}" for k, v in d.items())


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("configurar semana de_quem proxima".split(), _go), player, "Rodízio")
