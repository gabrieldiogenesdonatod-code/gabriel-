"""
Vigia de preço (fork PT-BR 1.4).

    "Jarvis, me avisa quando a RTX 3060 baixar de R$ 1.500"
    "Jarvis, vigia o preço deste link: https://www.kabum.com.br/produto/…"
    "Jarvis, como estão os preços que você está vigiando?"

Confere UMA vez por dia (e quando você pedir) e avisa por voz, no registro e
no celular (push do ntfy, se configurado) quando o preço fica abaixo do alvo.
Avisa de novo só se o preço subir e cair outra vez.

DE ONDE VEM O PREÇO
    • com link: lê a página da loja (dados estruturados do produto, metatags
      de preço ou o maior destaque em R$);
    • sem link: busca no Mercado Livre (API pública); se ela não responder,
      usa a pesquisa com fontes do modelo de IA; sem IA, a busca DuckDuckGo.
    Anúncios de peças/acessórios ("cooler para", "suporte", "caixa vazia") são
    ignorados, e o preço precisa conter as palavras do produto no título.

Histórico em memory/vigia_preco.json.
"""

from __future__ import annotations

import html
import json
import re
import statistics
import threading
import time
import unicodedata
import urllib.parse
from datetime import datetime

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "vigia_preco",
    "brief": "Price watcher: daily check, warns by voice and phone when below the target price.",
    "description": (
        "Price watcher for products. action='adicionar' with produto and preco (target in BRL; 'warn me "
        "when the RTX 3060 drops below 1500') and optional url (a store page); 'verificar' (check now), "
        "'listar' (current prices), 'remover' (produto or id), 'historico' (produto). Checks once a day "
        "and warns by voice and phone."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "adicionar | verificar | listar | remover | historico"},
            "produto": {"type": "STRING"}, "preco": {"type": "NUMBER"}, "url": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

_ARQ = MEMORIA / "vigia_preco.json"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/124.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}
_iniciado = threading.Event()
_lock = threading.Lock()


# ── preços (puros) ─────────────────────────────────────────────────────────────
def valor_br(texto: str) -> float | None:
    """'R$ 1.499,90' / '1499.90' / '1.499' → 1499.9."""
    t = re.sub(r"[^\d,.]", "", str(texto or ""))
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") == 1 and len(t.split(".")[1]) == 3:
        t = t.replace(".", "")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        v = float(t)
        return v if 0 < v < 10_000_000 else None
    except ValueError:
        return None


def preco_da_pagina(pagina: str) -> float | None:
    # 1) JSON-LD do produto
    for bloco in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', pagina, re.S | re.I):
        try:
            dados = json.loads(html.unescape(bloco.strip()))
        except Exception:
            continue
        pilha = [dados]
        while pilha:
            d = pilha.pop()
            if isinstance(d, list):
                pilha.extend(d)
            elif isinstance(d, dict):
                ofertas = d.get("offers")
                if ofertas:
                    pilha.append(ofertas)
                for k in ("price", "lowPrice"):
                    if k in d and (d.get("priceCurrency", "BRL") in ("BRL", "") or "@type" in d):
                        v = valor_br(str(d[k]).replace(".", ",") if re.fullmatch(r"\d+\.\d{1,2}", str(d[k])) else d[k])
                        if v:
                            return v
                pilha.extend(v for v in d.values() if isinstance(v, (dict, list)))
    # 2) metatags
    for rx in (r'property=["\']product:price:amount["\'][^>]*content=["\']([\d.,]+)',
               r'content=["\']([\d.,]+)["\'][^>]*property=["\']product:price:amount',
               r'itemprop=["\']price["\'][^>]*content=["\']([\d.,]+)'):
        m = re.search(rx, pagina, re.I)
        if m:
            bruto = m.group(1)
            v = valor_br(bruto.replace(".", ",") if re.fullmatch(r"\d+\.\d{1,2}", bruto) else bruto)
            if v:
                return v
    # 3) o "R$" que mais aparece entre os maiores destaques
    valores = [valor_br(x) for x in re.findall(r"R\$\s*(?:&nbsp;)?\s*([\d.]{1,9},\d{2})", pagina)]
    valores = [v for v in valores if v]
    if valores:
        return statistics.mode(valores) if len(valores) > 2 else min(valores)
    return None


_ACESSORIO = re.compile(r"\b(suporte|cabo|adesivo|caixa vazia|capa|pel[ií]cula|cooler para|para placa|"
                        r"backplate|kit de|pe[çc]a de reposi|defeito|n[aã]o liga|quebrad|sucata)\b", re.I)


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def relevante(titulo: str, produto: str) -> bool:
    tt = _dobrar(titulo)
    palavras = [w for w in re.findall(r"[a-z0-9]+", _dobrar(produto)) if len(w) >= 2 or w.isdigit()]
    return all(w in tt for w in palavras) and not _ACESSORIO.search(titulo)


