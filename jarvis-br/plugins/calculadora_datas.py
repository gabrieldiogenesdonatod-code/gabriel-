"""Datas (2.18): diferença, somar dias, dias úteis, idade, dia da semana e contagens regressivas salvas."""
from __future__ import annotations

import re
from datetime import date, timedelta

from plugins._lote2 import Colecao, P, rodar

PLUGIN = P("calculadora_datas", "Dates: difference, add days, business days, age, weekday, saved countdowns ('quantos dias faltam').",
           "diferenca | somar | dias_uteis | idade | dia_semana | contagem_criar | contagens | contagem_apagar",
           "Date math (dd/mm/aaaa). diferenca/dias_uteis: data, data2 (default today). somar: data, dias (negative ok). "
           "idade: data. contagem_criar: nome, data. contagens lists days left.",
           "data data2 dias nome")

CONT = Colecao("contagens")
SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def ler_data(t, padrao: date | None = None) -> date:
    t = str(t or "").strip().lower()
    if not t or t == "hoje":
        return padrao or date.today()
    if t == "amanha" or t == "amanhã":
        return date.today() + timedelta(1)
    m = re.search(r"(\d{1,4})[/-](\d{1,2})(?:[/-](\d{2,4}))?", t)
    if not m:
        raise ValueError(f"não entendi a data '{t}' (use dd/mm/aaaa)")
    a, b, c = m.groups()
    if len(a) == 4:
        return date(int(a), int(b), int(c))
    ano = int(c) if c else date.today().year
    return date(ano + 2000 if ano < 100 else ano, int(b), int(a))


def dias_uteis(a: date, b: date) -> int:
    if b < a:
        a, b = b, a
    return sum(1 for k in range((b - a).days) if (a + timedelta(k)).weekday() < 5)


def idade(nasc: date, ref: date) -> int:
    return ref.year - nasc.year - ((ref.month, ref.day) < (nasc.month, nasc.day))


def _go(p, pl):
    a = str(p.get("action")).lower()
    if a == "diferenca":
        d = (ler_data(p.get("data2")) - ler_data(p.get("data"))).days
        return f"{abs(d)} dias ({abs(d) // 7} semanas e {abs(d) % 7} dias)."
    if a == "somar":
        r = ler_data(p.get("data")) + timedelta(int(float(p.get("dias") or 0)))
        return f"{r:%d/%m/%Y}, {SEMANA[r.weekday()]}."
    if a == "dias_uteis":
        return f"{dias_uteis(ler_data(p.get('data')), ler_data(p.get('data2')))} dias úteis (sem contar feriados)."
    if a == "idade":
        return f"{idade(ler_data(p.get('data')), date.today())} anos."
    if a == "dia_semana":
        return SEMANA[ler_data(p.get("data")).weekday()].capitalize() + "."
    if a == "contagem_criar":
        d = ler_data(p.get("data"))
        CONT.por(p.get("nome") or "evento", {"data": d.isoformat()})
        return f"Contagem '{p.get('nome')}' criada: faltam {(d - date.today()).days} dias."
    if a == "contagem_apagar":
        return "Apagada." if CONT.tirar(p.get("nome")) else "Não achei essa contagem."
    itens = sorted(CONT.tudo().values(), key=lambda v: v["data"])
    return "\n".join(f"{v['nome']}: {(date.fromisoformat(v['data']) - date.today()).days} dias" for v in itens) or "Nenhuma contagem."


def run(parameters, player=None, session_memory=None):
    acoes = "diferenca somar dias_uteis idade dia_semana contagem_criar contagens contagem_apagar".split()
    return rodar(parameters, dict.fromkeys(acoes, _go), player, "Datas")
