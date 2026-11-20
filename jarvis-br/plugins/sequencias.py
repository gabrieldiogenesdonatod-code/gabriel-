"""Sequências (2.18): hábitos do dia a dia com marcação diária e ofensiva (streak), estilo Duolingo."""
from __future__ import annotations

from datetime import date, timedelta

from plugins._lote2 import Colecao, P, rodar

PLUGIN = P("sequencias", "Habit streaks: create daily habits (read, exercise, study), check today, current/best streak, what's pending today.",
           "criar | feito | hoje | ofensivas | apagar",
           "criar: nome. feito: nome (marks today). hoje: pending habits today. ofensivas: streaks.",
           "nome")

H = Colecao("sequencias")


def ofensiva(dias: list[str], ref: date) -> int:
    s, d = set(dias), ref if ref.isoformat() in dias else ref - timedelta(1)
    n = 0
    while d.isoformat() in s:
        n, d = n + 1, d - timedelta(1)
    return n


def melhor(dias: list[str]) -> int:
    ds = sorted(date.fromisoformat(x) for x in set(dias))
    best = cur = 0
    for i, d in enumerate(ds):
        cur = cur + 1 if i and (d - ds[i - 1]).days == 1 else 1
        best = max(best, cur)
    return best


def _go(p, pl):
    a, nome, hoje = str(p.get("action")).lower(), p.get("nome"), date.today()
    if a == "criar":
        H.por(nome, {"dias": []})
        return f"Hábito '{nome}' criado."
    tudo = list(H.tudo().values())
    if a == "hoje":
        falta = [h["nome"] for h in tudo if hoje.isoformat() not in h["dias"]]
        return ("Falta hoje: " + ", ".join(falta) + ".") if falta else "Tudo feito hoje! 🔥"
    if a == "ofensivas":
        return "\n".join(f"{h['nome']}: {ofensiva(h['dias'], hoje)} dia(s) (recorde {melhor(h['dias'])})" for h in tudo) or "Nenhum hábito."
    h = H.pegar(nome)
    if not h:
        return "Não achei esse hábito."
    if a == "apagar":
        H.tirar(nome)
        return "Apagado."
    if hoje.isoformat() not in h["dias"]:
        h["dias"].append(hoje.isoformat())
        H.por(h["nome"], h)
    return f"{h['nome']} feito! Ofensiva de {ofensiva(h['dias'], hoje)} dia(s)."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("criar feito hoje ofensivas apagar".split(), _go), player, "Sequências")
