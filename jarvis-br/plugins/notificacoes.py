"""
Notificações no celular (fork PT-BR 1.4).

Configuração do push pelo ntfy (grátis, sem conta) e um teste:

    "Jarvis, testa a notificação no celular"

Veja plugins/_notificar.py para o passo a passo.
"""

from __future__ import annotations

from plugins._notificar import PLUGIN_SETTINGS as _PS
from plugins._notificar import _config, enviar_push

PLUGIN = {
    "name": "notificacoes",
    "brief": "Test or check phone push notifications (ntfy).",
    "description": (
        "Phone notifications for JARVIS alerts (price watch, store calendar, anomalies, watchers). "
        "action='testar' sends a test push to the phone; 'status' says whether a topic is set."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "testar | status"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = _PS


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    topico = str(_config().get("ntfy_topico") or "").strip()
    if not topico:
        return ("O push no celular não está configurado. Instale o app ntfy no celular, assine um tópico "
                "com nome difícil de adivinhar e coloque o mesmo nome em Configurações, Plugins, "
                "Notificações no celular.")
    if acao == "testar":
        ok = enviar_push("Teste do J.A.R.V.I.S BR: se você está lendo isso, os avisos chegam no celular.",
                         "J.A.R.V.I.S", esperar=True)
        return "Mandei a notificação de teste." if ok else "Não consegui mandar: confira a internet e o tópico."
    return f"Push configurado no tópico {topico[:3]}… (ntfy)."
