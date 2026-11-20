"""
Servidor do Arcade JARVIS (1.7). Começa com "_": não é ferramenta.

Só biblioteca padrão: um http.server em 127.0.0.1 (porta livre) que entrega
dashboard/static/arcade.html e uma API pequena para o xadrez e as damas
(motor em Python) e para o placar. A partida de xadrez/damas é a mesma do
arquivo memory/xadrez.json, então clicar no Arcade e falar "cavalo f3"
mexem no mesmo jogo. Só aceita pedidos com o token da sessão.
"""

from __future__ import annotations

import json
import random
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from plugins import _xadrez_motor as motor
from plugins._comum import BASE, MEMORIA, gravar_json, ler_json

PAGINA = BASE / "dashboard" / "static" / "arcade.html"
# 2.2: o mesmo servidor local mostra também a tela do QR do WhatsApp e o player de música.
PAGINAS = {"/": "arcade.html", "/arcade": "arcade.html", "/whatsapp": "whatsapp.html", "/player": "player.html",
           "/grafo": "grafo.html", "/missoes": "missoes.html",                    # 2.4
           "/encomendas": "encomendas.html", "/mao": "mao.html",                  # 2.5
           "/vitrine": "vitrine.html", "/avatar_demo": "avatar.html",             # 2.6
           "/palco": "palco.html"}                                                 # 2.7
# 2.5: plugins penduram a própria API aqui (sem mexer neste arquivo):
#   ROTAS_GET["/api/x"] = fn(query: dict[str, str]) -> dict
#   ROTAS_POST["/api/x"] = fn(corpo: dict) -> dict
ROTAS_GET: dict = {}
ROTAS_POST: dict = {}
ARQ_PLACAR = MEMORIA / "jogos_placar.json"

_trava = threading.Lock()
_servidor: ThreadingHTTPServer | None = None
TOKEN = secrets.token_urlsafe(16)
_ao_jogar = None            # função opcional (texto) → None, para o JARVIS comentar em voz


def _xd():
    from plugins import xadrez
    return xadrez


# ── estado do xadrez/damas para a página ─────────────────────────────────────
def estado_xadrez() -> dict:
    d = ler_json(_xd().ARQ, {}) or {}
    if d.get("fen"):
        pos = motor.Posicao(d["fen"])
        legais = [[m[0], m[1], m[2]] for m in pos.legais()]
        r = pos.resultado()
        return {"fen": d["fen"], "tab": pos.tab, "vez": pos.vez, "voce": d.get("voce", "brancas"),
                "nivel": d.get("nivel", "medio"), "ativo": d.get("jogo") == "xadrez", "legais": legais,
                "ultimo": d.get("ultimo"), "xeque": pos.em_xeque(), "resultado": r,
                "lances": d.get("lances", [])[-12:], "outro": d.get("jogo") == "damas"}
    return {"fen": "", "ativo": False, "outro": d.get("jogo") == "damas"}


def estado_damas() -> dict:
    xd = _xd()
    d = ler_json(xd.ARQ, {}) or {}
    if d.get("tab") and d.get("jogo") != "xadrez":
        lances = xd.damas_lances(d["tab"], "b") if d.get("jogo") == "damas" else []
        return {"tab": d["tab"], "ativo": d.get("jogo") == "damas", "nivel": d.get("nivel", "medio"),
                "legais": [[list(c) for c in s] for s, _com in lances],
                "ultimo": d.get("ultimo_damas"), "fim": not lances}
    return {"tab": {}, "ativo": False}


def xadrez_novo(nivel: str, voce: str) -> dict:
    with _trava:
        d, fala = _xd().novo_xadrez(nivel if nivel in ("facil", "medio", "dificil") else "medio",
                                    "pretas" if voce == "pretas" else "brancas", random.Random())
        gravar_json(_xd().ARQ, d)
    return {**estado_xadrez(), "fala": fala}


def xadrez_lance(de: int, para: int, promo: str = "") -> dict:
    with _trava:
        xd = _xd()
        d = ler_json(xd.ARQ, {}) or {}
        if d.get("jogo") != "xadrez":
            return {**estado_xadrez(), "erro": "Não há partida de xadrez. Comece uma nova."}
        pos = motor.Posicao(d["fen"])
        if (pos.vez == "w") != (d.get("voce", "brancas") == "brancas"):
            return {**estado_xadrez(), "erro": "Não é a sua vez."}
        lance = next((m for m in pos.legais() if m[0] == de and m[1] == para and (m[2] == (promo or "Q") or not m[2])),
                     None)
        if not lance:
            return {**estado_xadrez(), "erro": "Esse lance não vale."}
        fala = xd.jogada_xadrez(d, lance, random.Random())
        gravar_json(xd.ARQ, d)
    _avisar(fala)
    return {**estado_xadrez(), "fala": fala}


