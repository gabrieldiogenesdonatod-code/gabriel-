"""Despensa (2.19): validade dos alimentos e remédios de casa — o que vence esta semana, o que já venceu e o que acabou.

Exemplos: "o leite da geladeira vence dia 20", "o que está vencendo na despensa", "acabou o iogurte",
"validade do remédio".
"""
from __future__ import annotations

from plugins._lote2 import Colecao, P, dias_ate, num1, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("despensa", "Pantry expiry tracker: add items with best-before date and quantity, what expires soon or is expired, use/remove, list.",
           "adicionar | vencendo | usar | listar",
           "adicionar: nome, validade (dd/mm/aaaa), quantidade. vencendo: dias (window, default 5). usar: nome, quantidade (default all).",
           "nome validade quantidade dias")

D = Colecao("despensa")


def _go(p, pl):
    a, nome = p["action"], p.get("nome")
    tudo = sorted(D.tudo().values(), key=lambda v: v["validade"])
    if a == "adicionar":
        D.por(nome, {"validade": ler_data(p.get("validade")).isoformat(), "qtd": num1(p, "quantidade", 1)})
        return f"{nome} na despensa, vence em {dias_ate(D.pegar(nome)['validade'])} dia(s)."
    if a == "vencendo":
        jan = int(num1(p, "dias", 5))
        r = [f"{v['nome']} " + (f"vence em {dias_ate(v['validade'])} dia(s)" if dias_ate(v["validade"]) >= 0 else "VENCEU")
             for v in tudo if dias_ate(v["validade"]) <= jan]
        return "; ".join(r) or "Despensa em dia: nada vencendo."
    if a == "listar":
        return "\n".join(f"{v['nome']} ({v['qtd']:g}): {v['validade'][8:]}/{v['validade'][5:7]}" for v in tudo) or "Despensa vazia."
    v = D.pegar(nome)
    if not v:
        return "Isso não está na despensa."
    v["qtd"] -= num1(p, "quantidade", v["qtd"])
    if v["qtd"] <= 0:
        D.tirar(v["nome"])
        return f"{v['nome']} acabou. Quer que eu ponha na lista de compras?"
    D.por(v["nome"], v)
    return f"{v['nome']}: sobraram {v['qtd']:g}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("adicionar vencendo usar listar".split(), _go), player, "Despensa")
