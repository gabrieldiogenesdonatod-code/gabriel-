"""Cérebro do MINER AI: rentabilidade, veredito honesto, recomendações e aprendizado com o histórico do SEU PC.

Tudo o que sai daqui é SIMULAÇÃO (o que poderia render), nunca dinheiro. O cérebro não promete lucro: se o
gasto de luz passa do ganho esperado, ele diz "não compensa" — que é o caso normal num PC comum.
"""
from __future__ import annotations

import os
from statistics import mean

MOEDAS = {
    "btc": {"nome": "Bitcoin", "algo": "SHA-256d", "recompensa": 3.125, "fator": 2.0 ** 32, "cg": "bitcoin", "motor": "btc",
            "hs_thread": 1.0e6, "dif_aprox": 1.3e14},
    "xmr": {"nome": "Monero", "algo": "RandomX", "recompensa": 0.6, "fator": 1.0, "cg": "monero", "motor": "xmrig",
            "hs_thread": 300.0, "dif_aprox": 6.0e11},
}
SO_ASIC = {"ltc": "Litecoin: Scrypt, dominado por máquinas ASIC.", "doge": "Dogecoin: Scrypt (minerada junto com a Litecoin), ASIC.",
           "bch": "Bitcoin Cash: SHA-256, só ASIC.", "eth": "Ethereum: não se minera mais desde 2022.",
           "etc": "Ethereum Classic: placa de vídeo dedicada."}


def ganho_dia(hashrate: float, dificuldade: float, recompensa: float, fator: float) -> float:
    return 0.0 if hashrate <= 0 or dificuldade <= 0 else hashrate * 86400 / (dificuldade * fator) * recompensa


def rentabilidade(moeda: str, hashrate: float, dificuldade: float, preco: float | None, watts: float, tarifa: float) -> dict:
    """SIMULAÇÃO de um dia minerando. Pura."""
    m = MOEDAS[moeda]
    moedas = ganho_dia(hashrate, dificuldade, m["recompensa"], m["fator"])
    luz = max(0.0, watts) * 24 / 1000 * max(0.0, tarifa)
    r = {"tipo": "simulacao", "moeda": moeda, "hashrate": hashrate, "moedas_dia": moedas, "reais_dia": moedas * preco if preco else None,
         "luz_dia": luz, "preco": preco}
    r["saldo_dia"] = None if r["reais_dia"] is None else r["reais_dia"] - luz
    r["compensa"] = None if r["saldo_dia"] is None else r["saldo_dia"] > 0
    blocos_dia = hashrate * 86400 / (dificuldade * m["fator"]) if dificuldade else 0
    r["chance_bloco_dia"] = blocos_dia
    r["anos_por_bloco"] = (1 / blocos_dia / 365) if blocos_dia else float("inf")
    r["luz_por_real_ganho"] = (luz / r["reais_dia"]) if r["reais_dia"] else float("inf")
    return r


def veredito(r: dict) -> str:
    """Frase honesta sobre a simulação. Pura."""
    nome = MOEDAS[r["moeda"]]["nome"]
    if r["reais_dia"] is None:
        return f"{nome}: sem preço agora, não dá para saber se compensa."
    if r["moeda"] == "btc":
        anos = r["anos_por_bloco"]
        quando = f"{anos / 1e9:,.0f} bilhões de anos".replace(",", ".") if anos >= 1e9 else f"{anos:,.0f} anos".replace(",", ".")
        return (f"Bitcoin na pool solo é LOTERIA: em média 1 bloco a cada {quando} neste PC. O valor esperado é "
                f"{_r(r['reais_dia'])}/dia contra {_r(r['luz_dia'])}/dia de luz. Não compensa como renda; só se você quiser o bilhete.")
    if r["compensa"]:
        return f"{nome}: estimativa de sobra de {_r(r['saldo_dia'])}/dia (ganho {_r(r['reais_dia'])}, luz {_r(r['luz_dia'])}). Pode mudar com preço e dificuldade."
    return (f"{nome}: NÃO compensa agora — ganharia {_r(r['reais_dia'])}/dia e gastaria {_r(r['luz_dia'])}/dia de luz "
            f"(prejuízo de {_r(-r['saldo_dia'])}/dia).")


def _r(v: float) -> str:
    if v is None:
        return "?"
    if 0 < abs(v) < 0.01:
        return "menos de R$ 0,01"
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + "R$ " + s


