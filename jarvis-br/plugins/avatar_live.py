"""
Avatar do JARVIS para lives (fork PT-BR 2.5).

    "Jarvis, liga o avatar da live"    → diz o endereço para colocar no OBS
    "Jarvis, comemora!" / "ri disso" / "faz cara de surpresa"

No OBS: Fontes → + → Navegador → URL que o JARVIS disser
(http://127.0.0.1:8766/avatar?k=…), largura 400, altura 400. O fundo é
transparente: posicione no canto da live da loja ou do jogo.

O rosto mexe a boca quando o JARVIS fala e REAGE sozinho:
  • ao que ele mesmo diz e ao que você diz ("kkkk" → ri junto; "parabéns" → comemora);
  • a cada venda registrada na Cristal Malhas → comemora com "Venda!";
  • ao chat da Twitch (opcional, só leitura, sem login): muita risada → ri;
    "pog"/"uau" → surpresa; "gg" → comemora; inscrição → agradece.
Servidor só no próprio PC (127.0.0.1), com chave fixa em config/avatar.json.
"""

from __future__ import annotations

import json
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from plugins._comum import BASE, CONFIG, MEMORIA, cfg, gravar_json, ler_json, salvar_cfg, sim

PLUGIN = {
    "name": "avatar_live",
    "brief": "JARVIS face for live streams (OBS browser source) that talks and reacts: laughs, surprise, celebrates.",
    "description": (
        "Live-stream avatar (OBS browser source, transparent). action='ligar' starts it and returns the URL to add in "
        "OBS; 'desligar'. 'reagir' with expressao (rir | surpresa | comemorar | pensar | triste | neutro) and optional "
        "texto (a short caption) makes the face react now. 'status'. It also reacts by itself to what is said, to "
        "store sales and to Twitch chat."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ligar | desligar | reagir | status"},
            "expressao": {"type": "STRING"}, "texto": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "avatar_live",
    "title": "Avatar da live (OBS)",
    "fields": [
        {"key": "ligado", "label": "Ligar o avatar junto com o JARVIS", "type": "toggle", "default": False},
        {"key": "porta", "label": "Porta (o endereço no OBS usa ela)", "type": "text", "default": "8766"},
        {"key": "legenda", "label": "Mostrar o que o JARVIS fala embaixo do rosto", "type": "toggle", "default": True},
        {"key": "vendas", "label": "Comemorar as vendas da Cristal Malhas", "type": "toggle", "default": True},
        {"key": "twitch", "label": "Canal da Twitch para reagir ao chat (vazio = não)", "type": "text", "default": ""},
    ],
}

EXPRESSOES = ("neutro", "rir", "surpresa", "comemorar", "pensar", "triste")
PAGINA = BASE / "dashboard" / "static" / "avatar.html"
ARQ_CHAVE = CONFIG / "avatar.json"
ARQ_VENDAS = MEMORIA / "cristal_vendas.csv"
REGRAS = [
    ("comemorar", r"parab[ée]ns|vit[óo]ria|venceu|ganhou|ganhamos|conseguiu|conseguimos|isso a[íi]|mandou bem|recorde|"
                  r"\bvenda\b|vendeu|bateu a meta|\bgol\b|\bgg\b|let'?s go|boa!"),
    ("surpresa", r"\buau\b|\bnossa\b|caramba|caraca|s[ée]rio\?|\bwow\b|meu deus|\beita\b|olha s[óo]|incr[íi]vel|"
                 r"impressionante|\bpog\b|pogchamp|\bomg\b"),
    ("rir", r"\b(?:ha){2,}|\bk{3,}|\b(?:he){2,}|\brs\b|risos|engra[çc]ad|piada|\blol\b|\blmao\b|kekw"),
    ("triste", r"que pena|infelizmente|perdeu|perdemos|sinto muito|\bpoxa\b|n[ãa]o deu|\bf\b no chat|sadge"),
    ("pensar", r"\bhmm+\b|deixa eu ver|vou verificar|pesquisando|um momento|s[óo] um segundo|calculando"),
]
_lock = threading.Lock()
_iniciou = threading.Event()
_estado = {"servidor": None, "expressao": "neutro", "expr_id": 0, "expr_ate": 0.0, "texto": "", "texto_id": 0,
           "vendas_tam": -1, "twitch": None, "chat": []}


def _c() -> dict:
    return cfg("avatar_live", PLUGIN_SETTINGS)


def chave() -> str:
    d = ler_json(ARQ_CHAVE, {}) or {}
    if not d.get("chave"):
        d["chave"] = secrets.token_urlsafe(12)
        gravar_json(ARQ_CHAVE, d)
    return d["chave"]


def porta() -> int:
    try:
        return int(str(_c().get("porta") or 8766))
    except ValueError:
        return 8766


def endereco() -> str:
    return f"http://127.0.0.1:{porta()}/avatar?k={chave()}"


# ── reações (puro) ────────────────────────────────────────────────────────────
def expressao_do_texto(texto: str) -> str | None:
    t = str(texto or "").lower()
    for nome, padrao in REGRAS:
        if re.search(padrao, t):
            return nome
    return None


def reacao_do_chat(mensagens: list[str]) -> str | None:
    """Várias mensagens parecidas em pouco tempo viram reação (puro)."""
    votos: dict[str, int] = {}
    for m in mensagens:
        e = expressao_do_texto(m)
        if e:
            votos[e] = votos.get(e, 0) + 1
    if not votos:
        return None
    nome, n = max(votos.items(), key=lambda kv: kv[1])
    return nome if n >= 2 else None


def reagir(expressao: str, texto: str = "", segundos: float = 3.5) -> str:
    e = expressao if expressao in EXPRESSOES else "neutro"
    with _lock:
        _estado.update(expressao=e, expr_ate=time.time() + segundos)
        _estado["expr_id"] += 1
        if texto:
            _estado["texto"] = str(texto)[:120]
            _estado["texto_id"] += 1
    return e


def _legenda(texto: str) -> None:
    if not texto or not sim(_c().get("legenda", True)):
        return
    with _lock:
        _estado["texto"] = " ".join(str(texto).split())[:160]
        _estado["texto_id"] += 1


def _ao_turno(entrada: str, saida: str, interrompido: bool) -> None:
    if _estado["servidor"] is None:
        return
    e = expressao_do_texto(entrada) if expressao_do_texto(entrada) == "rir" else None
    e = expressao_do_texto(saida) or e
    if e:
        reagir(e)
    _legenda(saida)


def estado_atual() -> dict:
    fala, falando = 0.0, False
    try:
        from core import registro_ferramentas
        app = registro_ferramentas.app()
        if app is not None:
            falando = bool(getattr(app, "_is_speaking", False))
            fala = float(getattr(app, "_out_level", 0.0) or 0.0) if falando else 0.0
    except Exception:
        pass
    with _lock:
        if _estado["expressao"] != "neutro" and time.time() > _estado["expr_ate"]:
            _estado["expressao"] = "neutro"
            _estado["expr_id"] += 1
        return {"fala": round(min(1.0, fala), 3), "falando": falando, "expressao": _estado["expressao"],
                "expr_id": _estado["expr_id"], "texto": _estado["texto"], "texto_id": _estado["texto_id"]}


# ── vendas e Twitch ───────────────────────────────────────────────────────────
def _olhar_vendas() -> None:
    try:
        tam = ARQ_VENDAS.stat().st_size
    except OSError:
        return
    antes = _estado["vendas_tam"]
    _estado["vendas_tam"] = tam
    if antes < 0 or tam <= antes:
        return
    try:
        from plugins._dados_br import ler
        v = (ler(ARQ_VENDAS.name) or [{}])[-1]
        texto = f"Venda! {v['quantidade']}× {v['produto']}" if v.get("produto") else "Venda!"
    except Exception:
        texto = "Venda!"
    reagir("comemorar", texto, 5.0)


def ler_irc(linha: str) -> tuple[str, str, str] | None:
    """(tipo, usuário, texto) de uma linha do chat da Twitch (puro)."""
    m = re.match(r"^(?:@(\S+) )?:(\w+)!\S+ PRIVMSG #\w+ :(.*)$", linha)
    if m:
        return "msg", m.group(2), m.group(3)
    m = re.match(r"^(?:@(\S+) )?:tmi\.twitch\.tv USERNOTICE #\w+(?: :(.*))?$", linha)
    if m:
        tags = dict(kv.split("=", 1) for kv in (m.group(1) or "").split(";") if "=" in kv)
        if tags.get("msg-id") in ("sub", "resub", "subgift", "submysterygift", "raid"):
            return tags.get("msg-id", "sub"), tags.get("display-name", ""), m.group(2) or ""
    return None


def _twitch(canal: str) -> None:
    canal = canal.lower().lstrip("#").strip()
    while _estado["twitch"] == canal and _estado["servidor"] is not None:
        try:
            s = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=30)
            s.sendall(f"CAP REQ :twitch.tv/tags twitch.tv/commands\r\nPASS SCHMOOPIIE\r\nNICK justinfan{secrets.randbelow(80000) + 10000}\r\nJOIN #{canal}\r\n".encode())
            buf = ""
            while _estado["twitch"] == canal:
                dados = s.recv(4096)
                if not dados:
                    break
                buf += dados.decode("utf-8", "ignore")
                *linhas, buf = buf.split("\r\n")
                for ln in linhas:
                    if ln.startswith("PING"):
                        s.sendall(b"PONG :tmi.twitch.tv\r\n")
                        continue
                    r = ler_irc(ln)
                    if not r:
                        continue
                    tipo, quem, texto = r
                    if tipo == "msg":
                        agora = time.time()
                        _estado["chat"] = [(t, m) for t, m in _estado["chat"] if agora - t < 10] + [(agora, texto)]
                        e = reacao_do_chat([m for _t, m in _estado["chat"]])
                        if e and time.time() > _estado["expr_ate"]:
                            reagir(e)
                            _estado["chat"] = []
                    elif tipo == "raid":
                        reagir("surpresa", f"Raid de {quem}!", 5.0)
                    else:
                        reagir("comemorar", f"Valeu, {quem}!" if quem else "Valeu pelo sub!", 5.0)
            s.close()
        except Exception as e:
            print(f"[Avatar] Twitch: {e}")
        time.sleep(10)


