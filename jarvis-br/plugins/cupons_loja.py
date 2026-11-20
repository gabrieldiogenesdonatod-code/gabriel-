"""Cupons de desconto (2.19): cria códigos com % ou valor, validade, limite de usos e compra mínima; confere e aplica na venda."""
from __future__ import annotations

import random
from datetime import date

from plugins._lote2 import Colecao, P, num1, reais, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("cupons_loja", "Discount coupons: create code (% or R$, expiry, max uses, minimum purchase), check or apply to a sale total, list.",
           "criar | conferir | aplicar | listar | apagar",
           "criar: codigo (optional), valor ('10%' or '15' reais), validade (dd/mm/aaaa), usos, minimo. conferir/aplicar: codigo, total.",
           "codigo valor validade usos minimo total")

C = Colecao("cupons")


def desconto(c: dict, total: float, ref: date) -> tuple[bool, float, str]:
    if c.get("validade") and date.fromisoformat(c["validade"]) < ref:
        return False, 0.0, "cupom vencido"
    if c.get("usos") and c.get("usados", 0) >= c["usos"]:
        return False, 0.0, "cupom já usado o máximo de vezes"
    if total < c.get("minimo", 0):
        return False, 0.0, f"a compra mínima é {reais(c['minimo'])}"
    d = total * c["valor"] / 100 if c["tipo"] == "%" else min(c["valor"], total)
    return True, round(d, 2), ""


def _go(p, pl):
    a, cod = p["action"], str(p.get("codigo") or "").upper().strip()
    if a == "criar":
        pct = "%" in str(p.get("valor"))
        v = num1(p, "valor", 10)
        cod = cod or f"CRISTAL{int(v)}{random.randint(10, 99)}"
        C.por(cod, {"tipo": "%" if pct else "R$", "valor": v, "usos": int(num1(p, "usos")), "usados": 0, "minimo": num1(p, "minimo"),
                    "validade": ler_data(p.get("validade")).isoformat() if p.get("validade") else None})
        return f"Cupom {cod} criado: {v:g}% de desconto." if pct else f"Cupom {cod} criado: {reais(v)} de desconto."
    if a == "listar":
        return "\n".join(f"{c['nome']}: {c['valor']:g}{'%' if c['tipo'] == '%' else ' reais'}, usado {c.get('usados', 0)}x" +
                         (f", até {c['validade']}" if c.get("validade") else "") for c in C.tudo().values()) or "Nenhum cupom."
    c = C.pegar(cod)
    if not c:
        return "Esse cupom não existe."
    if a == "apagar":
        C.tirar(cod)
        return "Cupom apagado."
    total = num1(p, "total")
    ok, d, motivo = desconto(c, total, date.today())
    if not ok:
        return f"Não vale: {motivo}."
    if a == "aplicar":
        c["usados"] = c.get("usados", 0) + 1
        C.por(c["nome"], c)
    return f"Desconto de {reais(d)}: de {reais(total)} por {reais(total - d)}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("criar conferir aplicar listar apagar".split(), _go), player, "Cupons")