def melhor_oferta(ofertas: list[dict], produto: str) -> dict | None:
    """ofertas: [{titulo, preco, link, loja}] → a mais barata entre as relevantes,
    descartando preços absurdamente baixos (menos de 40% da mediana)."""
    boas = [o for o in ofertas if o.get("preco") and relevante(o.get("titulo", ""), produto)]
    if not boas:
        return None
    med = statistics.median(o["preco"] for o in boas)
    boas = [o for o in boas if o["preco"] >= 0.4 * med]
    return min(boas, key=lambda o: o["preco"]) if boas else None


# ── fontes ─────────────────────────────────────────────────────────────────────
def _get(url: str, timeout: float = 20) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(4_000_000).decode("utf-8", "replace")


def da_url(url: str) -> dict | None:
    pagina = _get(url)
    v = preco_da_pagina(pagina)
    if not v:
        return None
    m = re.search(r"<title[^>]*>(.*?)</title>", pagina, re.I | re.S)
    loja = urllib.parse.urlparse(url).netloc.replace("www.", "")
    return {"preco": v, "titulo": html.unescape(m.group(1).strip())[:120] if m else "", "link": url, "loja": loja}


def mercado_livre(produto: str) -> list[dict]:
    url = "https://api.mercadolibre.com/sites/MLB/search?" + urllib.parse.urlencode({"q": produto, "limit": 30})
    dados = json.loads(_get(url))
    return [{"titulo": r.get("title", ""), "preco": float(r.get("price") or 0), "link": r.get("permalink", ""),
             "loja": "Mercado Livre"} for r in dados.get("results", []) if r.get("price")]


def busca_ia(produto: str) -> list[dict]:
    from plugins import _ia
    if not _ia.disponivel():
        return []
    from core import gemini
    resp = gemini.call(f"Pesquise o menor preço À VISTA, em reais, do produto NOVO '{produto}' em lojas brasileiras "
                       "confiáveis hoje. Responda SÓ JSON: [{\"titulo\": \"...\", \"preco\": 1234.56, \"loja\": \"...\", "
                       "\"link\": \"...\"}] com até 5 ofertas.", tier=gemini.SEARCH,
                       config={"tools": [{"google_search": {}}]}, timeout_ms=40_000)
    texto = ""
    try:
        for parte in resp.candidates[0].content.parts:
            texto += getattr(parte, "text", "") or ""
    except Exception:
        texto = getattr(resp, "text", "") or ""
    texto = texto[texto.find("["): texto.rfind("]") + 1]
    try:
        return [{"titulo": str(o.get("titulo", produto)), "preco": float(o["preco"]), "loja": str(o.get("loja", "")),
                 "link": str(o.get("link", ""))} for o in json.loads(texto) if o.get("preco")]
    except Exception:
        return []


def busca_ddg(produto: str) -> list[dict]:
    from actions.ddg_isolado import buscar                     # 2.8.2: processo separado
    saida = []
    if True:
        for r in buscar("text", f"{produto} preço", 15, region="br-pt"):
            for bruto in re.findall(r"R\$\s*([\d.]{1,9},\d{2})", f"{r.get('title', '')} {r.get('body', '')}"):
                v = valor_br(bruto)
                if v:
                    saida.append({"titulo": f"{r.get('title', '')} {r.get('body', '')}", "preco": v,
                                  "link": r.get("href", ""), "loja": urllib.parse.urlparse(r.get("href", "")).netloc})
    return saida


def consultar(v: dict) -> dict | None:
    if v.get("url"):
        return da_url(v["url"])
    for fonte in (mercado_livre, busca_ia, busca_ddg):
        try:
            o = melhor_oferta(fonte(v["produto"]), v["produto"])
            if o:
                o["fonte"] = fonte.__name__
                return o
        except Exception as e:
            print(f"[VigiaPreco] {fonte.__name__}: {e}")
    return None


# ── vigias ─────────────────────────────────────────────────────────────────────
def carregar() -> list[dict]:
    d = ler_json(_ARQ, [])
    return d if isinstance(d, list) else []


