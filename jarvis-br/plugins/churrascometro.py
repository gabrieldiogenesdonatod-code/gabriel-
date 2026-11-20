"""Churrascômetro (2.19): quanto comprar de carne, acompanhamento, bebida e carvão para o churrasco, e quanto dá por pessoa."""
from __future__ import annotations

import math

from plugins._lote2 import P, num1, reais, rodar

PLUGIN = P("churrascometro", "Barbecue calculator: meat by type, garlic bread, soft drinks, beer, charcoal and ice for N adults/kids; cost per person.",
           "calcular | custo",
           "calcular: adultos, criancas, horas (default 4), bebem (adults who drink beer). custo: same + preco (average R$/kg of meat).",
           "adultos criancas horas bebem preco")


def quantidades(adultos: int, criancas: int = 0, horas: float = 4, bebem: int = 0) -> dict:
    """Regra de bolso: 400 g de carne por adulto (500 g se passar de 5 h), metade por criança. Pura."""
    carne = adultos * (0.5 if horas > 5 else 0.4) + criancas * 0.2
    pessoas = adultos + criancas
    return {"carne bovina (kg)": round(carne * 0.5, 1), "frango (kg)": round(carne * 0.25, 1), "linguiça (kg)": round(carne * 0.25, 1),
            "pão de alho (un)": adultos * 2 + criancas, "refrigerante/suco (L)": math.ceil(pessoas * 0.6),
            "água (L)": math.ceil(pessoas * 0.4), "cerveja (L)": math.ceil(bebem * 1.5), "carvão (kg)": math.ceil(carne * 1.0),
            "gelo (kg)": math.ceil(pessoas / 3), "_carne_total": round(carne, 1)}


def _go(p, pl):
    ad, cr = int(num1(p, "adultos")), int(num1(p, "criancas"))
    if ad + cr == 0:
        return "Quantos adultos e quantas crianças?"
    q = quantidades(ad, cr, num1(p, "horas", 4), int(num1(p, "bebem")))
    total = q.pop("_carne_total")
    txt = "\n".join(f"{k}: {v:g}" for k, v in q.items() if v)
    if p["action"] == "custo":
        gasto = total * num1(p, "preco", 45)
        txt += f"\nCarne: cerca de {reais(gasto)}, {reais(gasto / (ad + cr))} por pessoa (sem bebida)."
    return f"Para {ad} adulto(s) e {cr} criança(s), {total:g} kg de carne no total:\n" + txt


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"calcular": _go, "custo": _go}, player, "Churrasco")
