"""Combustível (2.18): álcool ou gasolina (regra dos 70% ou pelo consumo real), abastecimentos, km/l e custo por km."""
from __future__ import annotations

from plugins import _lote2
from plugins._lote2 import P, gravar_json, hoje, ler_json, numeros, reais, rodar

PLUGIN = P("combustivel", "Fuel: ethanol vs gasoline (70% rule or real km/l), log fill-ups, average km/l, cost per km, trip cost.",
           "compensa | abastecer | media | viagem",
           "compensa: valor 'preço_etanol preço_gasolina' (+ optional km/l of each). abastecer: litros, preco, km (odometer). "
           "viagem: km -> cost from average.",
           "valor litros preco km")


def _arq():
    return _lote2.PASTA / "combustivel.json"


def compensa_etanol(pe, pg, kml_e=None, kml_g=None) -> tuple[bool, float]:
    razao = (kml_g / kml_e) if kml_e and kml_g else 1 / 0.7
    return pe * razao < pg, pe / pg


def media(log: list[dict]) -> tuple[float, float]:
    """km/l e R$/km entre o primeiro e o último abastecimento (tanque cheio)."""
    if len(log) < 2:
        return 0.0, 0.0
    km = log[-1]["km"] - log[0]["km"]
    litros = sum(x["l"] for x in log[1:])
    gasto = sum(x["l"] * x["p"] for x in log[1:])
    return (km / litros if litros else 0.0), (gasto / km if km else 0.0)


def _go(p, pl):
    a, log = str(p.get("action")).lower(), ler_json(_arq(), []) or []
    if a == "compensa":
        n = numeros(p.get("valor"))
        if len(n) < 2:
            return "Diga o preço do etanol e da gasolina."
        ok, r = compensa_etanol(n[0], n[1], *(n[2:4] if len(n) >= 4 else ()))
        return f"Etanol custa {r * 100:.0f}% da gasolina: abasteça com {'ETANOL' if ok else 'GASOLINA'}."
    if a == "abastecer":
        x = lambda k: (numeros(p.get(k)) or [0])[0]  # noqa: E731
        log.append({"d": hoje(), "l": x("litros"), "p": x("preco"), "km": x("km")})
        gravar_json(_arq(), log[-200:])
        return f"Abastecimento anotado: {reais(x('litros') * x('preco'))}."
    kml, rkm = media(log)
    if not kml:
        return "Preciso de pelo menos 2 abastecimentos com km do painel (tanque cheio)."
    if a == "viagem":
        km = (numeros(p.get("km")) or [0])[0]
        return f"{km:g} km ≈ {km / kml:.1f} litros ≈ {reais(km * rkm)}."
    return f"Média {kml:.1f} km/l, {reais(rkm)} por km."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("compensa abastecer media viagem".split(), _go), player)
