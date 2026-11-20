"""
Pesquisa no YouTube SEM abrir o YouTube (fork PT-BR 3.9.3).

    Na caixa de texto:  youtube: receita de bolo de cenoura      (ou  yt: ...)
    No painel VÍDEOS:   🔎 Pesquisar no YouTube

Os resultados aparecem num painel por cima da interface (J.A.R.V.I.S ou SEXTA-FEIRA), com miniatura,
título, canal e duração. Clicar num deles toca o vídeo na tela do JARVIS, no mesmo player do HUD
(actions/video_player.py, QtMultimedia + yt-dlp). Nenhuma aba é aberta.

A busca usa o yt-dlp (já está no requirements). Sem ele, lê a página de resultados direto.
"""
from __future__ import annotations

import json
import re
import threading

_PREFIXO = re.compile(r"^\s*(youtube|yt|you tube)\s*:\s*", re.I)
_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def pedido_de_busca(texto: str) -> str | None:
    """'youtube: X' → 'X'. Outro texto → None. Pura."""
    m = _PREFIXO.match(texto or "")
    if not m:
        return None
    return texto[m.end():].strip()


def _duracao(seg) -> str:
    try:
        seg = int(float(seg))
    except (TypeError, ValueError):
        return ""
    h, m, s = seg // 3600, seg % 3600 // 60, seg % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _por_ytdlp(termo: str, n: int) -> list:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{termo}", download=False)
    out = []
    for e in (info or {}).get("entries") or []:
        vid = str(e.get("id") or "")
        if not _ID.match(vid):
            continue
        out.append({"id": vid, "titulo": str(e.get("title") or "(sem título)"),
                    "canal": str(e.get("channel") or e.get("uploader") or ""),
                    "duracao": _duracao(e.get("duration")), "url": f"https://www.youtube.com/watch?v={vid}"})
    return out


def ler_pagina(html: str, n: int = 8) -> list:
    """Os vídeos de uma página de resultados do YouTube (o JSON ytInitialData). Pura."""
    m = re.search(r"ytInitialData\s*=\s*(\{.*?\});\s*</script>", html or "", re.S)
    if not m:
        return []
    try:
        dados = json.loads(m.group(1))
    except ValueError:
        return []
    out, vistos = [], set()

    def andar(o):
        if len(out) >= n:
            return
        if isinstance(o, dict):
            v = o.get("videoRenderer")
            if isinstance(v, dict) and _ID.match(str(v.get("videoId") or "")) and v["videoId"] not in vistos:
                vistos.add(v["videoId"])
                titulo = "".join(r.get("text", "") for r in (v.get("title") or {}).get("runs") or [])
                canal = "".join(r.get("text", "") for r in (v.get("ownerText") or {}).get("runs") or [])
                out.append({"id": v["videoId"], "titulo": titulo or "(sem título)", "canal": canal,
                            "duracao": (v.get("lengthText") or {}).get("simpleText", ""),
                            "url": f"https://www.youtube.com/watch?v={v['videoId']}"})
            for x in o.values():
                andar(x)
        elif isinstance(o, list):
            for x in o:
                andar(x)
    andar(dados)
    return out


def _por_pagina(termo: str, n: int) -> list:
    import requests
    from urllib.parse import quote_plus
    r = requests.get(f"https://www.youtube.com/results?search_query={quote_plus(termo)}&hl=pt-BR",
                     headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR,pt;q=0.9"}, timeout=10)
    r.raise_for_status()
    return ler_pagina(r.text, n)


def buscar(termo: str, n: int = 6) -> tuple[list, str]:
    """(resultados, erro). Tenta o yt-dlp e, se faltar ou falhar, a página de resultados."""
    termo = " ".join(str(termo or "").split())[:200]
    if not termo:
        return [], "O que você quer pesquisar?"
    erro = ""
    try:
        res = _por_ytdlp(termo, n)
        if res:
            return res, ""
    except Exception as e:
        erro = str(e)
    try:
        res = _por_pagina(termo, n)
        if res:
            return res, ""
        return [], "Nada encontrado para essa pesquisa."
    except Exception as e:
        return [], f"Não consegui pesquisar agora ({erro or e})."


def miniatura(video_id: str) -> bytes:
    """A miniatura do vídeo (jpg) ou b'' — nunca levanta."""
    if not _ID.match(str(video_id or "")):
        return b""
    try:
        import requests
        r = requests.get(f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg", timeout=6)
        return r.content if r.ok and r.content[:2] == b"\xff\xd8" else b""
    except Exception:
        return b""


class Busca:
    """Uma pesquisa em andamento, lida pela pintura (thread da interface) sem travar nada."""

    def __init__(self, termo: str, n: int = 6):
        self.termo = termo
        self.resultados: list = []
        self.erro = ""
        self.pronta = False
        self.miniaturas: dict = {}       # id → bytes (a pintura converte em imagem)
        threading.Thread(target=self._rodar, args=(n,), daemon=True, name="yt-busca").start()

    def _rodar(self, n: int):
        self.resultados, self.erro = buscar(self.termo, n)
        self.pronta = True
        for r in self.resultados:
            self.miniaturas[r["id"]] = miniatura(r["id"])
