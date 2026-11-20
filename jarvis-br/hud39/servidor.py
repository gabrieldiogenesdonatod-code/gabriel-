"""Servidor local do HUD 3.9 (só 127.0.0.1).

GET  /               a página (com o token)
GET  /hud.jpg        a arte de fundo
GET  /api/estado     os números do momento + o estado do JARVIS
GET  /api/sobre      as informações fixas do sistema
POST /api/acao       {"acao": ..., ...} — exige o cabeçalho X-Token
"""
from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import sistema

PORTA = 18091
TOKEN = secrets.token_hex(16)
STATIC = Path(__file__).resolve().parent / "static"
_SO = platform.system()
_ARQUIVOS = {"/hud.jpg": ("hud.jpg", "image/jpeg"), "/friday.jpg": ("friday.jpg", "image/jpeg")}

# Ganchos que o JARVIS instala ao abrir (no modo avulso ficam None).
_ganchos: dict = {"comando": None, "estado": None}
_srv: dict = {"s": None}


# ── ações ─────────────────────────────────────────────────────────────────────
def _pasta(nome: str) -> Path:
    casa = Path.home()
    try:
        from plugins._comum import pasta_usuario
        mapa = {"documentos": "Documents", "downloads": "Downloads", "videos": "Videos",
                "imagens": "Pictures", "area": "Desktop"}
        if nome in mapa:
            return pasta_usuario(mapa[nome])
    except Exception:
        pass
    nomes = {"musica": ["Music", "Músicas", "Musicas"], "videos": ["Videos", "Vídeos", "Movies"],
             "documentos": ["Documents", "Documentos"], "imagens": ["Pictures", "Imagens"],
             "downloads": ["Downloads"], "area": ["Desktop", "Área de Trabalho"], "casa": [""]}
    for n in nomes.get(nome, [""]):
        if (casa / n).exists():
            return casa / n
    return casa


def _abrir_no_sistema(alvo: str) -> bool:
    try:
        from plugins._comum import abrir_no_sistema
        return abrir_no_sistema(alvo)
    except Exception:
        pass
    try:
        if _SO == "Windows":
            os.startfile(alvo)                                   # noqa: S606
        else:
            subprocess.Popen(["open" if _SO == "Darwin" else "xdg-open", alvo])
        return True
    except Exception:
        return False


_TECLAS = {"tocar": 0xB3, "proxima": 0xB0, "anterior": 0xB1, "mudo": 0xAD, "vol_menos": 0xAE, "vol_mais": 0xAF}
_PLAYERCTL = {"tocar": ["play-pause"], "proxima": ["next"], "anterior": ["previous"]}


def _midia(tecla: str) -> str:
    if tecla not in _TECLAS:
        return "Tecla de mídia desconhecida."
    if _SO == "Windows":
        import ctypes
        vk = _TECLAS[tecla]
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        return "ok"
    if _SO == "Linux" and tecla in _PLAYERCTL and shutil.which("playerctl"):
        subprocess.run(["playerctl", *_PLAYERCTL[tecla]], timeout=3, capture_output=True)
        return "ok"
    return "Teclas de mídia só no Windows (ou Linux com playerctl)."


def _steam() -> bool:
    if _SO == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                if winreg.QueryValueEx(k, "SteamExe")[0]:
                    return _abrir_no_sistema("steam://open/games")
        except Exception:
            return False
    elif shutil.which("steam"):
        return _abrir_no_sistema("steam://open/games")
    return False


def _comando(texto: str) -> str:
    texto = " ".join(str(texto or "").split())[:500]
    if not texto:
        return "Comando vazio."
    fn = _ganchos.get("comando")
    if not callable(fn):
        return "O JARVIS não está aberto: o HUD está rodando sozinho."
    threading.Thread(target=fn, args=(texto,), daemon=True, name="hud39-comando").start()
    return "ok"


def executar(dados: dict) -> dict:
    """Uma ação vinda de um clique. Nada aqui apaga, instala ou finaliza."""
    a = str(dados.get("acao") or "")
    if a == "pasta":
        p = _pasta(str(dados.get("pasta") or "casa"))
        return {"ok": _abrir_no_sistema(str(p)), "resposta": f"Abrindo {p}"}
    if a == "navegador":
        return {"ok": bool(webbrowser.open("https://www.google.com")), "resposta": "Abrindo o navegador"}
    if a == "midia":
        r = _midia(str(dados.get("tecla") or ""))
        return {"ok": r == "ok", "resposta": r}
    if a == "steam":
        ok = _steam()
        return {"ok": ok, "resposta": "Abrindo a Steam" if ok else "Não achei a Steam neste PC."}
    if a == "comando":
        r = _comando(dados.get("texto"))
        return {"ok": r == "ok", "resposta": "Enviado ao JARVIS" if r == "ok" else r}
    if a == "ping":
        try:
            from core import telemetria
            return {"ok": True, "resposta": telemetria.get().medir_ping_agora()}
        except Exception as e:
            return {"ok": False, "resposta": f"Sem ping: {e}"}
    return {"ok": False, "resposta": "Ação desconhecida."}


