"""
Geofence pelo celular (fork PT-BR 1.5).

O celular avisa o JARVIS quando você CHEGA e quando SAI de casa:
    chegou → (se o PC estava desligado, o celular manda o Wake-on-LAN) e o
             JARVIS roda o protocolo de chegada que você escolher e dá boas-vindas;
    saiu   → a sessão confiável fecha e a Sentinela liga sozinha.

COMO O AVISO VIAJA: o script do celular (Termux) publica num tópico secreto
do ntfy, e o JARVIS fica inscrito nele. Funciona fora de casa (quando você
sai, o celular já não está na rede do PC) e não precisa abrir porta no roteador.
Cada aviso leva a chave do geofence; aviso sem a chave certa é ignorado.

    "Jarvis, configura o geofence"   → tópico, chave e o caminho do script
    "Jarvis, status do geofence"     "Jarvis, simula que eu cheguei"

Script do celular e passo a passo: celular/termux/ (LEIA-ME.md).
"""

from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.request
from datetime import datetime

from plugins._comum import BASE, cfg, falar, mostrar, registrar, salvar_cfg

PLUGIN = {
    "name": "geofence",
    "brief": "Phone geofence (Termux): arrive home → protocol + welcome; leave → close session + sentinel.",
    "description": (
        "Geofence events from the user's phone (Termux script → secret ntfy topic). Arriving runs the chosen "
        "arrival protocol and welcomes; leaving closes the trusted session and arms the sentinel. "
        "action='configurar' (shows topic/key for the phone script), 'status', 'simular' with evento "
        "(chegou|saiu), 'protocolo' with nome (arrival protocol)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "configurar | status | simular | protocolo"},
            "evento": {"type": "STRING"}, "nome": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "geofence",
    "title": "Geofence (celular)",
    "fields": [
        {"key": "ligado", "label": "Ouvir os avisos do celular", "type": "toggle", "default": True},
        {"key": "protocolo_chegada", "label": "Protocolo ao chegar (vazio = só boas-vindas)", "type": "text",
         "default": ""},
        {"key": "encerrar_ao_sair", "label": "Fechar a sessão confiável quando eu sair", "type": "toggle",
         "default": True},
    ],
}

_estado = {"ultimo": None, "conectado": False}
_iniciado = threading.Event()


def _sim(v) -> bool:
    return str(v).strip().lower() not in ("false", "0", "nao", "não", "off")


def credenciais() -> tuple[str, str]:
    """(tópico, chave) — criados na primeira vez e guardados nas configurações."""
    c = cfg("geofence", PLUGIN_SETTINGS)
    topico, chave = str(c.get("topico") or ""), str(c.get("chave") or "")
    if not topico or not chave:
        topico = topico or "jarvis-geo-" + secrets.token_hex(8)
        chave = chave or secrets.token_urlsafe(12)
        salvar_cfg("geofence", {"topico": topico, "chave": chave})
    return topico, chave


def interpretar(texto: str, chave: str) -> str | None:
    """'chegou <chave>' → 'chegou' (pura). None se a chave não bate."""
    partes = (texto or "").strip().split()
    if len(partes) != 2 or partes[0] not in ("chegou", "saiu") or not secrets.compare_digest(partes[1], chave):
        return None
    return partes[0]


def tratar(evento: str, player) -> str:
    from core import verificacao
    c = cfg("geofence", PLUGIN_SETTINGS)
    _estado["ultimo"] = (evento, time.time())
    try:
        from plugins import _monitor_db
        _monitor_db.gravar_evento("geofence", f"você {evento} de casa" if evento == "saiu" else "você chegou em casa")
    except Exception:
        pass
    if evento == "saiu":
        if _sim(c.get("encerrar_ao_sair", True)):
            verificacao.encerrar("você saiu de casa (geofence)")
        verificacao.avisar_evento("geofence_saiu", "")
        registrar(player, "Geofence: você saiu de casa.")
        return "saiu"
    verificacao.avisar_evento("geofence_chegou", "")
    registrar(player, "Geofence: você chegou em casa.")
    nome = str(c.get("protocolo_chegada") or "").strip()
    if nome:
        try:
            from plugins import protocolos
            threading.Thread(target=protocolos._executar, args=(nome, player), daemon=True).start()
        except Exception as e:
            print(f"[Geofence] protocolo: {e}")
    falar(player, "[GEOFENCE] O celular do usuário avisou que ele acabou de chegar em casa. Dê boas-vindas em UMA "
                  "frase curta, no estilo J.A.R.V.I.S. Não chame nenhuma ferramenta.")
    return "chegou"


def _servidor() -> str:
    try:
        from plugins._notificar import _config
        return str(_config().get("ntfy_servidor") or "https://ntfy.sh").rstrip("/")
    except Exception:
        return "https://ntfy.sh"


def _ouvir(player) -> None:
    espera = 5
    while True:
        if not _sim(cfg("geofence", PLUGIN_SETTINGS).get("ligado", True)):
            time.sleep(60)
            continue
        topico, chave = credenciais()
        try:
            req = urllib.request.Request(f"{_servidor()}/{topico}/json", headers={"User-Agent": "JARVIS-BR/1.5"})
            with urllib.request.urlopen(req, timeout=120) as r:
                _estado["conectado"] = True
                espera = 5
                for linha in r:
                    try:
                        msg = json.loads(linha.decode("utf-8"))
                    except Exception:
                        continue
                    if msg.get("event") != "message":
                        continue
                    evento = interpretar(msg.get("message", ""), chave)
                    if evento:
                        tratar(evento, player)
        except Exception as e:
            _estado["conectado"] = False
            print(f"[Geofence] reconectando: {e}")
        time.sleep(espera)
        espera = min(300, espera * 2)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_ouvir, args=(player,), daemon=True, name="geofence").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        topico, chave = credenciais()
        if acao == "configurar":
            script = BASE / "celular" / "termux" / "jarvis_geofence.py"
            mostrar(player, "GEOFENCE — CONFIGURAÇÃO",
                    f"No celular, edite o começo de {script.name}:\n\n"
                    f'  SERVIDOR = "{_servidor()}"\n  TOPICO   = "{topico}"\n  CHAVE    = "{chave}"\n'
                    '  REDE_CASA = "nome do seu Wi-Fi"\n  PC_MAC    = "MAC do PC (para ligar o PC ao chegar)"\n\n'
                    f"Script e passo a passo: {script.parent}\\LEIA-ME.md")
            return "A configuração do geofence está no painel: copie o tópico e a chave para o script do celular."
        if acao == "simular":
            evento = "saiu" if "sai" in str(p.get("evento") or "").lower() else "chegou"
            return f"Simulei: você {tratar(evento, player)}."
        if acao == "protocolo":
            nome = str(p.get("nome") or "").strip()
            salvar_cfg("geofence", {"protocolo_chegada": nome})
            return f"Ao chegar em casa vou rodar o protocolo {nome}." if nome else "Ao chegar, só dou boas-vindas."
        ultimo = _estado["ultimo"]
        estado = "ouvindo o celular" if _estado["conectado"] else "tentando conectar ao ntfy"
        if ultimo:
            return f"Geofence {estado}. Último aviso: você {ultimo[0]} às {datetime.fromtimestamp(ultimo[1]):%H:%M}."
        return f"Geofence {estado}. Ainda não recebi aviso do celular."
    except Exception as e:
        return f"O geofence falhou: {e}"
