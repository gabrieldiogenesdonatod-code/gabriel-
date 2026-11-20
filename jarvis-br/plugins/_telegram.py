"""
Telegram do JARVIS (fork PT-BR 2.0). Começa com "_": não é ferramenta.

Bot oficial e grátis, só com a biblioteca padrão (API HTTP do Telegram, long
polling). Crie o bot com o @BotFather, cole o token em ⚙ → Telegram do JARVIS
e mande o código de autorização para o bot. Só os chats autorizados conversam
com o JARVIS; o resto é ignorado.
"""

from __future__ import annotations

import json
import secrets
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json

ARQ = MEMORIA / "telegram.json"
from plugins._config_mensageiros import PLUGIN_SETTINGS  # noqa: E402

_estado = {"thread": None, "offset": 0, "erro": "", "bot": ""}
_parar = threading.Event()


def token() -> str:
    return str(cfg("mensageiros", PLUGIN_SETTINGS).get("telegram_token") or "").strip()


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("chats", [])
    d.setdefault("codigo", "")
    return d


def chamar(metodo: str, params: dict | None = None, timeout: float = 35, tok: str | None = None) -> dict:
    tok = tok or token()
    if not tok:
        raise RuntimeError("Telegram sem token")
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{metodo}",
                                 data=json.dumps(params or {}).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        resp = json.loads(e.read() or b"{}") or {"ok": False, "description": str(e)}
    if not resp.get("ok"):
        raise RuntimeError(resp.get("description") or "erro do Telegram")
    return resp.get("result")


def _multipart(campos: dict, arquivo_campo: str, arquivo: Path) -> tuple[bytes, str]:
    limite = uuid.uuid4().hex
    partes = []
    for k, v in campos.items():
        partes.append(f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    partes.append(f"--{limite}\r\nContent-Disposition: form-data; name=\"{arquivo_campo}\"; filename=\"{arquivo.name}\"\r\n"
                  "Content-Type: application/octet-stream\r\n\r\n".encode() + arquivo.read_bytes() + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def enviar(chat_id: int | str, texto: str, botoes: list[list[tuple[str, str]]] | None = None) -> bool:
    params = {"chat_id": chat_id, "text": texto[:4000]}
    if botoes:
        params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d[:64]} for t, d in linha]
                                                      for linha in botoes]}
    try:
        chamar("sendMessage", params, timeout=20)
        return True
    except Exception as e:
        print(f"[Telegram] envio falhou: {e}")
        return False


def enviar_arquivo(chat_id: int | str, legenda: str, arquivo: Path) -> bool:
    foto = Path(arquivo).suffix.lower() in (".jpg", ".jpeg", ".png")
    corpo, tipo = _multipart({"chat_id": chat_id, "caption": legenda[:1000]}, "photo" if foto else "document", Path(arquivo))
    req = urllib.request.Request(f"https://api.telegram.org/bot{token()}/{'sendPhoto' if foto else 'sendDocument'}",
                                 data=corpo, headers={"Content-Type": tipo})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return bool(json.loads(r.read()).get("ok"))
    except Exception as e:
        print(f"[Telegram] arquivo falhou: {e}")
        return False


def para_donos(texto: str, arquivo: Path | None = None, botoes=None) -> int:
    if not token():
        return 0
    n = 0
    for c in dados()["chats"]:
        n += bool(enviar_arquivo(c, texto, arquivo) if arquivo else enviar(c, texto, botoes))
    return n


def novo_codigo() -> str:
    d = dados()
    d["codigo"] = "J" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
    gravar_json(ARQ, d)
    return d["codigo"]


def decidir(msg: dict, chats: list, codigo: str) -> str:
    """'dono', 'parear' ou 'ignorar' (pura). Só conversas privadas."""
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return "ignorar"
    if chat.get("id") in chats:
        return "dono"
    texto = str(msg.get("text") or "")
    if codigo and codigo.upper() in texto.upper():
        return "parear"
    return "ignorar"


def _baixar(file_id: str) -> Path | None:
    try:
        info = chamar("getFile", {"file_id": file_id}, timeout=20)
        destino = Path(tempfile.gettempdir()) / f"jarvis_tg_{file_id[-12:]}{Path(info['file_path']).suffix or '.ogg'}"
        with urllib.request.urlopen(f"https://api.telegram.org/file/bot{token()}/{info['file_path']}", timeout=60) as r:
            destino.write_bytes(r.read())
        return destino
    except Exception as e:
        print(f"[Telegram] download falhou: {e}")
        return None


def tratar(upd: dict) -> None:
    from plugins._conversa_remota import atender
    if upd.get("callback_query"):                                # botão de uma oferta do companheiro
        cq = upd["callback_query"]
        chat_id = ((cq.get("message") or {}).get("chat") or {}).get("id")
        try:
            chamar("answerCallbackQuery", {"callback_query_id": cq["id"]}, timeout=10)
        except Exception:
            pass
        if chat_id not in dados()["chats"]:
            return
        from plugins import companheiro
        r = companheiro.responder_oferta(str(cq.get("data") or ""))
        if r:
            enviar(chat_id, r)
        return
    msg = upd.get("message") or {}
    d = dados()
    decisao = decidir(msg, d["chats"], d["codigo"])
    chat_id = (msg.get("chat") or {}).get("id")
    if decisao == "ignorar":
        return
    if decisao == "parear":
        d["chats"] = list(dict.fromkeys(d["chats"] + [chat_id]))
        d["codigo"] = ""
        gravar_json(ARQ, d)
        enviar(chat_id, "Pronto! Este Telegram agora fala com o J.A.R.V.I.S. Mande 'ajuda' para ver o que dá para fazer.")
        return
    arquivo, tipo = None, ""
    if msg.get("voice") or msg.get("audio"):
        arquivo, tipo = _baixar((msg.get("voice") or msg.get("audio"))["file_id"]), "voz"
    elif msg.get("photo"):
        arquivo, tipo = _baixar(msg["photo"][-1]["file_id"]), "foto"
    texto = str(msg.get("text") or msg.get("caption") or "")
    if texto.strip() == "/start":
        texto = "ajuda"
    atender(texto, lambda t: enviar(chat_id, t), lambda legenda, arq: enviar_arquivo(chat_id, legenda, arq), "telegram",
            str(arquivo) if arquivo else None, tipo)


def _laco() -> None:
    while not _parar.is_set():
        try:
            upds = chamar("getUpdates", {"offset": _estado["offset"], "timeout": 25,
                                         "allowed_updates": ["message", "callback_query"]}, timeout=35)
            _estado["erro"] = ""
            for u in upds or []:
                _estado["offset"] = max(_estado["offset"], int(u["update_id"]) + 1)
                try:
                    tratar(u)
                except Exception as e:
                    print(f"[Telegram] {e}")
        except Exception as e:
            _estado["erro"] = str(e)
            time.sleep(10)


def iniciar() -> str:
    t = _estado["thread"]
    if t is not None and t.is_alive():
        return ""
    if not token():
        return "falta o token do bot"
    try:
        eu = chamar("getMe", timeout=15)
        _estado["bot"] = eu.get("username", "")
    except Exception as e:
        return f"o Telegram recusou o token: {e}"
    _parar.clear()
    _estado["thread"] = threading.Thread(target=_laco, daemon=True, name="telegram")
    _estado["thread"].start()
    return ""


def rodando() -> bool:
    t = _estado["thread"]
    return t is not None and t.is_alive()


def parar() -> None:
    _parar.set()
