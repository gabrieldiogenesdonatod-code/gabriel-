"""
Holograma na mão (fork PT-BR 2.5).

    "Jarvis, mostra o clima na minha mão"
    "Jarvis, mostra na minha mão o que está tocando"
    "Jarvis, mostra a foto da coleção nova na mão"      (uma imagem do PC)
    "Jarvis, mostra na mão: reunião às 15h com o fornecedor"

Abre uma janela com a webcam e, quando você mostra a palma da mão aberta, o
que você pediu aparece como um cartão holográfico em cima dela, preso na mão
(acompanha quando você mexe). Fechar a mão esconde; fazer "pinça" (polegar +
indicador) troca de cartão. A detecção da mão roda no navegador (MediaPipe):
a imagem da câmera não sai do PC. Na primeira vez a página baixa o detector
(precisa de internet).
"""

from __future__ import annotations

import base64
import threading
import time
from pathlib import Path

from plugins._comum import mostrar

PLUGIN = {
    "name": "holograma_mao",
    "brief": "AR hologram in the user's hand (webcam window): shows what was asked (weather, music, image, text).",
    "description": (
        "Hologram in the hand (webcam AR window). action='mostrar' with tipo (texto | clima | musica | vendas | "
        "relogio | imagem), titulo, texto and imagem (path of a picture on the PC or https URL): adds a card that "
        "appears over the user's open palm. Put the answer the user asked for in titulo/texto. 'limpar' removes "
        "the cards; 'abrir' / 'fechar' the window."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "mostrar | limpar | abrir | fechar"},
            "tipo": {"type": "STRING"}, "titulo": {"type": "STRING"}, "texto": {"type": "STRING"},
            "imagem": {"type": "STRING"},
        },
        "required": [],
    },
}

MAX_CARTOES = 6
_lock = threading.Lock()
_estado = {"cartoes": [], "versao": 0, "novo": False, "aberta_em": 0.0}


def _imagem_data_url(caminho: str, lado: int = 900) -> str:
    """Arquivo do PC → data URL (JPEG reduzido); URL https passa direto."""
    c = str(caminho or "").strip()
    if not c:
        return ""
    if c.startswith(("http://", "https://", "data:image/")):
        return c
    p = Path(c).expanduser()
    if not p.is_file() or p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"):
        return ""
    try:
        import io

        from PIL import Image
        im = Image.open(p).convert("RGB")
        im.thumbnail((lado, lado))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"[Holograma] imagem: {e}")
        return ""


def montar_cartao(tipo: str, titulo: str = "", texto: str = "", imagem: str = "") -> dict:
    """O cartão já com o conteúdo resolvido (clima, música, vendas…)."""
    tipo = (tipo or "texto").lower().strip()
    if tipo == "clima" and not texto:
        try:
            from plugins import briefing_br
            texto = briefing_br.clima()
        except Exception as e:
            texto = f"Não consegui o clima agora ({e})."
        titulo = titulo or "Clima"
    elif tipo == "musica":
        try:
            from plugins import musica
            e = musica.estado_player()
        except Exception:
            e = {}
        if e.get("titulo"):
            titulo = titulo or "Tocando agora"
            texto = texto or f"{e.get('titulo')} — {e.get('artistas', '')}".strip(" —")
            imagem = imagem or e.get("capa", "")
        else:
            titulo, texto = titulo or "Música", texto or "Nada tocando agora."
    elif tipo == "vendas":
        try:
            from plugins.painel_led import _vendas_hoje
            texto = texto or _vendas_hoje() or "Nenhuma venda registrada hoje."
        except Exception:
            texto = texto or "Sem dados de vendas."
        titulo = titulo or "Cristal Malhas"
    elif tipo == "relogio":
        titulo = titulo or "Agora"
    return {"tipo": tipo if tipo in ("texto", "clima", "musica", "vendas", "relogio", "imagem") else "texto",
            "titulo": str(titulo or "")[:60], "texto": str(texto or "")[:400], "imagem": _imagem_data_url(imagem)}


def adicionar(cartao: dict) -> int:
    with _lock:
        _estado["cartoes"] = (_estado["cartoes"] + [cartao])[-MAX_CARTOES:]
        _estado["versao"] += 1
        _estado["novo"] = True
        return len(_estado["cartoes"])


def estado_tela(_q: dict | None = None) -> dict:
    with _lock:
        novo, _estado["novo"] = _estado["novo"], False
        return {"versao": _estado["versao"], "cartoes": list(_estado["cartoes"]), "novo": novo}


def _registrar_rotas() -> None:
    from plugins import _arcade
    _arcade.ROTAS_GET["/api/mao"] = estado_tela


def abrir() -> bool:
    from plugins import _arcade
    _registrar_rotas()
    try:
        from plugins._camera_remota import liberar
        liberar(0)                                            # a webcam fica livre para a janela
        time.sleep(0.4)
    except Exception:
        pass
    _estado["aberta_em"] = time.time()
    return _arcade.abrir_pagina("/mao", 1100, 720)


def on_session_start(player) -> None:
    try:
        _registrar_rotas()
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "mostrar").lower()
    try:
        if acao == "limpar":
            with _lock:
                _estado["cartoes"], _estado["versao"] = [], _estado["versao"] + 1
            return "Limpei o holograma."
        if acao == "fechar":
            return "É só fechar a janela do holograma (ou fechar a mão para esconder o cartão)."
        if acao == "abrir":
            return "Abri o holograma: mostre a palma da mão para a câmera." if abrir() else "Não consegui abrir a janela."
        c = montar_cartao(str(p.get("tipo") or ("imagem" if p.get("imagem") else "texto")), str(p.get("titulo") or ""),
                          str(p.get("texto") or ""), str(p.get("imagem") or ""))
        if c["tipo"] == "imagem" and not c["imagem"]:
            return "Não achei essa imagem (passe o caminho de um arquivo .jpg/.png ou um link https)."
        n = adicionar(c)
        if time.time() - _estado["aberta_em"] > 20 * 60 or n == 1:
            abrir()
            extra = " Abri a janela: mostre a palma da mão aberta para a câmera."
        else:
            extra = " Está na sua mão (se a janela estiver aberta)."
        mostrar(player, f"HOLOGRAMA · {c['titulo'] or c['tipo']}".upper(), c["texto"] or "(imagem)")
        return f"Pronto: {c['titulo'] or c['tipo']}.{extra}" + (" Faça pinça para trocar de cartão." if n > 1 else "")
    except Exception as e:
        return f"O holograma falhou: {e}"
