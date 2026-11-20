"""Assinaturas (2.18): Netflix, Spotify, nuvem… total por mês/ano, próximas cobranças e as menos usadas."""
from __future__ import annotations

from datetime import date

from plugins._lote2 import Colecao, P, numeros, reais, rodar

PLUGIN = P("assinaturas", "Subscriptions: add with price and billing day, monthly/yearly total, upcoming charges, mark as unused to cancel.",
           "adicionar | total | proximas | nao_uso | apagar | listar",
           "adicionar: nome, valor, dia (billing day), periodo (mensal|anual). nao_uso: nome (flags it). proximas: next 7 days.",
           "nome valor dia periodo")

A = Colecao("assinaturas")


def mensal(s: dict) -> float:
    return s["valor"] / 12 if s.get("periodo") == "anual" else s["valor"]


def dias_ate(dia: int, ref: date) -> int:
    d = min(dia, 28)
    alvo = ref.replace(day=d) if ref.day <= d else (ref.replace(day=1, month=ref.month % 12 + 1,
                                                                year=ref.year + (ref.month == 12)).replace(day=d))
    return (alvo - ref).days


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), p.get("nome")
    if a == "adicionar":
        A.por(nome, {"valor": (numeros(p.get("valor")) or [0])[0], "dia": int((numeros(p.get("dia")) or [1])[0]),
                     "periodo": "anual" if "anu" in str(p.get("periodo")).lower() else "mensal", "nao_uso": False})
        return f"Assinatura '{nome}' anotada."
    tudo = list(A.tudo().values())
    if a == "total":
        t = sum(mensal(s) for s in tudo)
        parados = [s["nome"] for s in tudo if s.get("nao_uso")]
        return f"{reais(t)} por mês, {reais(t * 12)} por ano." + (f" Sem uso: {', '.join(parados)}." if parados else "")
    if a == "proximas":
        r = [(dias_ate(s["dia"], date.today()), s) for s in tudo]
        return "; ".join(f"{s['nome']} em {d} dia(s) ({reais(s['valor'])})" for d, s in sorted(r, key=lambda x: x[0]) if d <= 7) \
            or "Nenhuma cobrança nos próximos 7 dias."
    if a == "listar":
        return "\n".join(f"{s['nome']}: {reais(s['valor'])} dia {s['dia']}" for s in tudo) or "Nenhuma."
    s = A.pegar(nome)
    if not s:
        return "Não achei."
    if a == "apagar":
        A.tirar(nome)
        return "Removida. Lembre de cancelar no site também."
    s["nao_uso"] = True
    A.por(s["nome"], s)
    return f"Marquei {s['nome']} como sem uso: cancelar economiza {reais(mensal(s) * 12)} por ano."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("adicionar total proximas nao_uso apagar listar".split(), _go), player, "Assinaturas")
