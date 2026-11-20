"""
Spotify (Web API) para o J.A.R.V.I.S BR 2.0. Começa com "_": não é ferramenta.

Login com PKCE: não precisa de "client secret", só do Client ID de um app que
você cria em https://developer.spotify.com/dashboard (Redirect URI:
http://127.0.0.1:8888/callback). O token fica em config/spotify_token.json
(nunca vai para o ZIP). Controlar o player (tocar, pular, volume) exige
Spotify Premium; sem Premium, o JARVIS abre a música no app e você dá o play.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from plugins._comum import CONFIG, abrir_no_sistema, ler_json, gravar_json

ARQ_TOKEN = CONFIG / "spotify_token.json"
REDIRECT = "http://127.0.0.1:8888/callback"
ESCOPOS = ("user-read-playback-state user-modify-playback-state user-read-currently-playing "
           "user-library-modify user-library-read user-top-read user-read-recently-played playlist-read-private")
API = "https://api.spotify.com/v1"


class ErroSpotify(Exception):
    def __init__(self, codigo: int, msg: str):
        super().__init__(msg)
        self.codigo = codigo


def par_pkce() -> tuple[str, str]:
    """(verifier, challenge) do PKCE (pura, a não ser pelo aleatório)."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def url_login(client_id: str, challenge: str, estado: str) -> str:
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": REDIRECT, "scope": ESCOPOS,
        "code_challenge_method": "S256", "code_challenge": challenge, "state": estado})


