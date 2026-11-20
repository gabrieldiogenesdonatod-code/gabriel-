"""
Realidade aumentada no celular (fork PT-BR 1.6).

No painel do celular, o botão 🥽 abre a câmera com uma sobreposição
holográfica: o próprio celular reconhece pessoas, objetos, carros, bichos…
(TensorFlow.js) e desenha as marcações. O botão "Perguntar ao JARVIS" manda a
foto daquele momento para o PC e a IA explica o que é.

    "Jarvis, abre a realidade aumentada"   → diz o endereço para abrir no celular

A câmera do navegador só funciona no endereço HTTPS do painel do celular.
"""

from __future__ import annotations

import base64

PLUGIN = {
    "name": "realidade_aumentada",
    "brief": "Augmented reality on the phone: camera with holographic object labels; ask JARVIS about what it sees.",
    "description": (
        "Augmented reality: tells the user how to open the AR page on the phone (camera with holographic object "
        "detection; a button sends the frame to JARVIS for an explanation). Use when the user asks for AR / "
        "'realidade aumentada' / 'modo holográfico'."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}}, "required": []},
}


def perguntar_imagem(b64: str, pergunta: str = "") -> str:
    from plugins import _ia
    if not b64:
        return "Não recebi a imagem."
    if not _ia.disponivel():
        return "Para explicar a imagem eu preciso da chave do Gemini no PC."
    try:
        dados = base64.b64decode(b64)
        from google.genai import types as gtypes

        from core import gemini
        resp = gemini.call([gtypes.Part.from_bytes(data=dados, mime_type="image/jpeg"),
                            (pergunta or "Você é o J.A.R.V.I.S olhando pela câmera do celular do usuário. Diga o que é "
                             "o objeto principal e um detalhe útil sobre ele, em no máximo 2 frases curtas.")
                            + " Responda em português do Brasil."], tier=gemini.FAST, timeout_ms=25_000)
        return (getattr(resp, "text", "") or "").strip() or "Não consegui identificar."
    except Exception as e:
        return f"Falhou: {e}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        from core import registro_ferramentas
        app = registro_ferramentas.app()
        url = ""
        painel = getattr(app, "_dashboard", None) if app else None
        if painel is not None:
            url = getattr(painel, "get_url", lambda: "")() or ""
        if url.startswith("http://"):
            return ("A câmera do celular só funciona com o painel em HTTPS. Ponha \"dashboard_https\": true no "
                    "config/api_keys.json, reinicie o JARVIS, abra o painel pelo QR code (aceite o aviso do certificado "
                    "uma vez) e toque em 🥽.")
        onde = f"Abra {url}/ar no celular" if url else "Abra o painel do celular (QR code do JARVIS), entre e toque em 🥽"
        return onde + ", permita a câmera e toque em 'Perguntar ao JARVIS' para eu explicar o que você está vendo."
    except Exception as e:
        return f"A realidade aumentada falhou: {e}"