def verificar(player=None, so_vencidos: bool = False) -> list[str]:
    from plugins._notificar import notificar
    with _lock:
        vigias = carregar()
        mensagens = []
        for v in vigias:
            if so_vencidos and time.time() - float(v.get("conferido") or 0) < 20 * 3600:
                continue
            try:
                o = consultar(v)
            except Exception as e:
                o, v["erro"] = None, str(e)[:150]
            v["conferido"] = time.time()
            if not o:
                continue
            v["erro"] = ""
            v.setdefault("historico", []).append({"ts": time.time(), "preco": o["preco"], "loja": o.get("loja", "")})
            v["historico"] = v["historico"][-120:]
            v["ultimo"] = o
            if o["preco"] <= v["alvo"]:
                if not v.get("avisado"):
                    v["avisado"] = True
                    msg = (f"{v['produto']} baixou: R$ {o['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                           + f" na {o.get('loja') or 'loja'} (seu alvo: R$ {v['alvo']:,.0f}).".replace(",", "."))
                    notificar(player, msg, titulo="Vigia de preço", etiqueta="PREÇO", prioridade="high")
                    mensagens.append(msg)
            elif v["alvo"] and o["preco"] > v["alvo"] * 1.02:
                v["avisado"] = False
        gravar_json(_ARQ, vigias)
    return mensagens


def _laco(player) -> None:
    time.sleep(240)
    while True:
        try:
            verificar(player, so_vencidos=True)
        except Exception as e:
            print(f"[VigiaPreco] {e}")
        time.sleep(3600)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="vigia_preco").start()


def _reais(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _achar(vigias: list[dict], termo: str) -> dict | None:
    t = _dobrar(termo)
    return next((v for v in vigias if v["id"] == termo.strip() or (t and t in _dobrar(v["produto"]))), None)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        if acao == "adicionar":
            produto = str(p.get("produto") or "").strip()
            url = str(p.get("url") or "").strip()
            alvo = valor_br(str(p.get("preco") or "")) if not isinstance(p.get("preco"), (int, float)) else float(p["preco"])
            if not produto and not url:
                return "Qual produto devo vigiar?"
            with _lock:
                vigias = carregar()
                v = {"id": str(max([int(x["id"]) for x in vigias] + [0]) + 1), "produto": produto or url,
                     "alvo": float(alvo or 0), "url": url, "criado": datetime.now().isoformat(timespec="minutes"),
                     "historico": [], "avisado": False}
                vigias.append(v)
                gravar_json(_ARQ, vigias)
            try:
                o = consultar(v)
            except Exception as e:
                o = None
                print(f"[VigiaPreco] {e}")
            if o:
                with _lock:
                    vigias = carregar()
                    for x in vigias:
                        if x["id"] == v["id"]:
                            x.update(ultimo=o, conferido=time.time())
                            x["historico"].append({"ts": time.time(), "preco": o["preco"], "loja": o.get("loja", "")})
                    gravar_json(_ARQ, vigias)
                agora = f" Hoje o menor que achei é {_reais(o['preco'])} ({o.get('loja', '')})."
                if alvo and o["preco"] <= alvo:
                    agora += " Já está abaixo do seu alvo!"
            else:
                agora = " Ainda não consegui ler o preço; confiro de novo amanhã."
            return f"Vigiando {v['produto']}" + (f" abaixo de {_reais(alvo)}" if alvo else "") + "." + agora
        vigias = carregar()
        if acao == "verificar":
            msgs = verificar(player)
            vigias = carregar()
            if msgs:
                return " ".join(msgs)
            return "Conferi: nenhum preço abaixo do alvo. " + "; ".join(
                f"{v['produto']}: {_reais(v['ultimo']['preco'])}" for v in vigias if v.get("ultimo"))[:400]
        if acao == "remover":
            alvo = _achar(vigias, str(p.get("produto") or ""))
            if not alvo:
                return "Não achei esse vigia."
            gravar_json(_ARQ, [v for v in vigias if v["id"] != alvo["id"]])
            return f"Parei de vigiar {alvo['produto']}."
        if acao == "historico":
            alvo = _achar(vigias, str(p.get("produto") or ""))
            if not alvo or not alvo.get("historico"):
                return "Ainda não tenho histórico desse produto."
            h = alvo["historico"]
            menor = min(h, key=lambda x: x["preco"])
            mostrar(player, f"PREÇO — {alvo['produto']}", "\n".join(
                f"{datetime.fromtimestamp(x['ts']):%d/%m %H:%M}  {_reais(x['preco']):>14}  {x.get('loja', '')}" for x in h[-60:]))
            return (f"{alvo['produto']}: agora {_reais(h[-1]['preco'])}; o menor desde que comecei foi "
                    f"{_reais(menor['preco'])} em {datetime.fromtimestamp(menor['ts']):%d/%m}.")
        if not vigias:
            return "Não estou vigiando nenhum preço. Diga, por exemplo: me avisa quando a RTX 3060 baixar de 1500 reais."
        linhas = []
        for v in vigias:
            u = v.get("ultimo")
            linhas.append(f"[{v['id']}] {v['produto']}: alvo {_reais(v['alvo'])}, "
                          + (f"agora {_reais(u['preco'])} ({u.get('loja', '')})" if u else "ainda sem preço")
                          + (f" — erro: {v['erro']}" if v.get("erro") else ""))
        mostrar(player, "VIGIA DE PREÇO", "\n".join(linhas))
        return "; ".join(linhas[:4]) + "."
    except Exception as e:
        return f"O vigia de preço falhou: {e}"
