"""Vencimentos (2.19): validade de documentos e contratos (CNH, passaporte, seguro, licenciamento, domínio) com aviso antes."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, dias_ate, num1, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("vencimentos", "Expiry tracker for documents/contracts (driver's licence, passport, insurance, domain…): add, what's coming up, renew.",
           "adicionar | proximos | renovar | listar | apagar",
           "adicionar: nome, data (dd/mm/aaaa), antecedencia (days to warn, default 30). renovar: nome, data (new).",
           "nome data antecedencia")

V = Colecao("vencimentos")


def linha(v: dict) -> str:
    d = dias_ate(v["data"])
    return f"{v['nome']}: " + (f"vence em {d} dia(s)" if d >= 0 else f"VENCIDO há {-d} dia(s)")


def _go(p, pl):
    a, nome = p["action"], p.get("nome")
    tudo = sorted(V.tudo().values(), key=lambda v: v["data"])
    if a == "adicionar":
        V.por(nome, {"data": ler_data(p.get("data")).isoformat(), "aviso": int(num1(p, "antecedencia", 30))})
        return linha(V.pegar(nome)) + "."
    if a == "proximos":
        return "; ".join(linha(v) for v in tudo if dias_ate(v["data"]) <= v.get("aviso", 30)) or "Nenhum vencimento próximo."
    if a == "listar":
        return "\n".join(linha(v) for v in tudo) or "Nenhum vencimento anotado."
    v = V.pegar(nome)
    if not v:
        return "Não achei esse vencimento."
    if a == "apagar":
        V.tirar(nome)
        return "Apagado."
    v["data"] = ler_data(p.get("data")).isoformat()
    V.por(v["nome"], v)
    return "Renovado. " + linha(v) + "."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("adicionar proximos renovar listar apagar".split(), _go), player, "Vencimentos")
