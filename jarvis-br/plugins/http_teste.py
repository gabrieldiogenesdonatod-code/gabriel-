"""Teste de HTTP (2.19): faz um GET ou POST numa rota (ótimo para a sua API local) e mostra status, tempo e a resposta."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from plugins._lote2 import P, rodar

PLUGIN = P("http_teste", "HTTP request tester for your APIs: GET/POST a URL, shows status, time, content type and body preview (pretty JSON).",
           "get | post | cabecalhos",
           "url (http/https; 'localhost:8000/rota' ok). post: corpo (JSON string). cabecalho: 'Nome: valor' (e.g. Authorization).",
           "url corpo cabecalho")


def pedir(url: str, metodo: str = "GET", corpo: str = "", cabecalho: str = "", timeout: float = 15) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    hs = {"User-Agent": "JARVIS-http-teste"}
    if cabecalho and ":" in cabecalho:
        k, v = cabecalho.split(":", 1)
        hs[k.strip()] = v.strip()
    dados = corpo.encode() if metodo == "POST" else None
    if dados is not None:
        hs.setdefault("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=dados, headers=hs, method=metodo), timeout=timeout) as r:
            st, cab, txt = r.status, dict(r.headers), r.read(200_000)
    except urllib.error.HTTPError as e:
        st, cab, txt = e.code, dict(e.headers), e.read(200_000)
    return {"status": st, "ms": (time.time() - t0) * 1000, "cabecalhos": cab, "corpo": txt.decode(errors="replace")}


def _go(p, pl):
    a = p["action"]
    r = pedir(str(p.get("url") or "").strip(), "POST" if a == "post" else "GET", str(p.get("corpo") or ""), str(p.get("cabecalho") or ""))
    if a == "cabecalhos":
        return "\n".join(f"{k}: {v}" for k, v in r["cabecalhos"].items())
    corpo = r["corpo"]
    try:
        corpo = json.dumps(json.loads(corpo), indent=2, ensure_ascii=False)
    except ValueError:
        pass
    tipo = r["cabecalhos"].get("Content-Type", "?")
    return f"Status {r['status']} em {r['ms']:.0f} ms, {tipo}, {len(r['corpo'])} caracteres.\n{corpo[:900]}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"get": _go, "post": _go, "cabecalhos": _go}, player, "HTTP")
