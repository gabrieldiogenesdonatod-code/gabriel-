"""
Resumo de vídeo do YouTube (fork PT-BR 1.9).

    "Jarvis, resume esse vídeo"                     (o vídeo aberto no navegador)
    "Jarvis, resume esse vídeo em tópicos"
    "Jarvis, resume https://youtu.be/…"             (ou com o link copiado)
    "Jarvis, o que esse vídeo fala sobre preço?"

Como ele acha o vídeo: o link que você disse ou copiou; senão, o último vídeo
do YouTube no histórico do Chrome/Edge/Brave (o que tem o mesmo título da aba
aberta, se der; ele só lê os endereços do YouTube, numa cópia, e nada sai do
PC além do link do vídeo). Como ele "assiste": pela legenda do vídeo
(youtube-transcript-api, opcional) ou, sem ela, mandando o link para o Gemini.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

from plugins._comum import MAC, WIN, mostrar

PLUGIN = {
    "name": "resumo_video",
    "brief": "Summarizes the YouTube video that is open (or a link) from its captions, in ~30 seconds of speech.",
    "description": (
        "YouTube video summary. Finds the video from url (if given), the clipboard, or the latest YouTube video in "
        "the browser history matching the open tab; reads its captions (or sends the link to Gemini) and summarizes. "
        "Parameters: url (optional), formato ('curto' ~30 s of speech, 'topicos' bullet points), pergunta (optional "
        "question about the video)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"url": {"type": "STRING"}, "formato": {"type": "STRING", "description": "curto | topicos"},
                       "pergunta": {"type": "STRING"}},
        "required": [],
    },
}

_RE_ID = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def id_do_video(texto: str) -> str:
    m = _RE_ID.search(texto or "")
    return m.group(1) if m else ""


def rv_id(url: str) -> str:
    return id_do_video(url)


def titulo_da_aba(titulo: str) -> str:
    """'(3) Como fazer X - YouTube — Google Chrome' → 'Como fazer X' (pura)."""
    t = re.sub(r"^\(\d+\)\s*", "", titulo or "")
    m = re.match(r"(.+?) - YouTube", t)
    return m.group(1).strip() if m else ""


def historicos() -> list[Path]:
    casa = Path.home()
    if WIN:
        base = Path(os.environ.get("LOCALAPPDATA", ""))
        raizes = [base / "Google/Chrome/User Data", base / "Microsoft/Edge/User Data",
                  base / "BraveSoftware/Brave-Browser/User Data", base / "Opera Software"]
    elif MAC:
        raizes = [casa / "Library/Application Support/Google/Chrome", casa / "Library/Application Support/Microsoft Edge"]
    else:
        raizes = [casa / ".config/google-chrome", casa / ".config/chromium", casa / ".config/microsoft-edge",
                  casa / ".config/BraveSoftware/Brave-Browser"]
    achados = []
    for r in raizes:
        if r.exists():
            achados += [p for p in r.glob("*/History") if p.is_file()] + [p for p in r.glob("History") if p.is_file()]
    return achados


def videos_recentes(limite: int = 20) -> list[tuple[int, str, str]]:
    """[(quando, url, título)] dos vídeos do YouTube mais recentes, de todos os navegadores (cópia do histórico)."""
    saida = []
    for h in historicos():
        try:
            with tempfile.TemporaryDirectory() as tmp:
                copia = Path(tmp) / "h.sqlite"
                shutil.copy2(h, copia)                          # o navegador trava o original
                con = sqlite3.connect(str(copia))
                try:
                    for quando, url, titulo in con.execute(
                            "SELECT last_visit_time, url, title FROM urls WHERE url LIKE '%youtube.com/watch%' OR url LIKE "
                            "'%youtu.be/%' OR url LIKE '%youtube.com/shorts/%' ORDER BY last_visit_time DESC LIMIT ?",
                            (limite,)):
                        saida.append((int(quando or 0), url, titulo or ""))
                finally:
                    con.close()
        except Exception:
            continue
    return sorted(saida, reverse=True)


def escolher(videos: list[tuple[int, str, str]], titulo_aba: str) -> str:
    """O vídeo da aba aberta, se o título bater; senão, o mais recente (pura)."""
    if titulo_aba:
        alvo = titulo_aba.lower()
        for _q, url, titulo in videos:
            if titulo and (titulo.lower().startswith(alvo) or alvo in titulo.lower()):
                return url
    return videos[0][1] if videos else ""


def achar_url(dado: str = "") -> tuple[str, str]:
    """(url, de onde veio)."""
    if id_do_video(dado):
        return dado, "o link"
    try:
        import pyperclip
        copiado = pyperclip.paste() or ""
        if id_do_video(copiado):
            return copiado.strip(), "o link copiado"
    except Exception:
        pass
    titulo = ""
    try:
        from plugins._janelas import ativa, listar
        j = ativa()
        titulo = titulo_da_aba((j or {}).get("titulo", ""))
        if not titulo:
            titulo = next((titulo_da_aba(x["titulo"]) for x in listar() if titulo_da_aba(x.get("titulo", ""))), "")
    except Exception:
        pass
    url = escolher(videos_recentes(), titulo)
    return url, ("a aba aberta" if titulo else "o histórico do navegador")


def legenda(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return ""
    langs = ["pt", "pt-BR", "en", "es"]
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):                 # versões antigas
            itens = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            return " ".join(i["text"] for i in itens)
        itens = YouTubeTranscriptApi().fetch(video_id, languages=langs)     # 1.x
        return " ".join(getattr(i, "text", "") for i in itens)
    except Exception as e:
        print(f"[ResumoVideo] sem legenda: {e}")
        return ""


def pedido(formato: str, pergunta: str) -> str:
    if pergunta:
        return (f"Responda em português, em até 4 frases, à pergunta sobre o vídeo: {pergunta}. Se o vídeo não falar disso, "
                "diga que não fala.")
    if formato.startswith("top"):
        return "Resuma o vídeo em português em 5 a 8 tópicos curtos, do mais importante ao menos, e uma frase de conclusão."
    return ("Resuma o vídeo em português para ser FALADO em cerca de 30 segundos (até 80 palavras): do que trata, as "
            "ideias principais e a conclusão. Sem listas.")


def resumir(url: str, formato: str = "curto", pergunta: str = "") -> tuple[str, str]:
    from plugins import _ia
    if not _ia.disponivel():
        return "", "Para resumir eu preciso da chave do Gemini."
    vid = id_do_video(url)
    texto = legenda(vid) if vid else ""
    if texto:
        return (_ia.perguntar(f"{pedido(formato, pergunta)}\n\nLEGENDA DO VÍDEO:\n{texto[:60000]}", True, 90) or "", "legenda")
    try:
        from google.genai import types as gtypes

        from core import gemini
        resp = gemini.call([gtypes.Part(file_data=gtypes.FileData(file_uri=f"https://www.youtube.com/watch?v={vid}")),
                            pedido(formato, pergunta)], tier=gemini.SMART, timeout_ms=180_000)
        return ((getattr(resp, "text", "") or "").strip() if resp is not None else ""), "vídeo"
    except Exception as e:
        return "", f"Não consegui assistir o vídeo: {e}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    try:
        url, origem = achar_url(str(p.get("url") or ""))
        if not url:
            return "Não achei o vídeo. Abra o vídeo no navegador ou copie o link e peça de novo."
        resumo, info = resumir(url, str(p.get("formato") or "curto").lower(), str(p.get("pergunta") or ""))
        if not resumo:
            return info or "Não consegui resumir esse vídeo."
        mostrar(player, "RESUMO DO VÍDEO", f"{resumo}\n\n{url}")
        try:                                                   # 2.0: entra no perfil de gosto
            from plugins import _gosto
            titulo = next((t for _q, u, t in videos_recentes(10) if rv_id(u) == rv_id(url) and t), "")
            _gosto.registrar("video", re.sub(r"\s*-\s*YouTube.*$", "", titulo) or url, "viu")
        except Exception:
            pass
        return f"(Vídeo achado por {origem}; li {'a legenda' if info == 'legenda' else 'o vídeo pelo Gemini'}.) {resumo}"
    except Exception as e:
        return f"O resumo falhou: {e}"