def _post_token(dados: dict) -> dict:
    req = urllib.request.Request("https://accounts.spotify.com/api/token", data=urllib.parse.urlencode(dados).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _guardar(tok: dict, client_id: str) -> None:
    antigo = ler_json(ARQ_TOKEN, {}) or {}
    gravar_json(ARQ_TOKEN, {"client_id": client_id, "access_token": tok["access_token"],
                            "refresh_token": tok.get("refresh_token") or antigo.get("refresh_token", ""),
                            "expira": time.time() + int(tok.get("expires_in", 3600)) - 60})


def conectar(client_id: str, espera_s: int = 180) -> str:
    """Abre o login do Spotify no navegador e espera a volta. '' = conectado."""
    if not client_id:
        return "falta o Client ID"
    verifier, challenge = par_pkce()
    estado = secrets.token_urlsafe(12)
    resultado: dict = {}

    class Volta(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == estado:
                resultado["code"] = q.get("code", [""])[0]
                resultado["erro"] = q.get("error", [""])[0]
            corpo = ("<h2 style='font-family:sans-serif'>Pronto! Pode voltar para o JARVIS.</h2>" if resultado.get("code")
                     else "<h2 style='font-family:sans-serif'>Não deu certo. Tente de novo.</h2>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(corpo)

    try:
        srv = HTTPServer(("127.0.0.1", 8888), Volta)
    except OSError:
        return "a porta 8888 está ocupada; feche o programa que a usa e tente de novo"
    srv.timeout = 1
    abrir_no_sistema(url_login(client_id, challenge, estado))
    fim = time.time() + espera_s
    try:
        while time.time() < fim and "code" not in resultado:
            srv.handle_request()
    finally:
        srv.server_close()
    if not resultado.get("code"):
        return resultado.get("erro") or "o login não voltou a tempo"
    try:
        tok = _post_token({"grant_type": "authorization_code", "code": resultado["code"], "redirect_uri": REDIRECT,
                           "client_id": client_id, "code_verifier": verifier})
    except Exception as e:
        return f"o Spotify recusou o login: {e}"
    _guardar(tok, client_id)
    return ""


def conectado() -> bool:
    return bool((ler_json(ARQ_TOKEN, {}) or {}).get("refresh_token"))


_lock = threading.Lock()


def token() -> str:
    with _lock:
        t = ler_json(ARQ_TOKEN, {}) or {}
        if not t.get("refresh_token"):
            raise ErroSpotify(401, "Spotify não conectado")
        if time.time() < t.get("expira", 0):
            return t["access_token"]
        novo = _post_token({"grant_type": "refresh_token", "refresh_token": t["refresh_token"],
                            "client_id": t["client_id"]})
        _guardar(novo, t["client_id"])
        return novo["access_token"]


def api(metodo: str, caminho: str, params: dict | None = None, corpo: dict | None = None):
    url = API + caminho + (("?" + urllib.parse.urlencode(params)) if params else "")
    for tentativa in range(2):
        req = urllib.request.Request(url, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else
                                     (b"" if metodo in ("PUT", "POST") else None),
                                     headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                bruto = r.read()
                return json.loads(bruto) if bruto else {}
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")[:300]
            if e.code == 401 and tentativa == 0:
                t = ler_json(ARQ_TOKEN, {}) or {}
                t["expira"] = 0
                gravar_json(ARQ_TOKEN, t)
                continue
            raise ErroSpotify(e.code, texto) from None
    raise ErroSpotify(401, "token recusado")


# ── pedidos ──────────────────────────────────────────────────────────────────
def tipo_do_pedido(pedido: str) -> str:
    """'playlist de treino' → playlist; 'álbum X' → album; 'músicas do Kaiser' → artist; senão track (pura)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", pedido.lower()).encode("ascii", "ignore").decode()
    if "playlist" in t:
        return "playlist"
    if "album" in t or "disco" in t:
        return "album"
    if any(x in t for x in ("musicas do", "musicas da", "musicas de", "artista", "som do", "som da")):
        return "artist"
    return "track"


def limpar_pedido(pedido: str) -> str:
    import re
    t = re.sub(r"(?i)\b(toca|tocar|coloca|bota|p[oõ]e|a\s+)?\s*(a\s+)?(playlist|[aá]lbum|disco|m[uú]sicas?\s+d[oae]s?|"
               r"artista|som\s+d[oae]|m[uú]sica)\b", " ", pedido)
    t = re.sub(r"\s+", " ", t).strip(" ,.")
    return re.sub(r"(?i)^(de|do|da|dos|das|o|a)\s+", "", t)


def buscar(pedido: str, tipo: str | None = None) -> dict | None:
    tipo = tipo or tipo_do_pedido(pedido)
    q = limpar_pedido(pedido) or pedido
    r = api("GET", "/search", {"q": q, "type": tipo, "limit": 1, "market": "from_token"})
    itens = (r.get(tipo + "s") or {}).get("items") or []
    itens = [i for i in itens if i]
    return {**itens[0], "_tipo": tipo} if itens else None


def nome_item(item: dict) -> str:
    if item.get("_tipo") == "track" or item.get("type") == "track":
        return f"{', '.join(a['name'] for a in item.get('artists', [])[:2])} - {item.get('name', '')}"
    return item.get("name", "")


def _garantir_aparelho() -> str | None:
    devs = (api("GET", "/me/player/devices") or {}).get("devices") or []
    ativo = next((d for d in devs if d.get("is_active")), None)
    if ativo:
        return ativo["id"]
    if devs:
        return devs[0]["id"]
    abrir_no_sistema("spotify:")                                  # abre o app e espera ele aparecer
    for _ in range(10):
        time.sleep(1.5)
        devs = (api("GET", "/me/player/devices") or {}).get("devices") or []
        if devs:
            return devs[0]["id"]
    return None


def tocar_item(item: dict) -> str:
    """Toca no Spotify. Sem Premium, abre a música no app. Devolve o nome do que tocou."""
    corpo = {"uris": [item["uri"]]} if item.get("_tipo") == "track" else {"context_uri": item["uri"]}
    try:
        api("PUT", "/me/player/play", corpo=corpo)
    except ErroSpotify as e:
        if e.codigo == 404:                                       # nenhum aparelho ativo
            dev = _garantir_aparelho()
            if not dev:
                raise
            api("PUT", "/me/player/play", {"device_id": dev}, corpo)
        elif e.codigo == 403:                                     # sem Premium
            abrir_no_sistema(item["uri"])
            return nome_item(item) + " (abri no Spotify; sem Premium, aperte o play)"
        else:
            raise
    return nome_item(item)


def tocando() -> dict | None:
    r = api("GET", "/me/player/currently-playing")
    if not r or not r.get("item"):
        return None
    it = r["item"]
    return {"faixa": nome_item({**it, "_tipo": "track"}), "id": it.get("id"), "tocando": r.get("is_playing", False),
            "progresso_ms": r.get("progress_ms", 0), "artistas": [a.get("id") for a in it.get("artists", [])]}


def top_artistas(n: int = 10) -> list[dict]:
    return (api("GET", "/me/top/artists", {"time_range": "medium_term", "limit": n}) or {}).get("items") or []


def lancamentos(artista_id: str, n: int = 3) -> list[dict]:
    r = api("GET", f"/artists/{artista_id}/albums", {"include_groups": "album,single", "limit": n, "market": "from_token"})
    return (r or {}).get("items") or []
