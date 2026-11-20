"""
Modo convidado (fork PT-BR 1.6).

Visita quer conversar com o JARVIS? Ligue o modo convidado: ele continua
simpático e ajuda com o que é LIVRE (conversa, música, clima, pesquisa,
piadas, quiz), mas:
    • sai da conversa com as suas memórias (recomeça a sessão sem elas);
    • não usa nada pessoal: arquivos, mensagens, loja, gastos, agenda, câmera…
    • não grava nada na memória.
Para sair, é preciso provar que é você (rosto, voz ou desbloquear o Windows).

    "Jarvis, modo convidado"            "Jarvis, sai do modo convidado"
"""

from __future__ import annotations

from plugins._comum import MEMORIA, gravar_json, ler_json

PLUGIN = {
    "name": "modo_convidado",
    "brief": "Guest mode: visitors can chat, but no personal data, memories or sensitive tools.",
    "description": (
        "Guest mode for visitors: action='ligar' (restart the session without the owner's memories; only free tools "
        "work), 'desligar' (needs the owner's verification), 'status'."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status"}},
                   "required": []},
}

_ARQ = MEMORIA / "modo_convidado.json"
INSTRUCAO = ("[MODO CONVIDADO] Quem está falando agora é uma VISITA, não o dono. Seja simpático e ajude com conversa, "
             "música, clima, pesquisa, piadas e jogos. NÃO revele nada pessoal do dono (nome completo, rotina, casa, "
             "trabalho, loja, finanças, saúde, conversas antigas, memórias), não abra arquivos nem mensagens. Se pedirem "
             "algo pessoal, diga com gentileza que no modo convidado isso não está disponível.")
_estado = {"ativo": None}


def ativo() -> bool:
    if _estado["ativo"] is None:
        _estado["ativo"] = bool((ler_json(_ARQ, {}) or {}).get("ativo"))
    return bool(_estado["ativo"])


def definir(ligar: bool) -> None:
    _estado["ativo"] = bool(ligar)
    gravar_json(_ARQ, {"ativo": bool(ligar)})


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    try:
        from core import registro_ferramentas
        if acao == "ligar":
            if ativo():
                return "O modo convidado já está ligado."
            definir(True)
            aviso = ""
            try:
                from core import verificacao
                if not verificacao.metodos():
                    aviso = (" Atenção: sem rosto ou voz cadastrados, qualquer pessoa consegue desligar o modo "
                             "convidado pela voz.")
            except Exception:
                pass
            registro_ferramentas.reconectar("modo convidado", manter_conversa=False)
            return "Modo convidado ligado: vou recomeçar a conversa sem as suas memórias." + aviso
        if acao == "desligar":
            if not ativo():
                return "O modo convidado não estava ligado."
            definir(False)
            registro_ferramentas.reconectar("fim do modo convidado", manter_conversa=False)
            return "Modo convidado desligado: voltando com as suas memórias."
        return "Modo convidado ligado." if ativo() else "Modo convidado desligado."
    except Exception as e:
        return f"O modo convidado falhou: {e}"
