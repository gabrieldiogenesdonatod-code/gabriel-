"""
Ajudante de internet dos plugins da 2.16 — só a biblioteca padrão (urllib),
para não depender de pacote nenhum. Começa com "_": não vira ferramenta.

    get_json(url, params=None, headers=None)      → dict/list (ou levanta ErroWeb)
    post_json(url, corpo, headers=None)
    get_texto(url)                                → (texto da página, título)

Os testes trocam `_abrir` por uma função falsa.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

AGENTE = "JARVIS-BR/2.16 (assistente pessoal)"


class ErroWeb(Exception):
    def __init__(self, msg: str, status: int = 0):
        super().__init__(msg)
        self.status = status


def _abrir(req: urllib.request.Request, timeout: float) -> tuple[int, bytes, str]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"", e.headers.get("Content-Type", "") if e.headers else ""
    except Exception as e:                                   # sem internet, DNS, tempo esgotado
        raise ErroWeb(f"sem conexão ({e.__class__.__name__})") from e


def _req(metodo: str, url: str, params=None, headers=None, corpo: bytes | None = None, timeout: float = 15):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = {"User-Agent": AGENTE, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"}
    h.update(headers or {})
    status, dados, tipo = _abrir(urllib.request.Request(url, data=corpo, headers=h, method=metodo), timeout)
    return status, dados, tipo


def get_json(url: str, params=None, headers=None, timeout: float = 15):
    status, dados, _t = _req("GET", url, params, headers, timeout=timeout)
    if status == 404:
        raise ErroWeb("não encontrado", 404)
    if status >= 400:
        raise ErroWeb(f"o serviço respondeu {status}", status)
    try:
        return json.loads(dados.decode("utf-8", "replace"))
    except ValueError as e:
        raise ErroWeb("resposta inválida") from e


def post_json(url: str, corpo, headers=None, timeout: float = 20, form: bool = False):
    if form:
        dados = urllib.parse.urlencode(corpo).encode()
        h = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        dados = json.dumps(corpo).encode()
        h = {"Content-Type": "application/json"}
    h.update(headers or {})
    status, resp, _t = _req("POST", url, None, h, dados, timeout)
    if status >= 400:
        raise ErroWeb(f"o serviço respondeu {status}: {resp[:200].decode('utf-8', 'replace')}", status)
    try:
        return json.loads(resp.decode("utf-8", "replace") or "null")
    except ValueError as e:
        raise ErroWeb("resposta inválida") from e


def limpar_html(html: str) -> tuple[str, str]:
    """(texto, título) de uma página HTML (pura)."""
    titulo = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        titulo = re.sub(r"\s+", " ", m.group(1)).strip()
    try:
        from bs4 import BeautifulSoup
        sopa = BeautifulSoup(html, "html.parser")
        for t in sopa(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"]):
            t.decompose()
        corpo = sopa.find("article") or sopa.find("main") or sopa.body or sopa
        texto = corpo.get_text("\n")
    except Exception:
        texto = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
        texto = re.sub(r"<[^>]+>", "\n", texto)
    import html as _h
    linhas = [re.sub(r"\s+", " ", _h.unescape(x)).strip() for x in texto.splitlines()]
    return "\n".join(x for x in linhas if len(x) > 30), titulo


def get_texto(url: str, timeout: float = 20, limite: int = 60_000) -> tuple[str, str]:
    status, dados, tipo = _req("GET", url, timeout=timeout)
    if status >= 400:
        raise ErroWeb(f"a página respondeu {status}", status)
    html = dados[:2_000_000].decode("utf-8", "replace")
    if "html" not in tipo and "<html" not in html[:2000].lower():
        return html[:limite], url
    texto, titulo = limpar_html(html)
    return texto[:limite], titulo or url
