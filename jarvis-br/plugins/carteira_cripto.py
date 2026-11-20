"""
Carteira de cripto (fork PT-BR 3.7) — quanto você tem de cada moeda, quanto vale hoje e o seu lucro ou prejuízo.

    "Jarvis, comprei 0,002 bitcoin por 1.200 reais"     "Jarvis, vendi 0,001 bitcoin por 700"
    "Jarvis, como está minha carteira de cripto?"       "Jarvis, histórico da carteira"
    "Jarvis, tira o dogecoin da carteira"

Preço médio: cada compra entra no custo médio da moeda; numa venda, o lucro é (preço de venda − custo médio)
× quantidade. A mineração também entra: o que o plugin `mineracao` estimou aparece como "minerado".
Preços do CoinGecko em reais (sem chave). É só controle: não compra, não vende e não é recomendação.
Nenhuma chave, senha ou frase de recuperação da carteira é pedida ou guardada — nunca diga isso ao JARVIS.
"""
from __future__ import annotations

import re
import time

from plugins._lote2 import P, carregar, guardar, norm, numeros, reais, rodar

PLUGIN = P("carteira_cripto", "Crypto portfolio: record buys and sells in reais, see value now, average cost and profit or loss per coin.",
           "ver | comprar | vender | historico | remover",
           "comprar/vender: moeda (bitcoin, ethereum, monero, solana, dogecoin… or ticker), quantidade, valor (total paid/received in R$). "
           "ver: holdings with current value and profit. historico: last operations. remover: deletes a coin. Never asks for keys or seed phrases.",
           "moeda quantidade valor")

# ticker / nome falado → id do CoinGecko
IDS = {"btc": "bitcoin", "bitcoin": "bitcoin", "eth": "ethereum", "ethereum": "ethereum", "ether": "ethereum",
       "xmr": "monero", "monero": "monero", "sol": "solana", "solana": "solana", "doge": "dogecoin", "dogecoin": "dogecoin",
       "ltc": "litecoin", "litecoin": "litecoin", "ada": "cardano", "cardano": "cardano", "xrp": "ripple", "ripple": "ripple",
       "bnb": "binancecoin", "usdt": "tether", "tether": "tether", "usdc": "usd-coin", "trx": "tron", "tron": "tron",
       "dot": "polkadot", "polkadot": "polkadot", "matic": "polygon-ecosystem-token", "pol": "polygon-ecosystem-token",
       "shib": "shiba-inu", "pepe": "pepe", "avax": "avalanche-2", "link": "chainlink", "ton": "the-open-network", "bch": "bitcoin-cash"}
NOMES = {"bitcoin": "Bitcoin", "ethereum": "Ethereum", "monero": "Monero", "solana": "Solana", "dogecoin": "Dogecoin",
         "litecoin": "Litecoin", "cardano": "Cardano", "ripple": "XRP", "binancecoin": "BNB", "tether": "Tether (USDT)",
         "usd-coin": "USDC", "tron": "Tron", "polkadot": "Polkadot", "polygon-ecosystem-token": "Polygon", "shiba-inu": "Shiba Inu",
         "pepe": "Pepe", "avalanche-2": "Avalanche", "chainlink": "Chainlink", "the-open-network": "Toncoin", "bitcoin-cash": "Bitcoin Cash"}
PROIBIDO = re.compile(r"\b(seed|semente|frase de recupera|chave privada|private key|mnemonic|palavras de recupera)", re.I)


def id_de(texto) -> str | None:
    t = norm(texto)
    for w in re.findall(r"[a-z0-9-]+", t):
        if w in IDS:
            return IDS[w]
    return None


def nome(cid: str) -> str:
    return NOMES.get(cid, cid)


def qtd_fmt(q: float) -> str:
    s = f"{q:.8f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def aplicar(posicoes: dict, op: dict) -> dict:
    """Aplica uma operação (compra/venda) às posições; devolve o lucro realizado da venda. Pura (muda o dict)."""
    pos = posicoes.setdefault(op["id"], {"qtd": 0.0, "custo": 0.0, "realizado": 0.0})
    if op["tipo"] == "compra":
        pos["qtd"] += op["qtd"]
        pos["custo"] += op["valor"]
        return {"lucro": 0.0}
    if op["qtd"] > pos["qtd"] + 1e-12:
        raise ValueError(f"você só tem {qtd_fmt(pos['qtd'])} de {nome(op['id'])}")
    medio = pos["custo"] / pos["qtd"] if pos["qtd"] else 0.0
    lucro = op["valor"] - medio * op["qtd"]
    pos["qtd"] -= op["qtd"]
    pos["custo"] -= medio * op["qtd"]
    pos["realizado"] += lucro
    if pos["qtd"] < 1e-12:
        pos["qtd"], pos["custo"] = 0.0, 0.0
    return {"lucro": lucro}


def posicoes_de(ops: list[dict]) -> dict:
    pos: dict = {}
    for op in ops:
        aplicar(pos, op)
    return pos


def _est() -> dict:
    return carregar("carteira_cripto", {"ops": []})


def precos(ids: list[str]) -> dict[str, float]:
    from plugins import mineracao
    return mineracao.precos(ids) if ids else {}