def damas_novo(nivel: str) -> dict:
    with _trava:
        d, fala = _xd().novo_damas(nivel if nivel in ("facil", "medio", "dificil") else "medio")
        gravar_json(_xd().ARQ, d)
    return {**estado_damas(), "fala": fala}


def damas_lance(casas: list) -> dict:
    with _trava:
        xd = _xd()
        d = ler_json(xd.ARQ, {}) or {}
        if d.get("jogo") != "damas":
            return {**estado_damas(), "erro": "Não há partida de damas. Comece uma nova."}
        alvo = [tuple(c) for c in casas]
        lance = next((x for x in xd.damas_lances(d["tab"], "b") if list(x[0]) == alvo), None)
        if not lance:
            return {**estado_damas(), "erro": "Esse lance não vale (a captura é obrigatória, e a maior)."}
        fala = xd.jogada_damas(d, lance, random.Random())
        gravar_json(xd.ARQ, d)
    _avisar(fala)
    return {**estado_damas(), "fala": fala}


# ── placar ─────────────────────────────────────────────────────────────────────
def placar() -> dict:
    return ler_json(ARQ_PLACAR, {}) or {}


def registrar(jogo: str, resultado: str = "", pontos: int | None = None) -> dict:
    """resultado: vitoria | derrota | empate; pontos: recorde (maior é melhor)."""
    jogo = "".join(ch for ch in str(jogo).lower() if ch.isalnum() or ch == "_")[:30] or "jogo"
    with _trava:
        p = placar()
        j = p.setdefault(jogo, {"vitorias": 0, "derrotas": 0, "empates": 0, "recorde": 0, "partidas": 0})
        j["partidas"] += 1
        if resultado in ("vitoria", "derrota", "empate"):
            j[{"vitoria": "vitorias", "derrota": "derrotas", "empate": "empates"}[resultado]] += 1
        if pontos is not None:
            try:
                j["recorde"] = max(int(j.get("recorde", 0)), int(pontos))
            except (TypeError, ValueError):
                pass
        gravar_json(ARQ_PLACAR, p)
    return p


def _avisar(fala: str) -> None:
    if _ao_jogar:
        try:
            _ao_jogar(fala)
        except Exception:
            pass


