"""
Modo Acompanhar — "olha minha tela" (fork PT-BR 2.11).

O JARVIS olha o que está na SUA tela (ou você pela câmera) QUANDO VOCÊ PEDE, e te
ajuda com o que está vendo. É sempre sob demanda: ele tira uma foto da tela na
hora, entende e responde. Não fica gravando nada sozinho.

    "Jarvis, o que você tá vendo na minha tela?"
    "Jarvis, me ajuda com esse erro que tá na tela."
    "Jarvis, olha a câmera, tô apresentável?"

Precisa da visão (Gemini) ligada. A captura é feita na hora e não é salva. O modo
de ficar observando sozinho o tempo todo NÃO está ligado aqui — isso é um ajuste
à parte, pra você ligar quando quiser (e aí aparece um aviso na tela).
"""

from __future__ import annotations

import unicodedata

PLUGIN = {
    "name": "acompanhar",
    "brief": "Look at my screen (or camera) on demand and help with what's there. Captures once, saves nothing.",
    "description": (
        "Looks at the user's screen (or webcam) ON DEMAND and helps with what's shown — a single capture each time, "
        "nothing saved, no continuous watching. Needs Gemini vision. action='tela' (look at the screen) or "
        "'camera' (look through the webcam); pergunta = what the user wants to know/do about it. Use for 'o que "
        "você tá vendo na tela', 'me ajuda com esse erro na tela', 'lê isso pra mim', 'olha a câmera'. Always a "
        "one-off look triggered by the user."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "tela | camera"},
            "pergunta": {"type": "STRING", "description": "what to know/do about what's shown (optional)"},
        },
    },
}


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def _capturar(fonte: str):
    """(bytes, de_onde) da tela ou da câmera, usando o que o projeto já tem. (None, '') se falhar."""
    try:
        from actions import screen_processor as sp
        if fonte == "camera":
            dados, _fmt = sp._capture_camera()
            return dados, "câmera"
        dados, _fmt = sp._capture_screen()
        return dados, "tela"
    except Exception as e:
        print(f"[Acompanhar] captura: {e}")
        return None, ""


def _prompt(pergunta: str, de_onde: str) -> str:
    base = ("Esta é a tela do computador do usuário agora." if de_onde == "tela"
            else "Esta é a imagem da webcam do usuário agora.")
    if pergunta.strip():
        return (f"{base} O usuário pergunta: \"{pergunta.strip()}\". Responda em português do Brasil, direto e "
                "curto, com base só no que dá pra ver. Se for um erro de código ou do sistema, diga o que é e o "
                "próximo passo.")
    return (f"{base} Descreva em 2 ou 3 frases o que o usuário está fazendo e, se houver algo que peça ação (um "
            "erro, um aviso, um campo a preencher), aponte. Português do Brasil.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "tela").strip()
    fonte = "camera" if acao in ("camera", "webcam", "cam") else "tela"
    pergunta = str(p.get("pergunta") or p.get("texto") or "")
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return ("Pra olhar a sua tela eu preciso da visão (Gemini) ligada — coloque a chave em ⚙ MOTOR & "
                    "PROVEDORES.")
        dados, de_onde = _capturar(fonte)
        if not dados:
            return ("Não consegui capturar a " + ("câmera" if fonte == "camera" else "tela") +
                    " agora. Veja se a câmera está livre, ou tente de novo.")
        resposta = _ia.ver_imagem(_prompt(pergunta, de_onde), dados, inteligente=False, segundos=40)
        if not resposta:
            return "Olhei, mas não consegui entender a imagem agora. Tenta de novo?"
        return resposta
    except Exception as e:
        return f"O Modo Acompanhar falhou: {e}"
