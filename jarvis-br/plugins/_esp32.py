"""
Aparelhos ESP32 da casa (fork PT-BR 2.5) — o lado do PC. Começa com "_": não é ferramenta.

Um servidor HTTP pequeno (só biblioteca padrão) na rede de casa, porta 8765,
que fica ligado enquanto o JARVIS está aberto — não precisa abrir o painel
remoto. Os aparelhos falam HTTP simples (TLS é pesado demais para eles):

    POST /esp32/planta?k=CHAVE   {"id": "sala", "bruto": 2310}     sensor de umidade da terra
    GET  /esp32/painel?k=CHAVE                                     o texto do painel de LED
    POST /esp32/luva?k=CHAVE     {"gesto": "repulsor"}             luva com acelerômetro
    GET  /esp32/ping?k=CHAVE                                       teste

A CHAVE é fixa e fica em config/esp32.json (fora do ZIP). Sem a chave certa:
401. Só liga depois que você pede "Jarvis, configura a planta / o painel /
a luva" (ou liga em ⚙ → Aparelhos ESP32). Na primeira vez, o Windows pede
para liberar a porta no firewall (uma janela de administrador).
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from plugins._comum import CONFIG, WIN, cfg, gravar_json, ler_json, salvar_cfg

PORTA_PADRAO = 8765
ARQ = CONFIG / "esp32.json"
ROTAS: dict = {}            # ("GET" | "POST", "/esp32/x") → fn(corpo: dict, query: dict) -> dict
PLUGIN_SETTINGS = {
    "namespace": "esp32",
    "title": "Aparelhos ESP32 (planta, painel de LED, luva)",
    "fields": [
        {"key": "ligado", "label": "Ligar o servidor dos aparelhos na rede de casa", "type": "toggle",
         "default": False},
        {"key": "porta", "label": "Porta", "type": "text", "default": str(PORTA_PADRAO)},
    ],
}
_lock = threading.Lock()
_srv = {"servidor": None, "erro": "", "ultimo": {}}


def obter_chave(nova: bool = False) -> str:
    d = ler_json(ARQ, {}) or {}
    if nova or not d.get("chave"):
        d["chave"] = secrets.token_urlsafe(12)
        gravar_json(ARQ, d)
    return d["chave"]


def porta() -> int:
    try:
        return int(str(cfg("esp32", PLUGIN_SETTINGS).get("porta") or PORTA_PADRAO))
    except ValueError:
        return PORTA_PADRAO


def ip_local() -> str:
    """O IP do PC na rede de casa (o que vai no sketch)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))                       # não manda nada: só escolhe a placa de rede
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def registrar_rota(metodo: str, caminho: str, fn) -> None:
    ROTAS[(metodo.upper(), caminho)] = fn


def visto(nome: str) -> float:
    """Quando esse aparelho falou com o PC pela última vez (0 = nunca)."""
    return _srv["ultimo"].get(nome, 0.0)


class _Atendente(BaseHTTPRequestHandler):
    server_version = "JARVIS-ESP32/2.5"

    def log_message(self, *a):
        pass

    def _json(self, obj: dict, codigo: int = 200) -> None:
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(corpo)

    def _tratar(self, metodo: str) -> None:
        import time
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        chave = q.pop("k", "") or self.headers.get("X-Chave", "")
        if not secrets.compare_digest(str(chave), obter_chave()):
            return self._json({"erro": "chave"}, 401)
        if u.path == "/esp32/ping":
            return self._json({"ok": True, "nome": "J.A.R.V.I.S BR"})
        fn = ROTAS.get((metodo, u.path))
        if fn is None:
            return self._json({"erro": "rota"}, 404)
        corpo = {}
        if metodo == "POST":
            try:
                tam = min(int(self.headers.get("Content-Length") or 0), 4096)
                corpo = json.loads(self.rfile.read(tam) or b"{}")
                if not isinstance(corpo, dict):
                    raise ValueError("não é objeto")
            except (ValueError, OSError):
                return self._json({"erro": "json"}, 400)
        _srv["ultimo"][u.path.rsplit("/", 1)[-1]] = time.time()
        try:
            return self._json(fn(corpo, q) or {"ok": True})
        except Exception as e:
            print(f"[ESP32] {u.path}: {e}")
            return self._json({"erro": str(e)[:120]}, 500)

    def do_GET(self):
        self._tratar("GET")

    def do_POST(self):
        self._tratar("POST")


def iniciar(liberar_firewall: bool = True) -> str:
    """Liga o servidor (uma vez). Devolve '' ou o erro."""
    with _lock:
        if _srv["servidor"] is not None:
            return ""
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", porta()), _Atendente)
        except OSError as e:
            _srv["erro"] = f"a porta {porta()} está ocupada ({e})"
            return _srv["erro"]
        srv.daemon_threads = True
        _srv["servidor"] = srv
        threading.Thread(target=srv.serve_forever, name="esp32", daemon=True).start()
    if WIN and liberar_firewall:
        def _firewall():
            try:
                from dashboard.server import _ensure_network_access
                _ensure_network_access(porta())
            except Exception as e:
                print(f"[ESP32] firewall: {e}")
        threading.Thread(target=_firewall, daemon=True).start()
    print(f"[ESP32] aparelhos em http://{ip_local()}:{porta()}/esp32/…")
    return ""


def ligar() -> str:
    salvar_cfg("esp32", {"ligado": True})
    return iniciar()


def iniciar_se_ligado() -> None:
    if cfg("esp32", PLUGIN_SETTINGS).get("ligado"):
        iniciar()


def parar() -> None:
    with _lock:
        if _srv["servidor"] is not None:
            _srv["servidor"].shutdown()
            _srv["servidor"].server_close()
            _srv["servidor"] = None


def configuracao(aparelho: str) -> str:
    """O texto que a pessoa cola no sketch."""
    erro = ligar()
    if erro:
        return f"Não consegui ligar o servidor dos aparelhos: {erro}."
    return (f"Para o sketch esp32/{aparelho}: PC_IP = \"{ip_local()}\", PC_PORTA = {porta()}, "
            f"CHAVE = \"{obter_chave()}\". O passo a passo está em esp32/{aparelho}/LEIA-ME.md.")
