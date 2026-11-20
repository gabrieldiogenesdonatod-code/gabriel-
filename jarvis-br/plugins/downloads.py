"""
Gerenciador de downloads — plugin do J.A.R.V.I.S BR.

    * Avisa quando um download TERMINA ("Download concluído: foto_produto.zip").
    * Organiza a pasta Downloads por tipo: Imagens, Vídeos, Áudios, PDFs,
      Documentos, Instaladores e Compactados. Automático (alguns minutos depois
      de cada download, para dar tempo de abrir pelo navegador) ou por voz:
      "Jarvis, organiza meus downloads".
    * "Jarvis, abre o último download" / "o que eu baixei hoje?".

Como sabe que terminou: o arquivo deixou de ser .crdownload/.part/.tmp e o
tamanho ficou parado por duas leituras seguidas. A pasta é lida a cada 5 s
(só a lista de nomes, sem abrir arquivo nenhum).

Organizar só MOVE arquivos (nada é apagado), nunca sobrescreve (cria
"nome (2).pdf") e registra desfazer: "Jarvis, desfaz" põe tudo de volta.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

from plugins._comum import (abrir_no_sistema, avisar, cfg, desfazer, mostrar, num,
                            pasta_usuario, plugin_ligado, sim, tamanho)

PLUGIN = {
    "name": "downloads",
    "brief": "Organize Downloads by type, open last download, list today's downloads.",
    "description": (
        "Downloads folder manager. action='organizar' sorts the Downloads folder into "
        "subfolders by type (images, videos, audio, PDFs, documents, installers, archives); "
        "'ultimo' opens the most recent download; 'hoje' lists what was downloaded today; "
        "'abrir_pasta' opens the Downloads folder; 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "organizar | ultimo | hoje | abrir_pasta | status"}},
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "downloads",
    "title": "Downloads",
    "fields": [
        {"key": "avisar", "label": "Avisar quando um download terminar", "type": "toggle", "default": True},
        {"key": "organizar_auto", "label": "Organizar automaticamente por tipo", "type": "toggle", "default": True},
        {"key": "espera_min", "label": "Esperar quantos minutos antes de mover", "type": "text", "default": "2"},
        {"key": "pasta", "label": "Pasta (vazio = Downloads do Windows)", "type": "text", "default": ""},
    ],
}

TIPOS = {
    "Imagens": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".svg", ".tif",
                ".tiff", ".avif", ".ico", ".raw", ".psd"},
    "Vídeos": {".mp4", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".m4v", ".flv", ".3gp", ".mpg", ".mpeg"},
    "Áudios": {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".opus", ".wma", ".mid"},
    "PDFs": {".pdf"},
    "Documentos": {".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".xls", ".xlsx", ".csv", ".ods",
                   ".ppt", ".pptx", ".odp", ".epub", ".xml", ".json"},
    "Instaladores": {".exe", ".msi", ".msix", ".msixbundle", ".appx", ".appxbundle", ".dmg", ".pkg",
                     ".deb", ".rpm", ".appimage", ".apk"},
    "Compactados": {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".iso"},
}
PARCIAIS = (".crdownload", ".part", ".partial", ".download", ".tmp", ".opdownload", ".!ut",
            ".aria2", ".dtapart")
_IGNORAR = {"desktop.ini", "thumbs.db", ".ds_store"}

_thread: threading.Thread | None = None
_parar = threading.Event()
_concluidos: list[dict] = []          # {"caminho", "quando"} desta sessão


def pasta() -> Path:
    c = cfg("downloads", PLUGIN_SETTINGS)
    p = str(c.get("pasta") or "").strip()
    return Path(os.path.expanduser(p)) if p else pasta_usuario("Downloads")


def categoria(nome: str) -> str | None:
    ext = Path(nome).suffix.lower()
    if nome.lower().endswith((".tar.gz", ".tar.xz", ".tar.bz2")):
        return "Compactados"
    for cat, exts in TIPOS.items():
        if ext in exts:
            return cat
    return None


def eh_parcial(nome: str) -> bool:
    return nome.lower().endswith(PARCIAIS)


def destino_livre(dest: Path) -> Path:
    """'foto.png' já existe → 'foto (2).png', 'foto (3).png'…"""
    if not dest.exists():
        return dest
    n = 2
    while True:
        alt = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
        if not alt.exists():
            return alt
        n += 1


def _listar(raiz: Path) -> dict[str, tuple[int, float]]:
    """{nome: (tamanho, mtime)} só do primeiro nível, sem abrir arquivos."""
    saida = {}
    try:
        with os.scandir(raiz) as it:
            for e in it:
                if not e.is_file(follow_symlinks=False):
                    continue
                if e.name.lower() in _IGNORAR or e.name.startswith((".", "~$")):
                    continue
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                saida[e.name] = (st.st_size, st.st_mtime)
    except FileNotFoundError:
        pass
    return saida


def organizar(player=None, so_estes: list[str] | None = None, idade_min_s: float = 10) -> str:
    raiz = pasta()
    if not raiz.exists():
        return f"Não encontrei a pasta {raiz}."
    movidos: list[tuple[str, str]] = []
    agora = time.time()
    for nome, (_t, mtime) in _listar(raiz).items():
        if so_estes is not None and nome not in so_estes:
            continue
        if eh_parcial(nome) or agora - mtime < idade_min_s:
            continue
        cat = categoria(nome)
        if not cat:
            continue
        origem = raiz / nome
        dest = destino_livre(raiz / cat / nome)
        try:
            dest.parent.mkdir(exist_ok=True)
            shutil.move(str(origem), str(dest))
            movidos.append((str(origem), str(dest)))
        except Exception as e:
            print(f"[Downloads] não movi {nome}: {e}")
    if not movidos:
        return "A pasta Downloads já está organizada."

    def voltar(lista=list(movidos)):
        ok = 0
        for orig, dest in lista:
            try:
                if Path(dest).exists():
                    shutil.move(dest, str(destino_livre(Path(orig))))
                    ok += 1
            except Exception:
                pass
        return f"{ok} arquivo(s) de volta para Downloads."

    desfazer(f"organizar {len(movidos)} download(s)", voltar)
    contagem: dict[str, int] = {}
    for _o, d in movidos:
        cat = Path(d).parent.name
        contagem[cat] = contagem.get(cat, 0) + 1
    return (f"Organizei {len(movidos)} arquivo(s): " +
            ", ".join(f"{n} em {c}" for c, n in sorted(contagem.items(), key=lambda kv: -kv[1])) + ".")


def _laco(player):
    raiz = pasta()
    anterior = _listar(raiz)
    candidatos: dict[str, tuple[int, int]] = {}        # nome → (tamanho, leituras estáveis)
    pendentes: dict[str, float] = {}                   # nome → hora em que terminou
    while not _parar.wait(5):
        if not plugin_ligado("downloads"):
            continue
        c = cfg("downloads", PLUGIN_SETTINGS)
        raiz_atual = pasta()
        if raiz_atual != raiz:
            raiz, anterior, candidatos = raiz_atual, _listar(raiz_atual), {}
            continue
        atual = _listar(raiz)
        for nome, (tam, _m) in atual.items():
            if eh_parcial(nome):
                continue
            if nome not in anterior or nome in candidatos:
                tam_ant, estavel = candidatos.get(nome, (-1, 0))
                estavel = estavel + 1 if tam == tam_ant else 0
                candidatos[nome] = (tam, estavel)
                if estavel >= 2 and tam > 0:
                    candidatos.pop(nome, None)
                    _concluidos.append({"caminho": str(raiz / nome), "quando": time.time()})
                    del _concluidos[:-50]
                    if sim(c.get("avisar", True)):
                        avisar(player, f"Download concluído: {nome} ({tamanho(tam)}).", "DOWNLOADS")
                    if sim(c.get("organizar_auto", True)) and categoria(nome):
                        pendentes[nome] = time.time()
        for nome in list(candidatos):
            if nome not in atual:
                candidatos.pop(nome, None)
        espera = max(0.0, num(c.get("espera_min"), 2)) * 60
        prontos = [n for n, t in pendentes.items() if time.time() - t >= espera]
        if prontos:
            for n in prontos:
                pendentes.pop(n, None)
            r = organizar(player, so_estes=prontos, idade_min_s=0)
            print(f"[Downloads] {r}")
        anterior = atual


def on_session_start(player) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _parar.clear()
    _thread = threading.Thread(target=_laco, args=(player,), daemon=True, name="downloads")
    _thread.start()


def _recentes(desde: float) -> list[Path]:
    raiz = pasta()
    arquivos = []
    for base in [raiz] + [raiz / c for c in TIPOS]:
        for nome, (_t, mtime) in _listar(base).items():
            if mtime >= desde and not eh_parcial(nome):
                arquivos.append((mtime, base / nome))
    return [p for _m, p in sorted(arquivos, reverse=True)]


def run(parameters: dict, player=None, session_memory=None) -> str:
    a = str((parameters or {}).get("action") or "status").strip().lower()
    try:
        if a == "organizar":
            return organizar(player)
        if a == "ultimo":
            vivos = [d for d in _concluidos if Path(d["caminho"]).exists()]
            alvo = Path(vivos[-1]["caminho"]) if vivos else next(iter(_recentes(0)), None)
            if alvo is None:
                return "Não encontrei downloads."
            return f"Abrindo {alvo.name}." if abrir_no_sistema(str(alvo)) else f"Não consegui abrir {alvo.name}."
        if a == "hoje":
            inicio = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
            lista = _recentes(inicio)
            if not lista:
                return "Nada baixado hoje."
            mostrar(player, "BAIXADOS HOJE", "\n".join(
                f"{time.strftime('%H:%M', time.localtime(p.stat().st_mtime))}  {p.name}" for p in lista[:40]))
            return f"Hoje você baixou {len(lista)} arquivo(s); o último foi {lista[0].name}."
        if a == "abrir_pasta":
            return "Abrindo a pasta Downloads." if abrir_no_sistema(str(pasta())) else "Não consegui abrir."
        if a == "status":
            c = cfg("downloads", PLUGIN_SETTINGS)
            soltos = [n for n in _listar(pasta()) if categoria(n)]
            return (f"Vigiando {pasta()}. Aviso de download: {'ligado' if sim(c.get('avisar', True)) else 'desligado'}; "
                    f"organização automática: {'ligada' if sim(c.get('organizar_auto', True)) else 'desligada'}. "
                    f"{len(soltos)} arquivo(s) soltos na pasta.")
        return "Use organizar, ultimo, hoje, abrir_pasta ou status."
    except Exception as e:
        return f"O gerenciador de downloads falhou: {e}"