def estado_jarvis() -> dict:
    fn = _ganchos.get("estado")
    base = {"conectado": callable(_ganchos.get("comando")), "estado": None, "falando": False, "mudo": False}
    if callable(fn):
        try:
            base.update(fn() or {})
        except Exception:
            pass
    return base


# ── HTTP ──────────────────────────────────────────────────────────────────────
def _json(o) -> bytes:
    def limpar(x):
        if isinstance(x, float) and (x != x or x in (float("inf"), float("-inf"))):
            return None
        if isinstance(x, dict):
            return {str(k): limpar(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [limpar(v) for v in x]
        return x
    return json.dumps(limpar(o), ensure_ascii=False, default=str).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _host_ok(self) -> bool:
        # Contra "DNS rebinding": só aceita quem chegou pelo endereço local de verdade.
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("127.0.0.1", "localhost")

    def _enviar(self, cod: int, corpo: bytes, tipo: str, cache: bool = False) -> None:
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if not self._host_ok():
            return self._enviar(403, b"{}", "application/json")
        rota = self.path.split("?")[0]
        if rota in ("/", "/index.html"):
            html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
            return self._enviar(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if rota in _ARQUIVOS:
            nome, tipo = _ARQUIVOS[rota]
            return self._enviar(200, (STATIC / nome).read_bytes(), tipo, cache=True)
        if rota == "/api/estado":
            return self._enviar(200, _json({**sistema.momento(), "jarvis": estado_jarvis()}), "application/json")
        if rota == "/api/sobre":
            return self._enviar(200, _json(sistema.fixo()), "application/json")
        self._enviar(404, b"{}", "application/json")

    def do_POST(self):
        if not self._host_ok() or self.path != "/api/acao" or self.headers.get("X-Token") != TOKEN:
            return self._enviar(403, b'{"erro": "sem permissao"}', "application/json")
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 8192)
            dados = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(dados, dict):
                raise ValueError
        except ValueError:
            return self._enviar(400, b'{"erro": "json"}', "application/json")
        try:
            r = executar(dados)
        except Exception as e:
            r = {"ok": False, "resposta": f"Falhou: {e}"}
        self._enviar(200, _json(r), "application/json")


def iniciar(porta: int = PORTA) -> str:
    """Sobe o servidor (uma vez). Se a porta estiver ocupada, usa outra livre."""
    if _srv["s"] is None:
        try:
            s = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
        except OSError:
            s = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True, name="hud39").start()
        _srv["s"] = s
        # Já aquece a telemetria e as informações fixas: a primeira tela vem com números.
        threading.Thread(target=lambda: (sistema.fixo(), sistema.momento()), daemon=True).start()
    return endereco()


def endereco() -> str:
    return f"http://127.0.0.1:{_srv['s'].server_address[1]}/" if _srv["s"] else ""


def parar() -> None:
    if _srv["s"] is not None:
        _srv["s"].shutdown()
        _srv["s"].server_close()
        _srv["s"] = None


# ── janela ────────────────────────────────────────────────────────────────────
def _navegadores() -> list[str]:
    achados = []
    if _SO == "Windows":
        bases = [os.environ.get(v, "") for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        for b in filter(None, bases):
            achados += [str(Path(b) / "Microsoft/Edge/Application/msedge.exe"),
                        str(Path(b) / "Google/Chrome/Application/chrome.exe")]
    elif _SO == "Darwin":
        achados += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    else:
        achados += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")]
    return [a for a in achados if a and Path(a).exists()]


def abrir_janela(url: str, tela_cheia: bool = True) -> str:
    """Abre como aplicativo (Edge/Chrome sem barra de endereço). Sem eles, o navegador padrão."""
    for exe in _navegadores():
        perfil = Path.home() / ".jarvis-br" / "hud39-janela"
        perfil.mkdir(parents=True, exist_ok=True)
        args = [exe, f"--app={url}", f"--user-data-dir={perfil}", "--no-first-run",
                "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required",
                "--window-size=1600,900"]
        if tela_cheia:
            args.append("--start-fullscreen")
        try:
            extra = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if _SO == "Windows" else {}
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **extra)
            return Path(exe).stem
        except Exception:
            continue
    webbrowser.open(url)
    return "navegador"


def abrir(comando=None, estado=None, tela_cheia: bool = True, janela: bool = True, painel: str = "",
          tema: str = "") -> str:
    """Sobe o servidor, instala os ganchos do JARVIS e abre a janela (já num painel, se pedido)."""
    if comando is not None:
        _ganchos["comando"] = comando
    if estado is not None:
        _ganchos["estado"] = estado
    url = iniciar()
    if janela:
        painel = "".join(c for c in str(painel or "") if c.isalnum())
        tema = "friday" if tema == "friday" else ""
        abrir_janela(url + (f"?tema={tema}" if tema else "") + (f"#{painel}" if painel else ""), tela_cheia)
    return url
