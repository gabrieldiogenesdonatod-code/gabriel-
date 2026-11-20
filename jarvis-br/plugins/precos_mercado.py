"""Preços de mercado (2.19): qual embalagem sai mais barata por quilo/litro e o histórico do que você pagou em cada produto."""
from __future__ import annotations

import re

from plugins._lote2 import P, carregar, guardar, hoje, norm, num1, reais, rodar

PLUGIN = P("precos_mercado", "Grocery prices: which package is cheaper per kg/litre/unit, and a price history per product (lowest, average, is today's price good).",
           "comparar | anotar | historico",
           "comparar: opcoes separated by ';' ('500 g 8,90; 1 kg 16,50'). anotar: produto, valor, local. historico: produto.",
           "opcoes produto valor local")

BASE = {"g": ("kg", .001), "kg": ("kg", 1), "ml": ("litro", .001), "l": ("litro", 1), "un": ("unidade", 1)}


def ler_opcao(t: str) -> tuple[float, str, float]:
    """'500 g 8,90' → (preço por kg, 'kg', preço). Pura."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|un\w*|litros?|unidades?)?\b[^\d]*(\d+(?:[.,]\d+)?)", norm(t))
    if not m:
        raise ValueError(f"não entendi '{t}' (use '500 g 8,90')")
    qtd, un, preco = float(m.group(1).replace(",", ".")), (m.group(2) or "un"), float(m.group(3).replace(",", "."))
    un = "l" if un.startswith("litro") else "un" if un.startswith("un") else un
    nome, fator = BASE[un]
    return preco / (qtd * fator), nome, preco


def _go(p, pl):
    a = p["action"]
    if a == "comparar":
        ops = [(ler_opcao(x), x.strip()) for x in str(p.get("opcoes") or "").split(";") if x.strip()]
        if len(ops) < 2:
            return "Diga duas opções, ex.: '500 g 8,90; 1 kg 16,50'."
        ops.sort(key=lambda o: o[0][0])
        (melhor, un, _), txt = ops[0]
        economia = (1 - melhor / ops[-1][0][0]) * 100
        return f"Leve '{txt}': {reais(melhor)} por {un}, {economia:.0f}% mais barato que a opção mais cara."
    h, prod = carregar("precos", {}), norm(p.get("produto"))
    if not prod:
        return "Qual produto?"
    if a == "anotar":
        h.setdefault(prod, []).append([hoje(), num1(p, "valor"), str(p.get("local") or "")])
        guardar("precos", h)
    reg = h.get(prod) or next((v for k, v in h.items() if prod in k), None)
    if not reg:
        return "Ainda não anotei preço desse produto."
    vals = [r[1] for r in reg]
    media, ult = sum(vals) / len(vals), reg[-1]
    nota = "abaixo da média, bom preço" if ult[1] < media * .97 else "acima da média" if ult[1] > media * 1.03 else "na média"
    return (f"{prod}: último {reais(ult[1])}{' no ' + ult[2] if ult[2] else ''} ({nota}); menor {reais(min(vals))}, "
            f"média {reais(media)} em {len(vals)} compra(s).")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("comparar anotar historico".split(), _go), player)
