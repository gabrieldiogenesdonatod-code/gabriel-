"""
Perfil de gosto do dono (fork PT-BR 2.0). Começa com "_": não é ferramenta.

O JARVIS vai aprendendo o que você curte, sem perguntar: músicas que você
pede, curte ou pula, o que toca no DJ, vídeos que você resume, jogos que você
joga e as ofertas que você aceita ou recusa. O companheiro usa isso para
oferecer coisas na hora certa; a música usa para sugerir.

Pesos esquecem devagar (meia-vida de 60 dias): o gosto de hoje pesa mais.
Tudo fica em memory/gosto.json, no seu PC.
"""

from __future__ import annotations

import threading
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json

ARQ = MEMORIA / "gosto.json"
MEIA_VIDA_DIAS = 60
PESOS = {"tocou": 1.0, "pediu": 2.0, "curtiu": 5.0, "pulou": -2.0, "recusou": -3.0, "aceitou": 3.0, "viu": 1.0,
         "jogou": 1.0}
_lock = threading.Lock()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("eventos", [])        # {ts, tipo (musica|video|jogo|oferta), item, extra, acao}
    d.setdefault("nao_gosta", [])
    return d


def artista_de(faixa: str) -> str:
    """'Kaiser - Impossível' → 'Kaiser' (pura)."""
    partes = [p.strip() for p in str(faixa or "").split(" - ")]
    return partes[0] if len(partes) >= 2 else ""


def registrar(tipo: str, item: str, acao: str = "tocou", extra: str = "", agora: float | None = None) -> None:
    item = str(item or "").strip()
    if not item:
        return
    with _lock:
        d = dados()
        d["eventos"] = (d["eventos"] + [{"ts": agora or time.time(), "tipo": tipo, "item": item[:200],
                                          "extra": str(extra)[:120], "acao": acao}])[-3000:]
        gravar_json(ARQ, d)


def peso(ev: dict, agora: float) -> float:
    idade_dias = max(0.0, (agora - ev["ts"]) / 86400)
    return PESOS.get(ev.get("acao", "tocou"), 1.0) * 0.5 ** (idade_dias / MEIA_VIDA_DIAS)


def ranking(eventos: list[dict], tipo: str, chave=None, agora: float | None = None, n: int = 10) -> list[tuple[str, float]]:
    """Itens mais pesados de um tipo (pura). `chave` transforma o item (ex.: faixa → artista)."""
    agora = agora or time.time()
    soma: dict[str, float] = {}
    nomes: dict[str, str] = {}
    for ev in eventos:
        if ev.get("tipo") != tipo:
            continue
        nome = chave(ev["item"]) if chave else ev["item"]
        if not nome:
            continue
        k = _dobrar(nome)
        nomes.setdefault(k, nome)
        soma[k] = soma.get(k, 0.0) + peso(ev, agora)
    return [(nomes[k], round(v, 2)) for k, v in sorted(soma.items(), key=lambda x: -x[1]) if v > 0][:n]


def top_artistas(n: int = 8) -> list[str]:
    d = dados()
    rank = ranking(d["eventos"], "musica", artista_de, n=n)
    return [a for a, _p in rank if _dobrar(a) not in {_dobrar(x) for x in d["nao_gosta"]}]


def ja_ofereceu(item: str, dias: float = 14) -> bool:
    limite = time.time() - dias * 86400
    k = _dobrar(item)
    return any(e["tipo"] == "oferta" and _dobrar(e["item"]) == k and e["ts"] >= limite for e in dados()["eventos"])


def taxa_aceite(dias: float = 30) -> float | None:
    limite = time.time() - dias * 86400
    resp = [e["acao"] for e in dados()["eventos"] if e["tipo"] == "oferta" and e["ts"] >= limite
            and e["acao"] in ("aceitou", "recusou")]
    return (resp.count("aceitou") / len(resp)) if resp else None


def nao_gosto(item: str) -> None:
    with _lock:
        d = dados()
        if _dobrar(item) not in {_dobrar(x) for x in d["nao_gosta"]}:
            d["nao_gosta"].append(item.strip()[:100])
        gravar_json(ARQ, d)


def resumo(n: int = 6) -> str:
    """Texto curto do gosto, para os pedidos à IA."""
    d = dados()
    partes = []
    art = top_artistas(n)
    if art:
        partes.append("artistas: " + ", ".join(art))
    faixas = ranking(d["eventos"], "musica", n=n)
    if faixas:
        partes.append("músicas: " + ", ".join(f for f, _p in faixas))
    videos = ranking(d["eventos"], "video", n=n)
    if videos:
        partes.append("vídeos que assistiu: " + "; ".join(v for v, _p in videos))
    jogos = ranking(d["eventos"], "jogo", n=n)
    if jogos:
        partes.append("jogos: " + ", ".join(j for j, _p in jogos))
    if d["nao_gosta"]:
        partes.append("NÃO gosta de: " + ", ".join(d["nao_gosta"][-10:]))
    return "; ".join(partes)