def _vigiar() -> None:
    while _estado["servidor"] is not None:
        c = _c()
        if sim(c.get("vendas", True)):
            _olhar_vendas()
        canal = str(c.get("twitch") or "").strip().lower().lstrip("#")
        if canal and _estado["twitch"] != canal:
            _estado["twitch"] = canal
            threading.Thread(target=_twitch, args=(canal,), daemon=True, name="avatar_twitch").start()
        elif not canal:
            _estado["twitch"] = None
        time.sleep(5)


# ── servidor (só 127.0.0.1) ───────────────────────────────────────────────────
class _Atendente(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not secrets.compare_digest((q.get("k") or [""])[0], chave()):
            self.send_error(403)
            return
        if u.path == "/avatar":
            corpo = PAGINA.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if u.path == "/avatar/eventos":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                ultimo = ""
                ping = 0.0
                while _estado["servidor"] is not None:
                    dados = json.dumps(estado_atual(), ensure_ascii=False)
                    if dados != ultimo or time.time() - ping > 2:
                        self.wfile.write(f"data: {dados}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        ultimo, ping = dados, time.time()
                    time.sleep(0.07)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            return
        self.send_error(404)


def ligar() -> str:
    with _lock:
        if _estado["servidor"] is None:
            try:
                srv = ThreadingHTTPServer(("127.0.0.1", porta()), _Atendente)
            except OSError as e:
                return f"a porta {porta()} está ocupada ({e}); troque em ⚙ → Avatar da live"
            srv.daemon_threads = True
            _estado["servidor"] = srv
            threading.Thread(target=srv.serve_forever, daemon=True, name="avatar").start()
            threading.Thread(target=_vigiar, daemon=True, name="avatar_vigia").start()
    try:
        from core import ganchos_turno
        ganchos_turno.registrar(_ao_turno)
    except Exception:
        pass
    return ""


def desligar() -> None:
    with _lock:
        srv, _estado["servidor"] = _estado["servidor"], None
        _estado["twitch"] = None
    if srv is not None:
        srv.shutdown()
        srv.server_close()


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    if sim(_c().get("ligado")):
        erro = ligar()
        if erro:
            print(f"[Avatar] {erro}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "ligar":
            erro = ligar()
            if erro:
                return f"Não consegui ligar o avatar: {erro}."
            salvar_cfg("avatar_live", {"ligado": True})
            reagir("comemorar", "Online!", 3)
            try:
                import pyperclip
                pyperclip.copy(endereco())
                copiado = " (já copiei o endereço)"
            except Exception:
                copiado = ""
            return (f"Avatar ligado{copiado}. No OBS: Fontes → + → Navegador → URL {endereco()} , largura 400, "
                    "altura 400. O fundo é transparente: arraste para o canto.")
        if acao == "desligar":
            desligar()
            salvar_cfg("avatar_live", {"ligado": False})
            return "Avatar da live desligado."
        if acao == "reagir":
            if _estado["servidor"] is None:
                ligar()
            e = reagir(str(p.get("expressao") or "comemorar").lower(), str(p.get("texto") or ""))
            return f"Avatar: {e}."
        ligado = _estado["servidor"] is not None
        extra = f" Chat da Twitch: #{_estado['twitch']}." if _estado["twitch"] else ""
        return (f"Avatar {'ligado em ' + endereco() if ligado else 'desligado'}. Expressão agora: "
                f"{_estado['expressao']}.{extra}")
    except Exception as e:
        return f"O avatar falhou: {e}"
