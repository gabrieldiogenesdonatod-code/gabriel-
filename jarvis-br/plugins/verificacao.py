"""
Verificação — o comando de voz e o vigia (fork PT-BR 1.5).

O núcleo está em core/verificacao.py. Aqui ficam:
    • ao abrir: reconhecer pelo rosto em silêncio (e confiar se você acabou de
      entrar no Windows), e ligar o vigia de bloqueio/suspensão;
    • os comandos:
        "Jarvis, você sabe quem eu sou?" / "status da verificação"
        "Jarvis, me verifica" (olhada na câmera / voz agora)
        "Jarvis, encerra a sessão"          (até você se verificar de novo)
        "Jarvis, deixa o gastos livre"      (muda o nível de uma ferramenta)
        "Jarvis, quem tentou usar comandos sensíveis?"   (histórico)
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from core import verificacao as v
from plugins._comum import mostrar, registrar, salvar_cfg

PLUGIN = {
    "name": "verificacao",
    "brief": "Owner verification: trusted session status, verify now, end session, command levels, history.",
    "description": (
        "Owner verification (face/voice/Windows unlock/phone key) and command levels. action='status' "
        "('do you know who I am?', 'am I verified?'), 'verificar' (verify now: camera/voice), 'encerrar' "
        "(end the trusted session), 'niveis' (list levels), 'nivel' with ferramenta + nivel "
        "(livre|sensivel|critico) to change one, 'historico' (recent verification events), 'ligar' / "
        "'desligar' the whole verification."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "status | verificar | encerrar | niveis | nivel | historico | ligar | desligar"},
            "ferramenta": {"type": "STRING"}, "nivel": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = v.PLUGIN_SETTINGS
_iniciado = threading.Event()
_NOMES = {"livre": v.LIVRE, "liberado": v.LIVRE, "qualquer um": v.LIVRE, "sensivel": v.SENSIVEL,
          "sensível": v.SENSIVEL, "so eu": v.SENSIVEL, "só eu": v.SENSIVEL, "critico": v.CRITICO,
          "crítico": v.CRITICO}


def on_session_start(player) -> None:
    if _iniciado.is_set():
        return
    _iniciado.set()
    v.iniciar_vigia()
    c = v.config()
    if not c["ligado"]:
        return
    if v.confiavel():
        return
    login = v.segundos_desde_login()
    if c["confiar_desbloqueio"] and login is not None and login < 300:
        v.confiar("windows")
        registrar(player, "Verificação: você acabou de entrar no Windows, sessão confiável.")
        return
    if c["rosto_ao_abrir"] and "rosto" in v.metodos():
        time.sleep(4)                                   # deixa a interface terminar de abrir
        if v.verificar_rosto(player, quadros=4):
            v.confiar("rosto")
            registrar(player, "Verificação: reconheci você pelo rosto.")
        else:
            registrar(player, "Verificação: não te vi na câmera; comandos sensíveis vão pedir verificação.")


def _hora(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M") if ts else "—"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "verificar":
            ok, fonte = v.provar_agora(player)
            if ok:
                v.confiar(fonte)
                return f"Confirmado pelo {fonte}. Sessão confiável até as {_hora(v.estado()['ate'])}."
            return f"Não consegui confirmar ({fonte})."
        if acao == "encerrar":
            v.encerrar("pedido do usuário")
            return "Sessão encerrada. Os comandos sensíveis vão pedir verificação."
        if acao in ("ligar", "desligar"):
            salvar_cfg("verificacao", {"ligado": acao == "ligar"})
            v.registrar(acao, "pelo comando de voz")
            return ("Verificação ligada." if acao == "ligar" else
                    "Verificação desligada: todos os comandos ficam liberados para quem estiver no PC.")
        if acao == "nivel":
            ferramenta = str(p.get("ferramenta") or "").strip().lower().replace(" ", "_")
            nivel = _NOMES.get(str(p.get("nivel") or "").strip().lower())
            if not ferramenta or not nivel:
                return "Diga a ferramenta e o nível: livre, sensível ou crítico."
            v.definir_nivel(ferramenta, nivel)
            v.registrar("nivel", f"{ferramenta} = {nivel}")
            return f"Pronto: {ferramenta} agora é {nivel}."
        if acao == "niveis":
            proprios = v.niveis_personalizados()
            linhas = ["SEUS AJUSTES"] + ([f"  {k}: {n}" for k, n in proprios.items()] or ["  nenhum"])
            for nivel in (v.CRITICO, v.SENSIVEL, v.LIVRE):
                linhas += ["", f"PADRÃO — {nivel.upper()}"] + [f"  {k}" for k, n in sorted(v.NIVEIS_PADRAO.items()) if n == nivel]
            linhas += ["", "O que não está na lista: o guardião decide (risco alto ou irreversível = sensível)."]
            mostrar(player, "NÍVEIS DE COMANDO", "\n".join(linhas))
            return ("Livre: conversar, música, clima, pesquisar. Sensível: seus dados, arquivos, mensagens e e-mail. "
                    "Crítico: desligar o PC, limpeza, instalar plugin, aplicar correção e mudar a segurança. "
                    "A lista completa está no painel.")
        if acao == "historico":
            import json
            log = json.loads(v.ARQ_LOG.read_text(encoding="utf-8")) if v.ARQ_LOG.exists() else []
            if not log:
                return "Ainda não há eventos de verificação."
            mostrar(player, "VERIFICAÇÃO — HISTÓRICO", "\n".join(
                f"{datetime.fromtimestamp(e['ts']):%d/%m %H:%M}  {e['evento']:<9} {e['detalhe']}" for e in log[-60:]))
            negados = [e for e in log if e["evento"] == "negou"]
            return (f"{len(log)} eventos. " + (f"{len(negados)} pedido(s) negado(s); o último às "
                                                f"{_hora(negados[-1]['ts'])}: {negados[-1]['detalhe']}." if negados
                                                else "Nenhum pedido negado."))
        e = v.estado()
        if not v.config()["ligado"]:
            return "A verificação está desligada: tudo fica liberado para quem estiver no PC."
        if not e["metodos"]:
            return ("Nenhum método cadastrado (rosto, voz ou chave), então vale o Windows: quem desbloqueou o PC é "
                    "tratado como você. Diga 'cadastra meu rosto' para ligar a verificação passiva.")
        if e["confiavel"]:
            return (f"Sim: você está verificado desde as {_hora(e['desde'])} ({e['fonte']}), até as {_hora(e['ate'])}. "
                    f"Métodos: {', '.join(e['metodos'])}.")
        return f"Agora não: a sessão está fechada. Métodos disponíveis: {', '.join(e['metodos'])}."
    except Exception as ex:
        return f"A verificação falhou: {ex}"
