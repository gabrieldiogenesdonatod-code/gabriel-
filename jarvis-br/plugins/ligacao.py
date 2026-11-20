"""
JARVIS te liga de verdade (fork PT-BR 1.5).

Em alerta CRÍTICO (a sentinela disparou, o servidor caiu, um alarme de
fumaça) ele faz uma LIGAÇÃO para o seu celular e fala a mensagem em
português — mesmo com o celular no silencioso para notificações.

Usa a Twilio (twilio.com), pela API REST (sem pacote extra):
    1. crie uma conta (a de teste é grátis, mas só liga para números que você
       verificar lá);
    2. pegue um número da Twilio;
    3. em ⚙ CONFIG. DE PLUGINS → Ligação de alerta: Account SID, Auth Token,
       o número da Twilio e o seu número (formato +55, DDD e número: +5511987654321).

    "Jarvis, testa a ligação"

2.3 — o mesmo número também ATENDE (plugins/_atendente_voz.py):
    "Jarvis, liga o atendimento de ligações"   → aponta o número da Twilio para este PC
Você (do "Seu número" + PIN) conversa com o JARVIS por voz; outras pessoas
falam com a secretária, que anota o recado.

Limites para não virar spam: no máximo uma ligação a cada 10 minutos e 5 por dia.
"""

from __future__ import annotations

import html
import threading
import time
from datetime import date

from plugins._comum import cfg

PLUGIN = {
    "name": "ligacao",
    "brief": "Places a real phone call (Twilio) for critical alerts; test it.",
    "description": (
        "Real phone call for critical alerts (sentinel triggered, server down, smoke alarm) via Twilio. "
        "action='testar' places a test call; 'status' says if it is configured; 'ligar' with mensagem calls now "
        "(only when the user explicitly asks). 'atender' makes the Twilio number ANSWER incoming calls (owner + PIN "
        "talks to JARVIS; anyone else gets the secretary that takes a message); 'parar_atender' stops answering."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "testar | status | ligar | atender | parar_atender"},
                       "mensagem": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "ligacao",
    "title": "Ligação de alerta (Twilio)",
    "fields": [
        {"key": "sid", "label": "Account SID", "type": "text", "default": ""},
        {"key": "token", "label": "Auth Token", "type": "password", "default": ""},
        {"key": "de", "label": "Número da Twilio (+1…)", "type": "text", "default": ""},
        {"key": "para", "label": "Seu número (+55 DDD número)", "type": "text", "default": ""},
        {"key": "criticos", "label": "Ligar em alertas críticos", "type": "toggle", "default": True},
        {"key": "atender", "label": "Atender quem liga para o número da Twilio (secretária; você com PIN)",
         "type": "toggle", "default": False},
        {"key": "pin", "label": "PIN para VOCÊ falar com o JARVIS ligando (só números, 4 a 8)", "type": "password",
         "default": ""},
    ],
}

_controle = {"ultima": 0.0, "dia": "", "hoje": 0}
_lock = threading.Lock()


def _c() -> dict:
    return cfg("ligacao", PLUGIN_SETTINGS)


def configurada() -> bool:
    c = _c()
    return all(str(c.get(k) or "").strip() for k in ("sid", "token", "de", "para"))


def twiml(mensagem: str) -> str:
    """O roteiro da ligação: fala duas vezes, devagar (pura)."""
    m = html.escape(mensagem.strip()[:600])
    return ('<Response><Say language="pt-BR" voice="Polly.Camila">' + m + '</Say><Pause length="1"/>'
            '<Say language="pt-BR" voice="Polly.Camila">Repetindo. ' + m + '</Say></Response>')


def pode_ligar(agora: float | None = None) -> bool:
    agora = agora or time.time()
    hoje = date.fromtimestamp(agora).isoformat()
    with _lock:
        if _controle["dia"] != hoje:
            _controle.update(dia=hoje, hoje=0)
        return agora - _controle["ultima"] >= 600 and _controle["hoje"] < 5


def ligar(mensagem: str, forcar: bool = False) -> str:
    if not configurada():
        return "A ligação não está configurada (Twilio) em Configurações, Plugins, Ligação de alerta."
    if not forcar and not pode_ligar():
        return "Já liguei há pouco (limite de uma a cada 10 minutos e 5 por dia)."
    c = _c()
    try:
        import requests
        r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{c['sid'].strip()}/Calls.json",
                          auth=(c["sid"].strip(), c["token"].strip()), timeout=20,
                          data={"To": c["para"].strip(), "From": c["de"].strip(), "Twiml": twiml(mensagem)})
    except Exception as e:
        return f"Não consegui ligar: {e}"
    if r.status_code >= 300:
        try:
            erro = r.json().get("message", r.text[:160])
        except Exception:
            erro = r.text[:160]
        return f"A Twilio recusou a ligação: {erro}"
    with _lock:
        _controle["ultima"] = time.time()
        _controle["hoje"] += 1
    return "Ligação feita."


def alerta_critico(mensagem: str) -> None:
    """Chamado pelo _notificar em avisos 'urgent'. Nunca bloqueia."""
    if not configurada() or str(_c().get("criticos", True)).lower() in ("false", "0", "nao", "não"):
        return
    if not pode_ligar():
        return
    threading.Thread(target=ligar, args=(f"Alerta do Jarvis. {mensagem}",), daemon=True).start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "testar":
            return ligar("Teste do Jarvis. Se você está ouvindo isso, as ligações de alerta funcionam.", forcar=True)
        if acao in ("atender", "parar_atender"):
            from plugins import _atendente_voz as A
            return A.ligar_atendimento() if acao == "atender" else A.desligar_atendimento()
        if acao == "ligar":
            msg = str(p.get("mensagem") or "").strip()
            return ligar(msg, forcar=True) if msg else "Qual mensagem devo falar na ligação?"
        return ("Ligação de alerta configurada para " + _c()["para"][-4:].rjust(8, "•") + "."
                if configurada() else "A ligação ainda não está configurada (precisa de uma conta Twilio).")
    except Exception as e:
        return f"A ligação falhou: {e}"