# ─────────────────────────────────────────────────────────── aprendizado ───
def hashrate_aprendido(historico: list[dict], motor: str, threads: int, carga: float) -> float | None:
    """Média do que ESTE PC realmente fez com essa configuração (≥ 3 amostras), proporcional à carga. Pura."""
    xs = [a["hs"] / max(1e-9, a["carga"]) * carga for a in historico
          if a.get("motor") == motor and a.get("threads") == threads and a.get("hs", 0) > 0 and a.get("carga", 0) > 0]
    return mean(xs) if len(xs) >= 3 else None


def melhor_configuracao(historico: list[dict], motor: str, temp_max: float) -> dict | None:
    """Das configurações testadas, a que faz mais hash por watt sem passar perto do limite de temperatura. Pura."""
    grupos: dict = {}
    for a in historico:
        if a.get("motor") != motor or not a.get("hs") or not a.get("watts"):
            continue
        grupos.setdefault((a["threads"], a["carga"]), []).append(a)
    melhores = []
    for (th, carga), xs in grupos.items():
        if len(xs) < 3:
            continue
        temps = [x["temp"] for x in xs if x.get("temp") is not None]
        if temps and max(temps) >= temp_max - 5:
            continue
        hs, w = mean(x["hs"] for x in xs), mean(x["watts"] for x in xs)
        melhores.append({"threads": th, "carga": carga, "hs": hs, "watts": w, "hs_por_watt": hs / w if w else 0,
                         "temp": max(temps) if temps else None, "amostras": len(xs)})
    return max(melhores, key=lambda m: m["hs_por_watt"]) if melhores else None


def recomendar(cfg: dict, historico: list[dict], simulacoes: dict[str, dict]) -> list[str]:
    """Conselhos concretos, do mais importante para o menos. Pura."""
    dicas = []
    conhecidas = [s["compensa"] for s in simulacoes.values() if s.get("compensa") is not None]
    if not conhecidas and simulacoes:
        dicas.append("Sem preço agora (internet?): não dá para dizer se compensa. Tente de novo daqui a pouco.")
    elif conhecidas and not any(conhecidas):
        dicas.append("Com a sua tarifa de luz, nenhuma moeda compensa neste PC. O mais econômico é não minerar; "
                     "se for minerar para aprender ou pelo bilhete, use o modo econômico.")
    xmr = simulacoes.get("xmr")
    btc = simulacoes.get("btc")
    if xmr and btc and xmr.get("reais_dia") and btc.get("reais_dia") is not None:
        vezes = xmr["reais_dia"] / max(btc["reais_dia"], 1e-12)
        if vezes > 10:
            dicas.append(f"Monero (pelo XMRig) rende uns {vezes:,.0f}× mais que Bitcoin no processador.".replace(",", "."))
    if not cfg.get("watts_medidos"):
        dicas.append("O consumo é estimado pelo TDP. Com um medidor de tomada (uns R$ 40) a conta de energia fica exata: "
                     "meça com e sem minerar e ponha a diferença em 'watts_medidos'.")
    for motor in ("btc", "xmrig"):
        m = melhor_configuracao(historico, motor, float(cfg.get("temperatura_max") or 80))
        if m:
            dicas.append(f"No motor {motor}, a configuração mais eficiente que você já testou foi {m['threads']} núcleo(s) a "
                         f"{m['carga']:.0f}% ({m['hs']:,.0f} H/s, {m['watts']:.1f} W).".replace(",", "."))
    if not cfg.get("horarios"):
        dicas.append("Se a sua tarifa for branca (mais barata à noite), configure horários, por exemplo 22:00-07:00.")
    if float(cfg.get("temperatura_max") or 80) > 85:
        dicas.append("Limite de temperatura acima de 85 °C encurta a vida do notebook; 80 °C é mais seguro.")
    return dicas


def hashrate_para(moeda: str, cfg: dict, historico: list[dict], threads: int, carga: float) -> tuple[float, bool]:
    """(hashrate, medido?) — o medido de verdade quando há histórico; senão a estimativa."""
    m = MOEDAS[moeda]
    aprendido = hashrate_aprendido(historico, m["motor"], threads, carga if m["motor"] == "btc" else 100.0)
    if aprendido:
        return aprendido, True
    frac = (carga / 100) if m["motor"] == "btc" else 1.0
    return m["hs_thread"] * threads * frac, False


def nucleos() -> int:
    return os.cpu_count() or 2
