"""
Discord do JARVIS (fork PT-BR 2.0). Começa com "_": não é ferramenta.

Bot do Discord só com a biblioteca padrão (API REST): o JARVIS conversa com
você por mensagem direta (DM). Passo a passo no INSTALAR.txt:
  1. discord.com/developers/applications → New Application → Bot → Reset Token (copie);
  2. cole o token e o SEU ID do Discord (Configurações → Avançado → Modo desenvolvedor;
     clique com o direito no seu nome → Copiar ID) em ⚙ → Discord do JARVIS;
  3. "Jarvis, liga o Discord" mostra o link para pôr o bot num servidor seu
     (o Discord só deixa um bot mandar DM para quem está num servidor com ele).
Só as mensagens do SEU ID são atendidas.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json

API = "https://discord.com/api/v10"
ARQ = MEMORIA / "discord.json"
UA = "DiscordBot (https://github.com/FatihMakes/Mark-LVI, 2.0)"
from plugins._config_mensageiros import PLUGIN_SETTINGS  # noqa: E402

_estado = {"thread": None, "canal": "", "ultimo": "", "erro": "", "bot_id": ""}
_parar = threading.Event()


def config() -> dict:
    c = cfg("mensageiros", PLUGIN_SETTINGS)
    return {"token": c.get("discord_token", ""), "dono_id": c.get("discord_dono_id", ""),
            "ligar_ao_abrir": c.get("ligar_ao_abrir", True)}


def chamar(metodo: str, caminho: str, corpo: dict | None = None, tok: str | None = None,
           dados_brutos: bytes | None = None, tipo: str = "application/json") -> dict | list:
    tok = tok or str(config().get("token") or "").strip()
    if not tok:
        raise RuntimeError("Discord sem token")
    for _ in range(3):
        req = urllib.request.Request(API + caminho, method=metodo,
                                     data=dados_brutos if dados_brutos is not None else
                                     (json.dumps(corpo).encode() if corpo is not None else None),
                                     headers={"Authorization": f"Bot {tok}", "User-Agent": UA, "Content-Type": tipo})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                bruto = r.read()
                return json.loads(bruto) if bruto else {}
        except urllib.error.HTTPError as e:
            corpo_erro = e.read()
            if e.code == 429:                                   # limite de velocidade: espera o que o Discord pedir
                try:
                    time.sleep(min(10.0, float(json.loads(corpo_erro).get("retry_after", 2))))
                except ValueError:
                    time.sleep(2)
                continue
            raise RuntimeError(f"Discord {e.code}: {corpo_erro[:200].decode('utf-8', 'replace')}") from None
    raise RuntimeError("Discord: limite de velocidade")


def link_convite(app_id: str) -> str:
    return f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=bot&permissions=0"


def canal_dm() -> str:
    if _estado["canal"]:
        return _estado["canal"]
    dono = str(config().get("dono_id") or "").strip()
    if not dono.isdigit():
        raise RuntimeError("falta o seu ID do Discord")
    _estado["canal"] = str(chamar("POST", "/users/@me/channels", {"recipient_id": dono})["id"])
    return _estado["canal"]


def enviar(texto: str) -> bool:
    try:
        for i in range(0, max(1, len(texto)), 1900):           # limite de 2000 caracteres por mensagem
            chamar("POST", f"/channels/{canal_dm()}/messages", {"content": texto[i:i + 1900]})
        return True
    except Exception as e:
        print(f"[Discord] envio falhou: {e}")
        return False


def enviar_arquivo(legenda: str, arquivo: Path) -> bool:
    arquivo = Path(arquivo)
    limite = uuid.uuid4().hex
    corpo = (f"--{limite}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json\r\n\r\n"
             + json.dumps({"content": legenda[:1900]}) + "\r\n"
             + f"--{limite}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"{arquivo.name}\"\r\n"
             "Content-Type: application/octet-stream\r\n\r\n").encode() + arquivo.read_bytes() + f"\r\n--{limite}--\r\n".encode()
    try:
        chamar("POST", f"/channels/{canal_dm()}/messages", dados_brutos=corpo, tipo=f"multipart/form-data; boundary={limite}")
        return True
    except Exception as e:
        print(f"[Discord] arquivo falhou: {e}")
        return False


def mensagens_do_dono(msgs: list[dict], dono: str) -> list[dict]:
    """Do mais antigo ao mais novo, só as do dono (pura)."""
    return sorted([m for m in msgs if str((m.get("author") or {}).get("id")) == str(dono)], key=lambda m: int(m["id"]))


def _baixar(anexo: dict) -> tuple[str | None, str]:
    nome = str(anexo.get("filename") or "").lower()
    tipo = "voz" if nome.endswith((".ogg", ".mp3", ".m4a", ".wav")) else "foto" if nome.endswith((".png", ".jpg", ".jpeg")) else ""
    if not tipo:
        return None, ""
    import tempfile
    destino = Path(tempfile.gettempdir()) / f"jarvis_dc_{anexo.get('id', 'x')}_{Path(nome).name}"
    try:
        with urllib.request.urlopen(urllib.request.Request(anexo["url"], headers={"User-Agent": UA}), timeout=60) as r:
            destino.write_bytes(r.read())
        return str(destino), tipo
    except Exception:
        return None, ""


def _laco() -> None:
    from plugins._conversa_remota import atender
    d = ler_json(ARQ, {}) or {}
    while not _parar.is_set():
        try:
            canal = canal_dm()
            if not _estado["ultimo"]:
                ultimas = chamar("GET", f"/channels/{canal}/messages?limit=1")
                _estado["ultimo"] = str(d.get("ultimo") or (ultimas[0]["id"] if ultimas else "0"))
            msgs = chamar("GET", f"/channels/{canal}/messages?after={_estado['ultimo']}&limit=20")
            _estado["erro"] = ""
            dono = str(config().get("dono_id") or "")
            for m in msgs or []:
                _estado["ultimo"] = str(max(int(_estado["ultimo"] or 0), int(m["id"])))
            for m in mensagens_do_dono(msgs or [], dono):
                arquivo, tipo = (_baixar(m["attachments"][0]) if m.get("attachments") else (None, ""))
                atender(m.get("content") or "", enviar, enviar_arquivo, "discord", arquivo, tipo)
            if msgs:
                gravar_json(ARQ, {"ultimo": _estado["ultimo"]})
        except Exception as e:
            _estado["erro"] = str(e)
            time.sleep(15)
        time.sleep(3)


def iniciar() -> tuple[str, str]:
    """('', link para convidar o bot) se ligou; (erro, '') se não."""
    t = _estado["thread"]
    c = config()
    if not str(c.get("token") or "").strip():
        return "falta o token do bot", ""
    try:
        eu = chamar("GET", "/users/@me")
        _estado["bot_id"] = str(eu.get("id", ""))
    except Exception as e:
        return f"o Discord recusou o token: {e}", ""
    convite = link_convite(_estado["bot_id"])
    if t is not None and t.is_alive():
        return "", convite
    try:
        canal_dm()
    except Exception as e:
        return f"{e} (o bot precisa estar num servidor com você: {convite})", convite
    _parar.clear()
    _estado["thread"] = threading.Thread(target=_laco, daemon=True, name="discord")
    _estado["thread"].start()
    return "", convite


def rodando() -> bool:
    t = _estado["thread"]
    return t is not None and t.is_alive()


def parar() -> None:
    _parar.set()
