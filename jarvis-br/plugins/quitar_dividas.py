"""Quitar dívidas (2.19): lista as dívidas e simula o plano avalanche (maior juro primeiro) ou bola de neve (menor saldo primeiro)."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, norm, num1, reais, rodar

PLUGIN = P("quitar_dividas", "Debt payoff planner: list debts (balance, monthly rate, minimum), simulate avalanche vs snowball with a monthly budget, log payments.",
           "adicionar | plano | pagar | listar | apagar",
           "adicionar: nome, saldo, juros (% per month), minimo. plano: valor (monthly budget), metodo (avalanche|bola_de_neve). "
           "pagar: nome, valor.",
           "nome saldo juros minimo valor metodo")

D = Colecao("dividas")


def simular(dividas: list[dict], mensal: float, metodo: str = "avalanche") -> tuple[int, float, list[str]] | None:
    """(meses, juros pagos, ordem de quitação) ou None se a parcela não cobre os mínimos/juros. Pura."""
    ds = [dict(d) for d in dividas if d["saldo"] > 0]
    if not ds or mensal < sum(min(d["minimo"], d["saldo"]) for d in ds):
        return None
    meses, juros, ordem = 0, 0.0, []
    while ds and meses < 600:
        meses += 1
        for d in ds:
            j = d["saldo"] * d["juros"] / 100
            d["saldo"] += j
            juros += j
        resto = mensal
        for d in ds:
            pg = min(d["minimo"], d["saldo"], resto)
            d["saldo"] -= pg
            resto -= pg
        for d in sorted(ds, key=(lambda d: -d["juros"]) if metodo == "avalanche" else (lambda d: d["saldo"])):
            pg = min(resto, d["saldo"])
            d["saldo"] -= pg
            resto -= pg
        ordem += [d["nome"] for d in ds if d["saldo"] <= 0.005]
        ds = [d for d in ds if d["saldo"] > 0.005]
    return None if ds else (meses, juros, ordem)


def _go(p, pl):
    a, nome = p["action"], p.get("nome")
    tudo = list(D.tudo().values())
    if a == "adicionar":
        D.por(nome, {"saldo": num1(p, "saldo"), "juros": num1(p, "juros"), "minimo": num1(p, "minimo")})
        return f"Dívida '{nome}' anotada."
    if a == "listar":
        return "\n".join(f"{d['nome']}: {reais(d['saldo'])} a {d['juros']:g}% ao mês" for d in tudo) + \
            f"\nTotal: {reais(sum(d['saldo'] for d in tudo))}" if tudo else "Nenhuma dívida anotada."
    if a == "plano":
        met = "bola_de_neve" if "bola" in norm(p.get("metodo")) or "neve" in norm(p.get("metodo")) else "avalanche"
        r, outro = simular(tudo, num1(p, "valor"), met), simular(tudo, num1(p, "valor"), "bola_de_neve" if met == "avalanche" else "avalanche")
        if not r:
            return "Com esse valor por mês as dívidas não diminuem (não cobre os mínimos ou os juros). Tente renegociar os juros."
        msg = f"Plano {met.replace('_', ' ')}: quita tudo em {r[0]} meses pagando {reais(r[1])} de juros. Ordem: {', '.join(r[2])}."
        return msg + (f" No outro método seriam {outro[0]} meses e {reais(outro[1])} de juros." if outro else "")
    d = D.pegar(nome)
    if not d:
        return "Não achei essa dívida."
    if a == "apagar":
        D.tirar(nome)
        return "Dívida apagada."
    d["saldo"] = max(0.0, d["saldo"] - num1(p, "valor"))
    D.por(d["nome"], d)
    return f"{d['nome']}: faltam {reais(d['saldo'])}." if d["saldo"] else f"{d['nome']} quitada! 🎉"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("adicionar plano pagar listar apagar".split(), _go), player, "Dívidas")
