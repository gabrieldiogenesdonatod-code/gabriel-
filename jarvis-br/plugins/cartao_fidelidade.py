"""Cartão fidelidade (2.19): carimbos por compra para cada cliente; ao completar o cartão, ganha o prêmio da loja."""
from __future__ import annotations

from plugins._lote2 import P, carregar, guardar, norm, num1, rodar

PLUGIN = P("cartao_fidelidade", "Loyalty card: stamp a customer's purchases, balance, redeem the reward, set the rule (N stamps = prize), top customers.",
           "carimbar | saldo | resgatar | regra | ranking",
           "carimbar: cliente, valor (stamps, default 1). saldo/resgatar: cliente. regra: valor (stamps needed), premio.",
           "cliente valor premio")


def _go(p, pl):
    a, d = p["action"], carregar("fidelidade", {"meta": 10, "premio": "um brinde", "clientes": {}})
    if a == "regra":
        d["meta"], d["premio"] = int(num1(p, "valor", d["meta"])), str(p.get("premio") or d["premio"])
        guardar("fidelidade", d)
        return f"Regra: {d['meta']} carimbos valem {d['premio']}."
    if a == "ranking":
        top = sorted(d["clientes"].values(), key=lambda c: -c["total"])[:8]
        return "; ".join(f"{c['nome']}: {c['total']} compra(s)" for c in top) or "Nenhum cliente com carimbo."
    nome = str(p.get("cliente") or "").strip()
    if not nome:
        return "Qual cliente?"
    c = d["clientes"].setdefault(norm(nome), {"nome": nome, "carimbos": 0, "total": 0, "resgates": 0})
    if a == "carimbar":
        n = int(num1(p, "valor", 1))
        c["carimbos"] += n
        c["total"] += n
    elif a == "resgatar":
        if c["carimbos"] < d["meta"]:
            return f"{c['nome']} ainda tem {c['carimbos']} de {d['meta']} carimbos."
        c["carimbos"] -= d["meta"]
        c["resgates"] += 1
        guardar("fidelidade", d)
        return f"{c['nome']} resgatou {d['premio']}! Sobraram {c['carimbos']} carimbo(s)."
    guardar("fidelidade", d)
    falta = d["meta"] - c["carimbos"]
    return f"{c['nome']}: {c['carimbos']} de {d['meta']} carimbos. " + (f"Faltam {falta} para ganhar {d['premio']}." if falta > 0
                                                                        else f"Já pode resgatar {d['premio']}!")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("carimbar saldo resgatar regra ranking".split(), _go), player)
