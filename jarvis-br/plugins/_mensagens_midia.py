"""
Entender as mídias das mensagens (fork PT-BR 2.16). Começa com "_": não vira ferramenta.

    entender(arquivo, tipo)  → {"texto": transcrição/descrição, "resumo": 1 linha}
    guardar(ev, info)        → anota em memory/mensagens_midia.json (últimas 80)
    recentes(chat=None)      → o que foi anotado

Áudio: transcreve (faster-whisper local, senão a IA) e, se passar de ~25
palavras, faz um resumo de UMA linha ("Ana pergunta se você pega as crianças às 17h").
Foto: a IA descreve em uma frase e copia qualquer texto escrito nela.
Documento PDF: o começo do texto.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from plugins._comum import MEMORIA, gravar_json, ler_json

ARQ = MEMORIA / "mensagens_midia.json"
_lock = threading.Lock()


def precisa_resumo(texto: str, palavras: int = 25) -> bool:
    return len(re.findall(r"\w+", texto or "")) > palavras


def resumo_local(texto: str, limite: int = 140) -> str:
    """Sem IA: a primeira frase, cortada (pura)."""
    t = " ".join((texto or "").split())
    frase = re.split(r"(?<=[.!?])\s", t)[0]
    return frase if len(frase) <= limite else frase[:limite].rsplit(" ", 1)[0] + "…"


def _resumir(texto: str, quem: str = "") -> str:
    from plugins import _ia
    if _ia.disponivel():
        r = _ia.perguntar(f"Resuma em UMA linha curta (até 20 palavras), em português, o que {quem or 'a pessoa'} disse "
                          f"neste áudio, focando no pedido ou na informação principal:\n{texto[:4000]}", False, 20)
        if r:
            return r.strip().strip('"')
    return resumo_local(texto)


def _ver_foto(arq: Path) -> str:
    from plugins import _ia
    if not _ia.disponivel():
        return ""
    try:
        from google.genai import types as gtypes

        from core import gemini
        mime = "image/png" if arq.suffix.lower() == ".png" else "image/webp" if arq.suffix.lower() == ".webp" else "image/jpeg"
        resp = gemini.call([gtypes.Part.from_bytes(data=arq.read_bytes(), mime_type=mime),
                            "Descreva esta foto em UMA frase curta em português. Se houver texto escrito nela (print, "
                            "comprovante, documento), copie o essencial depois de 'Texto:'."], tier=gemini.FAST,
                           timeout_ms=30_000)
        return ((getattr(resp, "text", "") or "") if resp is not None else "").strip()
    except Exception as e:
        print(f"[Mídia] foto: {e}")
        return ""


def entender(arquivo: str | Path, tipo: str, quem: str = "") -> dict:
    arq = Path(arquivo)
    tipo = str(tipo or "")
    if tipo in ("ptt", "audio") or arq.suffix.lower() in (".ogg", ".opus", ".mp3", ".m4a", ".wav"):
        from plugins import _whatsapp as W
        texto = W.transcrever_audio(str(arq))
        if not texto:
            return {"tipo": "áudio", "texto": "", "resumo": "áudio que não consegui transcrever"}
        return {"tipo": "áudio", "texto": texto,
                "resumo": _resumir(texto, quem) if precisa_resumo(texto) else texto}
    if tipo in ("image", "sticker") or arq.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
        d = _ver_foto(arq)
        return {"tipo": "foto", "texto": d, "resumo": d.split("Texto:")[0].strip() or "uma foto"}
    if arq.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(str(arq)) as pdf:
                t = "\n".join((pg.extract_text() or "") for pg in pdf.pages[:3])
            return {"tipo": "documento", "texto": t[:6000], "resumo": resumo_local(t, 160) or "um PDF"}
        except Exception:
            pass
    return {"tipo": "arquivo", "texto": "", "resumo": f"um arquivo ({arq.suffix or 'sem extensão'})"}


def guardar(chat: str, nome: str, info: dict, arquivo: str = "") -> None:
    with _lock:
        lista = ler_json(ARQ, []) or []
        lista.append({"chat": chat, "nome": nome, "quando": time.strftime("%Y-%m-%d %H:%M"), "arquivo": str(arquivo),
                      **{k: info.get(k, "") for k in ("tipo", "texto", "resumo")}})
        gravar_json(ARQ, lista[-80:])


def recentes(chat: str | None = None, tipo: str | None = None) -> list[dict]:
    lista = ler_json(ARQ, []) or []
    return [x for x in lista if (chat is None or x["chat"] == chat) and (tipo is None or x["tipo"] == tipo)]
