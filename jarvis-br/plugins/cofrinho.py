"""Cofrinho (2.18): metas de economia com prazo; quanto guardar por mês e se está no ritmo."""
from __future__ import annotations

from datetime import date

from plugins._lote2 import Colecao, P, hoje, numeros, reais, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("cofrinho", "Savings goals: create a goal with deadline, deposit/withdraw, monthly amount needed, on-track check.",
           "criar | guardar | tirar | ver | apagar",
           "criar: nome, valor (goal), data (deadline dd/mm/aaaa). guardar/tirar: nome, valor. ver: nome or all.",
           "nome valor data")

C = Colecao("cofrinho")


def meses_ate(ref: date, fim: date) -> int:
    return max(1, (fim.year - ref.year) * 12 + fim.month - ref.month)


def resumo(m: dict, ref: date) -> str:
    falta = max(0.0, m["meta"] - m["saldo"])
    txt = f"{m['nome']}: {reais(m['saldo'])} de {reais(m['meta'])} ({m['saldo'] * 100 // max(1, m['meta']):.0f}%)"
    if falta and m.get("fim"):
        txt += f", guarde {reais(falta / meses_ate(ref, date.fromisoformat(m['fim'])))} por mês"
    return txt + ("" if falta else " — meta batida!")


def _go(p, pl):
    a, nome, v = str(p.get("action")).lower(), p.get("nome"), (numeros(p.get("valor")) or [0])[0]
    if a == "criar":
        fim = ler_data(p.get("data")).isoformat() if p.get("data") else None
        C.por(nome, {"meta": v, "saldo": 0.0, "fim": fim, "mov": []})
        return f"Meta '{nome}' criada."
    if a == "ver" and not nome:
        return "\n".join(resumo(m, date.today()) for m in C.tudo().values()) or "Nenhuma meta."
    m = C.pegar(nome)
    if not m:
        return "Não achei essa meta."
    if a == "apagar":
        C.tirar(nome)
        return "Meta apagada."
    if a in ("guardar", "tirar"):
        m["saldo"] += v if a == "guardar" else -v
        m["mov"].append([hoje(), v if a == "guardar" else -v])
        C.por(m["nome"], m)
    return resumo(m, date.today()) + "."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("criar guardar tirar ver apagar".split(), _go), player, "Cofrinho")
