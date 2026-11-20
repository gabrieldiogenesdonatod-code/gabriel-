"""
Vigia de servidores e sites (fork PT-BR 1.5).

Confere a cada minuto se os seus sites/servidores respondem (HTTP ou porta
TCP). Três falhas seguidas = CAÍDO: avisa por voz, no celular e — se a
ligação de alerta estiver configurada — te LIGA. Quando volta, avisa também.

    "Jarvis, vigia o site meusite.com.br"
    "Jarvis, vigia o servidor 203.0.113.10 porta 22"
    "Jarvis, como estão os servidores?"        "Jarvis, para de vigiar o meusite"
"""

from __future__ import annotations

import re
import socket
import threading
import time
from datetime import datetime

from plugins._comum import CONFIG, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "servidores",
    "brief": "Uptime watcher for the user's sites/servers (HTTP or TCP port); critical alert + call when down.",
    "description": (
        "Watches the user's websites and servers every minute (HTTP status or TCP port). action='adicionar' with "
        "alvo (URL, domain, or host plus porta) and optional nome; 'status' ('how are my servers?'); 'remover' "
        "with alvo/nome; 'verificar' to check now. Three failures in a row = down: voice, phone push and a call."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "adicionar | status | remover | verificar"},
            "alvo": {"type": "STRING"}, "nome": {"type": "STRING"}, "porta": {"type": "INTEGER"},
        },
        "required": ["action"],
    },
}

ARQ = CONFIG / "servidores.json"
_estado: dict[str, dict] = {}
_iniciado = threading.Event()


def normalizar(alvo: str, porta: int | None = None) -> dict:
    """'meusite.com.br' → https://meusite.com.br ; '1.2.3.4' + 22 → tcp (pura)."""
    a = alvo.strip()
    m = re.match(r"^([\w.-]+):(\d{2,5})$", a)
    if m and not a.startswith("http"):
        return {"tipo": "tcp", "host": m.group(1), "porta": int(m.group(2))}
    if porta:
        host = re.sub(r"^https?://", "", a).split("/")[0]
        return {"tipo": "tcp", "host": host, "porta": int(porta)}
    if not a.startswith(("http://", "https://")):
        a = "https://" + a
    return {"tipo": "http", "url": a}


def checar(s: dict, timeout: float = 10) -> tuple[bool, str]:
    t0 = time.perf_counter()
    try:
        if s["tipo"] == "tcp":
            with socket.create_connection((s["host"], int(s["porta"])), timeout=timeout):
                pass
            return True, f"{(time.perf_counter() - t0) * 1000:.0f} ms"
        import urllib.request
        req = urllib.request.Request(s["url"], method="GET", headers={"User-Agent": "JARVIS-BR/1.5 (uptime)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ok = r.status < 500
            return ok, f"HTTP {r.status}, {(time.perf_counter() - t0) * 1000:.0f} ms"
    except Exception as e:
        cod = getattr(e, "code", None)
        if cod and int(cod) < 500:                       # 401/403/404: o servidor está de pé
            return True, f"HTTP {cod}"
        return False, str(getattr(e, "reason", e))[:120]


def _nome(s: dict) -> str:
    return s.get("nome") or s.get("url") or f"{s.get('host')}:{s.get('porta')}"


def rodada(player=None) -> list[str]:
    from plugins._notificar import notificar
    msgs = []
    for s in ler_json(ARQ, []) or []:
        chave = _nome(s)
        e = _estado.setdefault(chave, {"falhas": 0, "caido": False, "desde": 0.0, "ultimo": ""})
        ok, info = checar(s)
        e["ultimo"] = info
        if ok:
            if e["caido"]:
                minutos = (time.time() - e["desde"]) / 60
                notificar(player, f"{chave} voltou ({info}) depois de {minutos:.0f} min fora.", titulo="Servidores",
                          etiqueta="SERVIDOR")
                msgs.append(f"{chave} voltou")
            e.update(falhas=0, caido=False)
        else:
            e["falhas"] += 1
            if e["falhas"] == 3 and not e["caido"]:
                e.update(caido=True, desde=time.time())
                notificar(player, f"{chave} está FORA DO AR ({info}).", titulo="Servidores", etiqueta="SERVIDOR",
                          prioridade="urgent")
                try:
                    from plugins import _monitor_db
                    _monitor_db.gravar_evento("alerta", f"Servidor fora do ar: {chave} ({info})")
                except Exception:
                    pass
                msgs.append(f"{chave} caiu")
    return msgs


def _laco(player) -> None:
    time.sleep(45)
    while True:
        try:
            if ler_json(ARQ, []):
                rodada(player)
        except Exception as e:
            print(f"[Servidores] {e}")
        time.sleep(60)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="servidores").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        lista = ler_json(ARQ, []) or []
        if acao == "adicionar":
            alvo = str(p.get("alvo") or "").strip()
            if not alvo:
                return "Qual site ou servidor devo vigiar?"
            s = normalizar(alvo, int(p["porta"]) if p.get("porta") else None)
            s["nome"] = str(p.get("nome") or "").strip() or re.sub(r"^https?://", "", alvo).split("/")[0]
            lista.append(s)
            gravar_json(ARQ, lista)
            ok, info = checar(s)
            return f"Vigiando {s['nome']}. Agora: {'no ar' if ok else 'FORA DO AR'} ({info})."
        if acao == "remover":
            alvo = str(p.get("alvo") or p.get("nome") or "").lower()
            restantes = [s for s in lista if alvo not in _nome(s).lower() and alvo not in str(s).lower()]
            gravar_json(ARQ, restantes)
            return "Parei de vigiar." if len(restantes) < len(lista) else "Não achei esse servidor na lista."
        if not lista:
            return "Não estou vigiando nenhum servidor. Diga, por exemplo: vigia o site meusite.com.br."
        linhas = []
        for s in lista:
            ok, info = checar(s) if acao == "verificar" else (not _estado.get(_nome(s), {}).get("caido"),
                                                             _estado.get(_nome(s), {}).get("ultimo", "aguardando"))
            linhas.append(f"{'🟢' if ok else '🔴'} {_nome(s)} — {info}")
        mostrar(player, f"SERVIDORES — {datetime.now():%H:%M}", "\n".join(linhas))
        caidos = [l for l in linhas if l.startswith("🔴")]
        return (f"{len(caidos)} fora do ar: " + "; ".join(l[2:] for l in caidos) if caidos
                else f"Todos os {len(lista)} no ar.")
    except Exception as e:
        return f"O vigia de servidores falhou: {e}"
