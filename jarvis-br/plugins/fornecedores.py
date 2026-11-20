"""Fornecedores (2.19): contato, prazo de entrega e pedido mínimo de cada um; pedidos feitos e quando devem chegar."""
from __future__ import annotations

from datetime import date, timedelta

from plugins._lote2 import Colecao, P, dias_ate, num1, reais, rodar

PLUGIN = P("fornecedores", "Suppliers: contact, lead time, minimum order; log purchase orders with expected arrival; pending and late orders.",
           "cadastrar | pedido | recebido | pendentes | ver | listar | apagar",
           "cadastrar: nome, contato, prazo (days), minimo (R$). pedido: nome, valor. recebido: nome.",
           "nome contato prazo minimo valor")

F = Colecao("fornecedores")


def _go(p, pl):
    a, nome = p["action"], p.get("nome")
    if a == "cadastrar":
        velho = F.pegar(nome) or {}
        F.por(nome, {"contato": str(p.get("contato") or velho.get("contato", "")), "prazo": int(num1(p, "prazo", velho.get("prazo", 7))),
                     "minimo": num1(p, "minimo", velho.get("minimo", 0)), "pedidos": velho.get("pedidos", [])})
        return f"Fornecedor {nome} salvo."
    if a == "listar":
        return "\n".join(f"{f['nome']}: {f['contato']}, {f['prazo']} dias, mínimo {reais(f['minimo'])}" for f in F.tudo().values()) or "Nenhum fornecedor."
    if a == "pendentes":
        out = []
        for f in F.tudo().values():
            for ped in f["pedidos"]:
                if not ped.get("recebido"):
                    d = dias_ate(ped["previsao"])
                    out.append(f"{f['nome']}: {reais(ped['valor'])}, " + (f"chega em {d} dia(s)" if d >= 0 else f"ATRASADO {-d} dia(s)"))
        return "\n".join(out) or "Nenhum pedido a caminho."
    f = F.pegar(nome)
    if not f:
        return "Não achei esse fornecedor."
    if a == "apagar":
        F.tirar(nome)
        return "Fornecedor apagado."
    if a == "pedido":
        v = num1(p, "valor")
        if f["minimo"] and v < f["minimo"]:
            return f"O pedido mínimo de {f['nome']} é {reais(f['minimo'])}."
        prev = date.today() + timedelta(f["prazo"])
        f["pedidos"].append({"data": date.today().isoformat(), "valor": v, "previsao": prev.isoformat()})
        F.por(f["nome"], f)
        return f"Pedido de {reais(v)} anotado; deve chegar em {prev:%d/%m}."
    if a == "recebido":
        aberto = next((x for x in f["pedidos"] if not x.get("recebido")), None)
        if not aberto:
            return "Não há pedido em aberto com ele."
        aberto["recebido"] = date.today().isoformat()
        F.por(f["nome"], f)
        return f"Pedido de {f['nome']} recebido."
    total = sum(x["valor"] for x in f["pedidos"])
    return f"{f['nome']}: {f['contato']}, prazo {f['prazo']} dias, mínimo {reais(f['minimo'])}, {len(f['pedidos'])} pedido(s), {reais(total)} no total."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("cadastrar pedido recebido pendentes ver listar apagar".split(), _go), player, "Fornecedores")
