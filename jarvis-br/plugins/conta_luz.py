"""Conta de luz (2.18): quanto cada aparelho gasta por mês (kWh e R$) e o que pesa mais na conta."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, numeros, reais, rodar

PLUGIN = P("conta_luz", "Electricity cost per appliance: watts x hours/day -> kWh and R$/month; ranking; tariff setting.",
           "calcular | adicionar | ranking | tarifa | apagar",
           "calcular/adicionar: nome, watts, horas (per day), dias (per month, default 30). tarifa: valor R$/kWh (default 0.95).",
           "nome watts horas dias valor")

A = Colecao("aparelhos_luz")
WATTS = {"chuveiro": 5500, "ar condicionado": 1200, "geladeira": 150, "pc gamer": 450, "notebook": 65, "tv": 100,
         "ferro": 1000, "micro-ondas": 1200, "maquina de lavar": 500, "ventilador": 80, "lampada led": 9}


def kwh_mes(w, horas, dias=30):
    return w * horas * dias / 1000


def _tarifa():
    t = A.pegar("__tarifa__")
    return t["v"] if t else 0.95


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), str(p.get("nome") or "")
    x = lambda k, d: (numeros(p.get(k)) or [d])[0]  # noqa: E731
    if a == "tarifa":
        A.por("__tarifa__", {"v": x("valor", .95)})
        return f"Tarifa {reais(x('valor', .95))}/kWh."
    if a in ("calcular", "adicionar"):
        w = x("watts", WATTS.get(nome.lower(), 100))
        k = kwh_mes(w, x("horas", 1), x("dias", 30))
        if a == "adicionar":
            A.por(nome, {"kwh": k})
        return f"{nome or 'Aparelho'} ({w:g} W): {k:.1f} kWh/mês ≈ {reais(k * _tarifa())}."
    if a == "apagar":
        return "Apagado." if A.tirar(nome) else "Não achei."
    r = sorted((v for k, v in A.tudo().items() if k != "__tarifa__"), key=lambda v: -v["kwh"])
    tot = sum(v["kwh"] for v in r)
    return "\n".join(f"{v['nome']}: {v['kwh']:.0f} kWh ({reais(v['kwh'] * _tarifa())})" for v in r) + \
        f"\nTotal ≈ {reais(tot * _tarifa())}/mês" if r else "Adicione aparelhos primeiro."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("calcular adicionar ranking tarifa apagar".split(), _go), player, "Conta de luz")
