"""
JARVIS no Telegram e no Discord (fork PT-BR 2.0). O WhatsApp é a ferramenta whatsapp_jarvis.

    "Jarvis, liga o Telegram"          "Jarvis, autoriza meu Telegram"  (código para mandar ao bot)
    "Jarvis, liga o Discord"           (mostra o link para pôr o bot num servidor seu)
    "Jarvis, me manda no Telegram a lista de compras"
    "Jarvis, me liga e diz que o download terminou"
    "Jarvis, status dos mensageiros"

Por mensagem, você conversa com o JARVIS como na voz, manda áudio e foto, e
usa os mesmos atalhos do WhatsApp (foto, tela, status, link, confirmar…).
"""

from __future__ import annotations

import threading

from plugins import _canais, _discord, _telegram
from plugins._comum import mostrar

PLUGIN = {
    "name": "mensageiros",
    "brief": "JARVIS on Telegram and Discord (bots), plus sending a message to the owner on any channel or calling his "
             "phone.",
    "description": (
        "Telegram/Discord bots for talking with JARVIS. action='ligar'/'desligar'/'status' with canal (telegram | "
        "discord); 'autorizar' with canal=telegram shows a pairing code on screen; 'enviar' with texto (+ optional canal "
        "whatsapp|telegram|discord) sends a message to the OWNER only; 'ligar_celular' with texto calls the owner's phone "
        "(Twilio) and speaks the text. Messages the owner sends there reach you as '[Mensagem do dono pelo Telegram]'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status | autorizar | enviar | "
                                                                    "ligar_celular"},
                       "canal": {"type": "STRING"}, "texto": {"type": "STRING"}},
        "required": [],
    },
}
PLUGIN_SETTINGS = _telegram.PLUGIN_SETTINGS                # Telegram e Discord, numa seção só
_iniciou = threading.Event()


def _canal(p) -> str:
    c = str(p.get("canal") or "").lower()
    return "discord" if "disc" in c else "telegram" if "tele" in c else "whatsapp" if "whats" in c or "zap" in c else c


def ligar(canal: str, player=None) -> str:
    if canal == "telegram":
        erro = _telegram.iniciar()
        if erro:
            return (f"Telegram: {erro}. Crie o bot no @BotFather e cole o token em ⚙ CONFIG. DE PLUGINS → Telegram do "
                    "JARVIS." if "token" in erro else f"Telegram: {erro}.")
        if not _telegram.dados()["chats"]:
            cod = _telegram.novo_codigo()
            mostrar(player, "AUTORIZAR TELEGRAM", f"No Telegram, abra @{_telegram._estado['bot']} e mande:\n\n    {cod}")
            return f"Telegram ligado. Para autorizar, mande o código que está na tela para o bot @{_telegram._estado['bot']}."
        return f"Telegram ligado (@{_telegram._estado['bot']})."
    if canal == "discord":
        erro, convite = _discord.iniciar()
        if convite:
            mostrar(player, "DISCORD DO JARVIS", f"Para o bot poder te mandar DM, ponha ele num servidor seu:\n\n{convite}")
        if erro:
            return f"Discord: {erro}."
        return "Discord ligado: o JARVIS conversa com você por DM."
    return "Qual: Telegram ou Discord? (O WhatsApp é 'liga o WhatsApp'.)"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    canal = _canal(p)
    try:
        if acao == "ligar":
            return ligar(canal, player)
        if acao == "desligar":
            (_discord if canal == "discord" else _telegram).parar()
            return f"{'Discord' if canal == 'discord' else 'Telegram'} desligado."
        if acao == "autorizar":
            if canal == "discord":
                return "No Discord, basta pôr o seu ID em ⚙ → Discord do JARVIS (só ele é atendido)."
            cod = _telegram.novo_codigo()
            mostrar(player, "AUTORIZAR TELEGRAM", f"Mande para o bot{(' @' + _telegram._estado['bot']) if _telegram._estado['bot'] else ''}:\n\n    {cod}")
            return "O código está na tela: mande para o bot no Telegram."
        if acao == "enviar":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return "O que eu mando?"
            usados = _canais.mandar(texto, canal=canal)
            return (f"Mandei pelo {_canais.NOMES[usados[0]]}." if usados else
                    "Nenhum canal ligado e autorizado (WhatsApp, Telegram ou Discord).")
        if acao == "ligar_celular":
            return _canais.ligar(str(p.get("texto") or "Oi, aqui é o Jarvis."))
        partes = [f"Telegram: {'ligado' if _telegram.rodando() else 'desligado'}"
                  + (f" ({len(_telegram.dados()['chats'])} chat autorizado)" if _telegram.dados()["chats"] else "")
                  + (f", problema: {_telegram._estado['erro']}" if _telegram._estado["erro"] else ""),
                  f"Discord: {'ligado' if _discord.rodando() else 'desligado'}"
                  + (f", problema: {_discord._estado['erro']}" if _discord._estado["erro"] else ""),
                  "canais prontos: " + (", ".join(_canais.NOMES[c] for c in _canais.ativos()) or "nenhum")]
        return "; ".join(partes) + "."
    except Exception as e:
        return f"Os mensageiros falharam: {e}"


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    if str(_discord.config().get("ligar_ao_abrir", True)).lower() == "false":
        return
    if _telegram.token():
        print(f"[Telegram] {_telegram.iniciar() or 'ligado'}")
    if str(_discord.config().get("token") or ""):
        print(f"[Discord] {_discord.iniciar()[0] or 'ligado'}")