def _operar(p, tipo: str) -> str:
    if PROIBIDO.search(" ".join(str(v) for v in p.values())):
        return "Nunca me diga frase de recuperação ou chave privada: quem tem isso leva a carteira. Eu só preciso da moeda, da quantidade e do valor."
    cid = id_de(p.get("moeda"))
    if not cid:
        return "Qual moeda? (bitcoin, ethereum, monero, solana, dogecoin… ou o código, como BTC)"
    q = numeros(p.get("quantidade"))
    v = numeros(str(p.get("valor") or "").replace(".", "").replace(",", ".")) if re.search(r"\d\.\d{3}", str(p.get("valor") or "")) \
        else numeros(p.get("valor"))
    if not q or q[0] <= 0:
        return f"Quanto de {nome(cid)}?"
    if not v or v[0] <= 0:
        return f"Por quanto em reais, no total, você {'comprou' if tipo == 'compra' else 'vendeu'}?"
    op = {"ts": time.time(), "tipo": tipo, "id": cid, "qtd": q[0], "valor": v[0]}
    e = _est()
    pos = posicoes_de(e["ops"])
    try:
        r = aplicar(pos, dict(op))
    except ValueError as erro:
        return f"Não registrei: {erro}."
    e["ops"].append(op)
    guardar("carteira_cripto", e)
    preco_un = v[0] / q[0]
    if tipo == "compra":
        return (f"Anotado: comprou {qtd_fmt(q[0])} {nome(cid)} por {reais(v[0])} ({reais(preco_un)} cada). "
                f"Agora tem {qtd_fmt(pos[cid]['qtd'])}, custo médio {reais(pos[cid]['custo'] / pos[cid]['qtd'])}.")
    return (f"Anotado: vendeu {qtd_fmt(q[0])} {nome(cid)} por {reais(v[0])}. "
            f"{'Lucro' if r['lucro'] >= 0 else 'Prejuízo'} de {reais(abs(r['lucro']))} sobre o custo médio. Sobrou {qtd_fmt(pos[cid]['qtd'])}.")


def _comprar(p, pl):
    return _operar(p, "compra")


def _vender(p, pl):
    return _operar(p, "venda")


def minerado() -> float:
    """XMR estimado pela mineração (plugin mineracao)."""
    try:
        from plugins import mineracao
        return sum(float(s.get("xmr") or 0) for s in (mineracao._cfg().get("sessoes") or []))
    except Exception:
        return 0.0


def _ver(p, pl):
    pos = {k: v for k, v in posicoes_de(_est()["ops"]).items() if v["qtd"] > 0 or v["realizado"]}
    xmr_min = minerado()
    if not pos and xmr_min <= 0:
        return "A carteira está vazia. Diga, por exemplo: 'comprei 0,002 bitcoin por 1.200 reais'."
    ids = sorted(set(pos) | ({"monero"} if xmr_min > 0 else set()))
    pr = precos(ids)
    linhas, total, custo_total, sem_preco = [], 0.0, 0.0, []
    for cid in ids:
        v = pos.get(cid, {"qtd": 0.0, "custo": 0.0, "realizado": 0.0})
        if v["qtd"] > 0:
            if cid not in pr:
                sem_preco.append(nome(cid))
                linhas.append(f"{nome(cid)}: {qtd_fmt(v['qtd'])} (sem preço agora), custo {reais(v['custo'])}")
                continue
            agora = v["qtd"] * pr[cid]
            dif = agora - v["custo"]
            pct = dif / v["custo"] * 100 if v["custo"] else 0.0
            total += agora
            custo_total += v["custo"]
            linhas.append(f"{nome(cid)}: {qtd_fmt(v['qtd'])} = {reais(agora)} ({'+' if dif >= 0 else '−'}{reais(abs(dif))}, {pct:+.1f}%)")
        if v["realizado"]:
            linhas.append(f"{nome(cid)}: já realizou {'lucro' if v['realizado'] >= 0 else 'prejuízo'} de {reais(abs(v['realizado']))} em vendas")
    if xmr_min > 0:
        val = f" ≈ {reais(xmr_min * pr['monero'])}" if "monero" in pr else ""
        linhas.append(f"Minerado (estimado): {qtd_fmt(xmr_min)} XMR{val}")
    t = "Carteira de cripto: " + "; ".join(linhas) + "."
    if custo_total:
        d = total - custo_total
        t += f" Total {reais(total)} para {reais(custo_total)} investidos: {'lucro' if d >= 0 else 'prejuízo'} de {reais(abs(d))} ({d / custo_total * 100:+.1f}%)."
    return t + " Só controle, não é recomendação."


def _historico(p, pl):
    ops = _est()["ops"][-10:]
    if not ops:
        return "Nenhuma operação registrada."
    return "Últimas operações: " + "; ".join(
        f"{time.strftime('%d/%m', time.localtime(o['ts']))} {'comprou' if o['tipo'] == 'compra' else 'vendeu'} {qtd_fmt(o['qtd'])} "
        f"{nome(o['id'])} por {reais(o['valor'])}" for o in reversed(ops)) + "."


def _remover(p, pl):
    cid = id_de(p.get("moeda"))
    if not cid:
        return "Qual moeda tiro da carteira?"
    e = _est()
    antes = len(e["ops"])
    e["ops"] = [o for o in e["ops"] if o["id"] != cid]
    if len(e["ops"]) == antes:
        return f"Não tem {nome(cid)} na carteira."
    guardar("carteira_cripto", e)
    return f"Tirei {nome(cid)} da carteira ({antes - len(e['ops'])} operação(ões))."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"ver": _ver, "comprar": _comprar, "vender": _vender, "historico": _historico, "remover": _remover}, player)
