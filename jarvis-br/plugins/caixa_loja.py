"""Caixa da loja (2.19): abre com o troco, anota vendas por forma de pagamento, sangria e suprimento, e fecha conferindo a gaveta."""
from __future__ import annotations

from plugins._lote2 import P, carregar, guardar, hoje, norm, num1, reais, rodar

PLUGIN = P("caixa_loja", "Store cash register: open with float, log sales by payment type, cash withdrawals/top-ups, close and check the drawer.",
           "abrir | venda | sangria | suprimento | resumo | fechar | historico",
           "abrir: valor (float in drawer). venda: valor, forma (dinheiro|pix|debito|credito). sangria/suprimento: valor. "
           "fechar: valor = cash counted in the drawer.",
           "valor forma")

FORMAS = {"din": "dinheiro", "pix": "pix", "deb": "débito", "cre": "crédito", "car": "crédito"}


def forma(t) -> str:
    return next((v for k, v in FORMAS.items() if norm(t).startswith(k)), "dinheiro")


def totais(d: dict) -> dict:
    out: dict = {}
    for v, f in d.get("vendas", []):
        out[f] = out.get(f, 0) + v
    return out


def gaveta(d: dict) -> float:
    """Dinheiro que deve estar na gaveta: troco + vendas em dinheiro + suprimentos - sangrias."""
    return d.get("abertura", 0) + totais(d).get("dinheiro", 0) + sum(d.get("suprimentos", [])) - sum(d.get("sangrias", []))


def resumo(d: dict) -> str:
    t = totais(d)
    return (f"{len(d.get('vendas', []))} venda(s), total {reais(sum(t.values()))} (" +
            ", ".join(f"{k} {reais(v)}" for k, v in t.items()) + f"). Na gaveta deve ter {reais(gaveta(d))}.")


def _go(p, pl):
    a, c, v = p["action"], carregar("caixa", {"dias": {}}), num1(p, "valor")
    dia = c["dias"].get(hoje())
    if a == "historico":
        return "\n".join(f"{k}: {reais(sum(totais(d).values()))}" + (f", diferença {reais(d['dif'])}" if d.get("dif") else "")
                         for k, d in sorted(c["dias"].items())[-10:]) or "Nenhum dia registrado."
    if a == "abrir":
        c["dias"][hoje()] = {"abertura": v, "vendas": [], "sangrias": [], "suprimentos": []}
        guardar("caixa", c)
        return f"Caixa aberto com {reais(v)} de troco."
    if dia is None:
        return "O caixa de hoje ainda não foi aberto. Diga 'abrir caixa com X reais'."
    if a == "venda":
        dia["vendas"].append([v, forma(p.get("forma"))])
    elif a in ("sangria", "suprimento"):
        dia[a + "s"].append(v)
    elif a == "fechar":
        dia["dif"] = round(v - gaveta(dia), 2)
        guardar("caixa", c)
        dif = dia["dif"]
        return resumo(dia) + (" Caixa bateu certinho." if abs(dif) < 0.01 else
                              f" {'Sobrou' if dif > 0 else 'Faltou'} {reais(abs(dif))}.")
    guardar("caixa", c)
    return resumo(dia)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("abrir venda sangria suprimento resumo fechar historico".split(), _go), player, "Caixa")
