"""
Porteiro de voz (fork PT-BR 2.13).

Controla com quem o JARVIS fala. Por padrão, só o dono. O dono pode apresentar
uma visita para uma conversa temporária (modo convidado), e retomar quando
quiser — sem nunca ficar trancado para fora.

    "Jarvis, só fale comigo."                 → liga o porteiro (só o dono)
    "Jarvis, agora quem fala é o João."       → abre conversa temporária com o João
    "Jarvis, sou eu de novo."                 → volta a falar com o dono
    "Jarvis, pode falar com todo mundo."      → desliga o porteiro

A regra de voz de verdade roda no core/porteiro.py (que o main.py consulta a
cada fala). Esta ferramenta é o controle manual + o que o próprio JARVIS chama
quando o dono apresenta ou retoma.
"""

from __future__ import annotations

import unicodedata

from core import porteiro
from plugins._comum import nome_usuario

PLUGIN = {
    "name": "porteiro_voz",
    "brief": "Voice gatekeeper: by default only the owner is served; the owner can present a guest for a "
             "temporary conversation and take over again.",
    "description": (
        "Controls who JARVIS talks to, by voice. action='apresentar' with nome=<name> when the OWNER presents a "
        "visitor ('agora quem fala é o João', 'fala com a Ana', 'deixa eu te apresentar o Pedro') — opens a "
        "temporary guest conversation (free tools only, nothing personal). action='voltar' when the owner takes "
        "over again ('sou eu de novo'). action='ligar' to enforce owner-only, 'desligar' to let anyone talk, "
        "'status' to report. The owner is never locked out: if the voice can't be confirmed, it is treated as the "
        "owner."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "apresentar | voltar | ligar | desligar | status"},
            "nome": {"type": "STRING", "description": "nome da visita (para 'apresentar')"},
        },
    },
}

PLUGIN_SETTINGS = {
    "namespace": "porteiro_voz",
    "title": "Porteiro de voz",
    "fields": [
        {"key": "estrito", "label": "Só responder para a minha voz (porteiro ligado)",
         "type": "toggle", "default": True},
        {"key": "janela_min", "label": "Minutos que a visita apresentada fica liberada",
         "type": "text", "default": "15", "placeholder": "15"},
    ],
}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def _sync_convidado(ligar: bool) -> None:
    try:
        from plugins import modo_convidado
        if ligar and not modo_convidado.ativo():
            modo_convidado.definir(True)
        elif not ligar and modo_convidado.ativo():
            modo_convidado.definir(False)
    except Exception as e:
        print(f"[PorteiroVoz] convidado: {e}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = _dobrar(p.get("action") or "status").strip()
    dono = nome_usuario() or "você"
    try:
        if acao in ("apresentar", "convidado", "visita", "passar"):
            nome = str(p.get("nome") or p.get("name") or "").strip() or "a visita"
            porteiro.abrir_convidado(nome)
            _sync_convidado(True)
            return (f"Prazer, {nome}! Posso ajudar com conversa, música, clima, pesquisa e jogos. "
                    f"Coisas pessoais do {dono} ficam de fora até ele voltar.")
        if acao in ("voltar", "sou_eu", "retomar", "dono", "eu"):
            porteiro.fechar_convidado()
            _sync_convidado(False)
            return f"Voltando a falar só com você, {dono}."
        if acao in ("ligar", "ativar", "trancar", "so_eu", "so_comigo"):
            porteiro.definir_estrito(True)
            return (f"Porteiro ligado: a partir de agora eu só atendo você, {dono}. "
                    f"Se quiser que eu fale com alguém, é só me apresentar a pessoa.")
        if acao in ("desligar", "desativar", "liberar", "todo_mundo", "todos"):
            porteiro.definir_estrito(False)
            _sync_convidado(False)
            return "Porteiro desligado: posso conversar com qualquer pessoa agora."
        # status
        e = porteiro.estado_atual()
        if not e.get("estrito", True):
            return "O porteiro está desligado — converso com qualquer pessoa."
        if e.get("modo") == "convidado":
            return f"Conversa temporária aberta com {e.get('convidado') or 'a visita'}. Diga 'sou eu de novo' para retomar."
        return f"Porteiro ligado: só atendo você, {dono}."
    except Exception as e:
        return f"O porteiro de voz falhou: {e}"