# ── HTTP ──────────────────────────────────────────────────────────────────────
class Atendente(BaseHTTPRequestHandler):
    def log_message(self, *a):          # silencioso
        pass

    def _json(self, obj, codigo=200):
        corpo = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _ok_token(self, q) -> bool:
        return secrets.compare_digest((q.get("t") or [""])[0], TOKEN) or \
            secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in PAGINAS:
            if not self._ok_token(q):
                return self._json({"erro": "token"}, 403)
            try:
                corpo = (PAGINA.parent / PAGINAS[u.path]).read_bytes()
            except OSError:
                return self._json({"erro": f"{PAGINAS[u.path]} não encontrado"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if not self._ok_token(q):
            return self._json({"erro": "token"}, 403)
        rotas = {"/api/xadrez": estado_xadrez, "/api/damas": estado_damas, "/api/placar": placar,
                 "/api/whatsapp": _estado_whatsapp, "/api/musica": _estado_musica,
                 "/api/musica/playlists": _playlists, "/api/grafo": _grafo, "/api/missoes": _missoes}
        if u.path == "/api/musica/buscar":
            return self._json(_buscar_musica((q.get("q") or [""])[0]))
        if u.path == "/api/grafo/buscar":                       # 2.4: memória em grafo
            return self._json(_buscar_grafo((q.get("q") or [""])[0]))
        if u.path == "/api/grafo/no":
            return self._json(_conexoes_grafo((q.get("nome") or [""])[0]))
        fn = rotas.get(u.path)
        if fn is None and u.path in ROTAS_GET:                  # 2.5: rotas dos plugins
            try:
                return self._json(ROTAS_GET[u.path]({k: v[0] for k, v in q.items() if k != "t"}))
            except Exception as e:
                return self._json({"erro": str(e)}, 500)
        try:
            return self._json(fn()) if fn else self._json({"erro": "rota"}, 404)
        except Exception as e:
            return self._json({"erro": str(e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        if not self._ok_token(parse_qs(u.query)):
            return self._json({"erro": "token"}, 403)
        try:
            tam = min(int(self.headers.get("Content-Length") or 0), 65536)
            b = json.loads(self.rfile.read(tam) or b"{}")
        except (ValueError, OSError):
            return self._json({"erro": "json"}, 400)
        try:
            if u.path == "/api/xadrez/novo":
                return self._json(xadrez_novo(str(b.get("nivel", "medio")), str(b.get("voce", "brancas"))))
            if u.path == "/api/xadrez/lance":
                return self._json(xadrez_lance(int(b["de"]), int(b["para"]), str(b.get("promo") or "")))
            if u.path == "/api/damas/novo":
                return self._json(damas_novo(str(b.get("nivel", "medio"))))
            if u.path == "/api/damas/lance":
                return self._json(damas_lance(list(b["casas"])))
            if u.path == "/api/placar":
                return self._json(registrar(str(b.get("jogo", "")), str(b.get("resultado", "")), b.get("pontos")))
            if u.path == "/api/musica/cmd":
                return self._json(_comando_musica(b))
            if u.path == "/api/missoes/cmd":                    # 2.4: pausar / continuar / cancelar
                from core import missoes
                return self._json(missoes.comando(str(b.get("acao") or ""), int(b.get("id") or 0)))
            if u.path == "/api/whatsapp/ligar":
                from plugins import _whatsapp
                _whatsapp.iniciar_em_segundo_plano()
                return self._json({"ok": True})
            if u.path in ROTAS_POST:                            # 2.5: rotas dos plugins
                try:
                    return self._json(ROTAS_POST[u.path](b))
                except (KeyError, TypeError, ValueError):
                    raise
                except Exception as e:
                    return self._json({"erro": str(e)}, 500)
        except (KeyError, TypeError, ValueError) as e:
            return self._json({"erro": f"pedido inválido: {e}"}, 400)
        return self._json({"erro": "rota"}, 404)


# ── 2.2: WhatsApp e música ──────────────────────────────────────────────────
def _estado_whatsapp() -> dict:
    from plugins import _whatsapp
    return _whatsapp.estado_para_tela()


def _estado_musica() -> dict:
    from plugins import musica
    return musica.estado_player()


def _playlists() -> dict:
    from plugins import musica
    return musica.playlists_player()


def _buscar_musica(q: str) -> dict:
    from plugins import musica
    return musica.buscar_player(q)


def _comando_musica(b: dict) -> dict:
    from plugins import musica
    return musica.comando_player(str(b.get("acao") or ""), b)


# ── 2.4: memória em grafo e missões ──────────────────────────────────────────
def _grafo() -> dict:
    from core import memoria_grafo
    return {**memoria_grafo.grafo_json(), "estatisticas": memoria_grafo.estatisticas()}


def _buscar_grafo(q: str) -> dict:
    from core import memoria_grafo
    return {"resultados": memoria_grafo.buscar(q, 8)}


def _conexoes_grafo(nome: str) -> dict:
    from core import memoria_grafo
    return memoria_grafo.conexoes(nome)


def _missoes() -> dict:
    from core import missoes
    return {"missoes": missoes.listar()}


def abrir_pagina(caminho: str, largura: int = 1180, altura: int = 860, x: int | None = None,
                 y: int | None = None, extras: list[str] | None = None) -> bool:
    """Abre uma página deste servidor numa janela própria (Edge/Chrome em modo app); senão, no navegador."""
    import os
    import shutil
    import subprocess

    from plugins._comum import CNW, WIN, abrir_no_sistema
    url = iniciar().replace("/?t=", f"{caminho}?t=", 1)
    if WIN:
        for exe, fixo in (("msedge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                          ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe")):
            caminho_exe = shutil.which(exe) or (fixo if os.path.exists(fixo) else None)
            if caminho_exe:
                args = [caminho_exe, f"--app={url}", f"--window-size={largura},{altura}"]
                if x is not None and y is not None:
                    args.append(f"--window-position={x},{y}")
                args += list(extras or [])                     # 2.6: ex.: som sem precisar clicar (vitrine)
                try:
                    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **CNW)
                    return True
                except OSError:
                    pass
    return abrir_no_sistema(url)


def iniciar(porta: int = 0) -> str:
    """Liga o servidor (uma vez) e devolve a URL com o token."""
    global _servidor
    with _trava:
        if _servidor is None:
            _servidor = ThreadingHTTPServer(("127.0.0.1", porta), Atendente)
            _servidor.daemon_threads = True
            threading.Thread(target=_servidor.serve_forever, name="arcade", daemon=True).start()
        return f"http://127.0.0.1:{_servidor.server_address[1]}/?t={TOKEN}"


def parar() -> None:
    global _servidor
    with _trava:
        if _servidor is not None:
            _servidor.shutdown()
            _servidor.server_close()
            _servidor = None
