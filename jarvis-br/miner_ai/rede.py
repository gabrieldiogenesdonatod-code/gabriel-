"""Dados de fora do PC (só leitura, sem chave de API): preço, dificuldade das redes e saldos PÚBLICOS.
Cada resposta diz de onde veio e quando; se a internet falhar, devolve None — nunca inventa um número."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "MINER-AI/1.0 (JARVIS BR)"}
_cache: dict = {}


def get(url: str, params: dict | None = None, timeout: float = 10, cache_s: float = 300):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    agora = time.time()
    if url in _cache and agora - _cache[url][0] < cache_s:
        return _cache[url][1]
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        txt = r.read().decode("utf-8", "replace")
    try:
        dado = json.loads(txt)
    except ValueError:
        dado = txt.strip()
    _cache[url] = (agora, dado)
    return dado


def precos_brl(ids: list[str]) -> dict[str, float]:
    """{'bitcoin': 512345.0, 'monero': 1600.0} pelo CoinGecko. Moeda que falhar fica de fora."""
    try:
        d = get("https://api.coingecko.com/api/v3/simple/price", {"ids": ",".join(ids), "vs_currencies": "brl"})
        return {k: float(v["brl"]) for k, v in d.items() if isinstance(v, dict) and "brl" in v}
    except Exception:
        return {}


def dificuldade(moeda: str) -> dict | None:
    """{'valor', 'fonte', 'ts'} ou None."""
    fontes = {"btc": [("https://blockchain.info/q/getdifficulty", lambda d: float(d)),
                      ("https://mempool.space/api/v1/mining/hashrate/3d", lambda d: float(d["currentDifficulty"]))],
              "xmr": [("https://xmrchain.net/api/networkinfo", lambda d: float(d["data"]["difficulty"])),
                      ("https://moneroblocks.info/api/get_stats/", lambda d: float(d["difficulty"]))]}
    for url, ler in fontes.get(moeda, []):
        try:
            v = ler(get(url, cache_s=1800))
            if v:
                return {"valor": v, "fonte": urllib.parse.urlparse(url).netloc, "ts": time.time()}
        except Exception:
            continue
    return None


def saldo_btc(endereco: str) -> dict | None:
    """Saldo CONFIRMADO na blockchain de um endereço público (Blockstream). Só leitura."""
    try:
        d = get(f"https://blockstream.info/api/address/{endereco}", cache_s=600)
        c, m = d["chain_stats"], d["mempool_stats"]
        return {"confirmado": (c["funded_txo_sum"] - c["spent_txo_sum"]) / 1e8,
                "pendente": (m["funded_txo_sum"] - m["spent_txo_sum"]) / 1e8, "fonte": "blockstream.info", "ts": time.time()}
    except Exception:
        return None


def saldo_pool_xmr(endereco: str) -> dict | None:
    """Na pool SupportXMR: já pago (confirmado) e devido ainda não pago (pendente). Só leitura."""
    try:
        d = get(f"https://supportxmr.com/api/miner/{endereco}/stats", cache_s=600)
        return {"confirmado": float(d.get("amtPaid") or 0) / 1e12, "pendente": float(d.get("amtDue") or 0) / 1e12,
                "fonte": "supportxmr.com", "ts": time.time()}
    except Exception:
        return None
