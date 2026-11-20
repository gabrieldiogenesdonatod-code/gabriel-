"""
Conversar com o J.A.R.V.I.S pelo WhatsApp (fork PT-BR 1.8).

    "Jarvis, liga o WhatsApp"          → na 1ª vez instala a ponte e mostra o QR code
    "Jarvis, autoriza meu WhatsApp"    → mostra um código; mande-o do seu WhatsApp para o número do JARVIS
    "Jarvis, me manda no whats a lista de compras"
    "Jarvis, manda uma foto da câmera no meu whats"
    "Jarvis, status do WhatsApp" / "desliga o WhatsApp" / "tira os donos do WhatsApp"

Usa o WhatsApp Web (whatsapp-web.js), não a API oficial: a Meta pode limitar ou
banir o número. O mais seguro é um chip só para o JARVIS. Se usar o seu número,
converse com ele no chat "Você" (mensagem para mim).
"""

from __future__ import annotations

import threading

from plugins import _whatsapp as W
from plugins._comum import abrir_no_sistema, mostrar

PLUGIN = {
    "name": "whatsapp_jarvis",
    "brief": "Talk to JARVIS over WhatsApp (WhatsApp Web bridge): owner chats, camera photos, alerts.",
    "description": (
        "WhatsApp link between the user and JARVIS. action='ligar' starts it (first time installs the bridge and opens "
        "a QR code to scan in WhatsApp > Linked devices); 'status'; 'desligar'; 'autorizar' shows a pairing code the "
        "user sends from his WhatsApp so that chat becomes an owner (never read the code aloud if the user is not "
        "alone; it is on screen); 'desautorizar' removes all owner chats; 'enviar' with texto sends a message to the "
        "OWNER's own WhatsApp (not to other people); 'foto' sends a camera photo (optional camera number) or "
        "'tela' a screenshot to the owner. Store/personal mode: incoming messages become reply DRAFTS; "
        "'rascunhos' lists them, 'aprovar' with id sends one, 'editar' with id + texto sends an edited version, "
        "'ignorar' with id discards — never send a draft unless the user explicitly approves it. Messages the owner sends on WhatsApp reach you as "
        "'[Mensagem do dono pelo WhatsApp]' — answer them normally and briefly."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ligar | status | desligar | autorizar | "
                                                                    "desautorizar | enviar | foto | tela | rascunhos | aprovar | editar | "
                                                                    "ignorar"},
                       "texto": {"type": "STRING"}, "camera": {"type": "STRING"}, "id": {"type": "INTEGER"}},
        "required": [],
    },
}
PLUGIN_SETTINGS = W.PLUGIN_SETTINGS

_iniciou = threading.Event()
NOMES_ESTADO = {"desligado": "desligado", "iniciando": "iniciando", "qr": "esperando ler o QR code",
                "autenticado": "entrando", "pronto": "conectado", "desconectado": "desconectado", "falha": "com falha"}


def _mostrar_qr(player) -> str:
    import time
    for _ in range(90):                                        # o 1º QR leva uns segundos (abre o navegador escondido)
        e = W.estado()
        if e.get("estado") == "pronto":
            return f"WhatsApp conectado no número {e.get('numero', '')}."
        arq = W.qr_png()
        if e.get("estado") == "qr" and arq:
            abrir_no_sistema(str(arq))
            mostrar(player, "WHATSAPP DO JARVIS", "No celular: WhatsApp → ⋮ → Aparelhos conectados → Conectar um "
                    "aparelho, e leia o QR code que abriu na tela.\n\nDepois mande 'ajuda' para o JARVIS (ou, se for o "
                    "seu número, no chat 'Você').")
            return "Abri o QR code: leia no WhatsApp em Aparelhos conectados, Conectar um aparelho."
        if e.get("estado") in ("falha", "desligado"):
            return f"O WhatsApp não iniciou: {e.get('erro') or 'veja memory/whatsapp_sessao/ponte.log'}."
        time.sleep(1)
    return "A ponte ligou, mas o QR code está demorando. Peça 'status do WhatsApp' daqui a pouco."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "ligar":
            # 2.2: não trava a conversa (a 1ª vez instala por minutos); a janela mostra o andamento e o QR ao vivo.
            if W.pronto():
                return f"O WhatsApp já está conectado (número {W.estado().get('numero', '')})."
            if not W.node_exe():
                erro = W.instalar()                              # tenta o Node pelo winget e explica o que fazer
                return erro
            W.iniciar_em_segundo_plano()
            from plugins import _arcade
            aberta = _arcade.abrir_pagina("/whatsapp", 560, 760)
            primeira = not W.dependencias_ok()
            return ("Abri a janela do WhatsApp." if aberta else "Abra a janela do WhatsApp no navegador.") + \
                (" Como é a primeira vez, eu instalo a ponte antes (alguns minutos); o QR code aparece lá sozinho."
                 if primeira else " O QR code aparece lá em instantes: leia em Aparelhos conectados.")
        if acao == "desligar":
            return "WhatsApp desligado." if W.parar() else "O WhatsApp já estava desligado."
        if acao == "autorizar":
            cod = W.novo_codigo()
            numero = W.estado().get("numero", "")
            mostrar(player, "AUTORIZAR WHATSAPP", f"Do SEU WhatsApp, mande esta mensagem para o número do JARVIS"
                    f"{(' (' + numero + ')') if numero else ''}:\n\n    {cod}\n\nVale até ser usado.")
            return "O código de autorização está na tela: mande-o do seu WhatsApp para o número do JARVIS."
        if acao == "desautorizar":
            return f"Tirei {W.remover_donos()} conversa(s) da lista de donos."
        if acao in ("rascunhos", "aprovar", "editar", "ignorar"):
            comando = "rascunhos" if acao == "rascunhos" else f"{acao} {p.get('id') or 0} {p.get('texto') or ''}".strip()
            r = W.comando_loja(comando)
            if acao == "rascunhos" and r != "Nenhum rascunho esperando.":
                mostrar(player, "RASCUNHOS DO WHATSAPP", r)
                return "Os rascunhos estão na tela."
            return r or "Diga o número do rascunho."
        if acao in ("enviar", "foto", "tela"):
            if not W.pronto():
                return "O WhatsApp não está conectado. Diga 'liga o WhatsApp'."
            if acao == "enviar":
                texto = str(p.get("texto") or "").strip()
                if not texto:
                    return "O que eu mando?"
                n = W.para_donos(texto)
            else:
                cam = W.so_digitos(str(p.get("camera") or ""))
                legenda, arq = W.executar_rapido(acao, int(cam) - 1 if cam else 0)
                if arq is None:
                    return legenda
                n = W.para_donos(legenda, arq)
            return "Mandei no seu WhatsApp." if n else \
                "Não sei para onde mandar ainda: fale com o JARVIS uma vez pelo WhatsApp (ou use 'autoriza meu WhatsApp')."
        e = W.estado()
        txt = f"WhatsApp {NOMES_ESTADO.get(e.get('estado', ''), e.get('estado', ''))}"
        if e.get("numero"):
            txt += f" (número {e['numero']})"
        txt += f". Donos autorizados: {len(W.dados()['ids'])}."
        return txt
    except Exception as e:
        return f"O WhatsApp falhou: {e}"


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    if W.config().get("ligar_ao_abrir") and W.dependencias_ok():
        erro = W.iniciar()
        print(f"[WhatsApp] {erro or 'ponte ligada'}")
