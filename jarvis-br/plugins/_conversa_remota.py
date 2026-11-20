"""
Conversa com o dono por mensagem (fork PT-BR 2.0). Começa com "_": não é ferramenta.

O mesmo atendimento para o WhatsApp, o Telegram e o Discord: atalhos que
respondem na hora (foto, tela, status, link, confirmar…), áudio transcrito,
foto explicada, respostas às ofertas do companheiro, e o resto vai para a
sessão do JARVIS, com as mesmas ferramentas da voz — a resposta volta pelo
mesmo canal.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable

EnviarTexto = Callable[[str], object]
EnviarArquivo = Callable[[str, Path], object]


def instrucao(texto: str, fonte: str) -> str:
    nome = {"whatsapp": "WhatsApp", "telegram": "Telegram", "discord": "Discord"}.get(fonte, fonte)
    return (f"[Mensagem do dono pelo {nome}] {texto}\n"
            f"(Responda em texto curto, como numa conversa de {nome}. Se usar uma ferramenta que pede confirmação, "
            "diga que ele pode responder CONFIRMAR por aqui.)")


def atender(texto: str, enviar_texto: EnviarTexto, enviar_arquivo: EnviarArquivo, fonte: str,
            arquivo: str | None = None, tipo: str = "") -> None:
    from plugins import _whatsapp as W
    texto = str(texto or "").strip()
    if arquivo and tipo in ("ptt", "audio", "voz"):
        texto = W.transcrever_audio(arquivo)
        if not texto:
            enviar_texto("Não consegui entender o áudio (instale o faster-whisper ou configure a chave do Gemini). "
                         "Pode mandar por texto?")
            return
        enviar_texto(f"🎙 {texto}")
    if arquivo and tipo in ("image", "foto"):
        from plugins.realidade_aumentada import perguntar_imagem
        enviar_texto(perguntar_imagem(base64.b64encode(Path(arquivo).read_bytes()).decode(), texto))
        return
    if not texto:
        return
    try:                                                       # resposta a uma oferta do companheiro ("quero", "agora não")
        from plugins import companheiro
        r = companheiro.responder_oferta(texto)
        if r:
            enviar_texto(r)
            return
    except Exception:
        pass
    nome, cam = W.comando_rapido(texto)
    if nome:
        resp, foto = W.executar_rapido(nome, cam)
        if foto is not None:
            enviar_arquivo(resp, foto)
        else:
            enviar_texto(resp)
        return
    from core import resposta_remota
    silencio = not W.config().get("falar_em_casa", False)
    if not resposta_remota.pedir(instrucao(texto, fonte), lambda t: enviar_texto(t), fonte=fonte, silencio=silencio):
        from plugins import _ia
        r = _ia.perguntar(f"Você é o J.A.R.V.I.S, assistente do usuário. Responda curto, em português, como numa conversa "
                          "de mensagens. O PC está sem a sessão de voz agora, então você não consegue usar ferramentas; "
                          f"diga isso se ele pedir uma ação. Mensagem: {texto}") if _ia.disponivel() else None
        enviar_texto(r or "O JARVIS está sem conexão agora. Comandos que funcionam mesmo assim: foto, tela, status, link.")
