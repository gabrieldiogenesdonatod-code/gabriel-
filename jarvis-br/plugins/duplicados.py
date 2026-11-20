"""
Duplicados e fotos borradas (fork PT-BR 2.16, ideia 17).

    "Jarvis, procura arquivos duplicados em Downloads"
    "Jarvis, acha fotos tremidas na pasta Imagens"
    "Jarvis, limpa os duplicados"            → mostra o que vai sair e pede CONFIRMAÇÃO na tela

DUPLICADOS: compara pelo tamanho, depois pelo começo do arquivo e só então pelo
conteúdo inteiro (SHA-256) — dois arquivos só são "iguais" se forem idênticos
byte a byte, mesmo com nomes diferentes. Em cada grupo fica o MAIS ANTIGO (o
original); os outros são as cópias.

BORRADAS: mede a nitidez de cada foto (variância do Laplaciano, OpenCV) e
marca as muito abaixo da média da própria pasta — assim uma pasta de fotos
escuras não vira "tudo borrado". Fotos de tela e muito pequenas ficam de fora.

Nada é apagado sem você apertar CONFIRMAR, e vai para a LIXEIRA (dá para
recuperar). A prévia (painel e uma página com miniaturas das borradas) mostra
exatamente o que sai.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict
from pathlib import Path

from plugins._comum import confirmar, mostrar, pasta_usuario, tamanho

PLUGIN = {
    "name": "duplicados",
    "brief": "Find duplicate files and blurry photos in a folder; preview; delete to Recycle Bin only after confirmation.",
    "description": (
        "Duplicates and blurry photos. action='duplicados' with pasta (Downloads, Imagens, Documentos, Desktop or a path) "
        "finds identical files. action='borradas' with pasta finds blurry photos. action='limpar' with tipo = duplicados | "
        "borradas asks on-screen confirmation and sends the extra copies / blurry photos of the last scan to the "
        "Recycle Bin. Never say they were deleted before the user confirms."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "duplicados | borradas | limpar"},
                       "pasta": {"type": "STRING"}, "tipo": {"type": "STRING"}},
        "required": ["action"],
    },
}

_ultimo: dict = {"duplicados": [], "borradas": []}
IMAGENS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp"}
_PULAR = {"node_modules", ".git", "__pycache__", "AppData", "$RECYCLE.BIN", "venv", ".venv"}


def _pasta(nome: str) -> Path:
    apelidos = {"downloads": "Downloads", "imagens": "Pictures", "fotos": "Pictures", "documentos": "Documents",
                "desktop": "Desktop", "area de trabalho": "Desktop", "videos": "Videos", "vídeos": "Videos"}
    n = str(nome or "Downloads").strip()
    if n.lower() in apelidos:
        return pasta_usuario(apelidos[n.lower()])
    return Path(n).expanduser()


def arquivos(raiz: Path, prazo: float, extensoes: set | None = None):
    for dirpath, dirs, nomes in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in _PULAR and not d.startswith(".")]
        if time.monotonic() > prazo:
            return
        for n in nomes:
            p = Path(dirpath) / n
            if extensoes and p.suffix.lower() not in extensoes:
                continue
            yield p


def _hash(p: Path, ate: int | None = None) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        lido = 0
        while True:
            bloco = f.read(1 << 20 if ate is None else min(1 << 20, ate - lido))
            if not bloco:
                break
            h.update(bloco)
            lido += len(bloco)
            if ate is not None and lido >= ate:
                break
    return h.hexdigest()


def achar_duplicados(caminhos, minimo: int = 1024) -> list[list[Path]]:
    """Grupos de arquivos idênticos; o primeiro de cada grupo é o mais antigo (pura, só lê)."""
    por_tamanho: dict[int, list[Path]] = defaultdict(list)
    for p in caminhos:
        try:
            t = p.stat().st_size
        except OSError:
            continue
        if t >= minimo:
            por_tamanho[t].append(p)
    grupos = []
    for lista in por_tamanho.values():
        if len(lista) < 2:
            continue
        por_inicio: dict[str, list[Path]] = defaultdict(list)
        for p in lista:
            try:
                por_inicio[_hash(p, 64 * 1024)].append(p)
            except OSError:
                continue
        for parecidos in por_inicio.values():
            if len(parecidos) < 2:
                continue
            por_conteudo: dict[str, list[Path]] = defaultdict(list)
            for p in parecidos:
                try:
                    por_conteudo[_hash(p)].append(p)
                except OSError:
                    continue
            for iguais in por_conteudo.values():
                if len(iguais) > 1:
                    grupos.append(sorted(iguais, key=lambda x: (x.stat().st_mtime, len(str(x)))))
    return sorted(grupos, key=lambda g: -g[0].stat().st_size * (len(g) - 1))


def nitidez(p: Path) -> float | None:
    try:
        import cv2
        import numpy as np
        dados = np.fromfile(str(p), dtype=np.uint8)
        img = cv2.imdecode(dados, cv2.IMREAD_GRAYSCALE)
        if img is None or min(img.shape[:2]) < 300:
            return None
        escala = 1000 / max(img.shape[:2])
        if escala < 1:
            img = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
        return float(cv2.Laplacian(img, cv2.CV_64F).var())
    except Exception:
        return None


def borradas(notas: dict[Path, float], fator: float = 0.25, absoluto: float = 60.0) -> list[tuple[Path, float]]:
    """Fotos bem abaixo da mediana da própria pasta (e abaixo de um mínimo absoluto) (pura)."""
    if len(notas) < 3:
        return [(p, v) for p, v in notas.items() if v < absoluto * 0.5]
    valores = sorted(notas.values())
    mediana = valores[len(valores) // 2]
    corte = min(absoluto, mediana * fator)
    return sorted(((p, v) for p, v in notas.items() if v < corte), key=lambda x: x[1])


def _galeria(lista: list[tuple[Path, float]]) -> Path:
    from plugins._comum import MEMORIA
    arq = MEMORIA / "fotos_borradas.html"
    itens = "".join(f'<figure><img src="{p.as_uri()}" loading="lazy"><figcaption>{p.name}<br>nitidez {v:.0f}'
                    f'</figcaption></figure>' for p, v in lista[:300])
    arq.write_text("<!doctype html><meta charset=utf-8><title>Fotos borradas</title><style>body{background:#111;color:#ddd;"
                   "font:14px sans-serif}figure{display:inline-block;width:220px;margin:6px}img{width:220px;height:160px;"
                   "object-fit:cover}</style><h2>Fotos que parecem borradas (nada foi apagado)</h2>" + itens,
                   encoding="utf-8")
    return arq


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "duplicados").lower()
    try:
        if a == "duplicados":
            raiz = _pasta(p.get("pasta"))
            if not raiz.exists():
                return f"Não achei a pasta {raiz}."
            grupos = achar_duplicados(arquivos(raiz, time.monotonic() + 90))
            _ultimo["duplicados"] = grupos
            if not grupos:
                return f"Nenhum arquivo duplicado em {raiz.name}."
            sobra = sum(g[0].stat().st_size * (len(g) - 1) for g in grupos)
            linhas = []
            for g in grupos[:80]:
                linhas.append(f"FICA  {g[0]}  ({tamanho(g[0].stat().st_size)})")
                linhas += [f"  sai {x}" for x in g[1:]]
            mostrar(player, f"DUPLICADOS — {raiz.name}", "\n".join(linhas))
            copias = sum(len(g) - 1 for g in grupos)
            return (f"Achei {copias} cópia(s) em {len(grupos)} grupo(s), {tamanho(sobra)} a liberar. Fica sempre o mais "
                    "antigo. Quer que eu mande as cópias para a lixeira?")
        if a == "borradas":
            raiz = _pasta(p.get("pasta") or "Imagens")
            notas = {}
            for f in arquivos(raiz, time.monotonic() + 120, IMAGENS):
                if "screenshot" in f.name.lower() or "captura" in f.name.lower():
                    continue
                v = nitidez(f)
                if v is not None:
                    notas[f] = v
            ruins = borradas(notas)
            _ultimo["borradas"] = ruins
            if not ruins:
                return f"Olhei {len(notas)} fotos em {raiz.name} e nenhuma parece borrada."
            pagina = _galeria(ruins)
            mostrar(player, f"FOTOS BORRADAS — {raiz.name}", "\n".join(f"{v:7.0f}  {p_}" for p_, v in ruins[:200])
                    + f"\n\nMiniaturas: {pagina}")
            try:
                import webbrowser
                webbrowser.open(pagina.as_uri())
            except Exception:
                pass
            return (f"De {len(notas)} fotos, {len(ruins)} parecem borradas. Abri uma página com as miniaturas para "
                    "você conferir. Quer mandar para a lixeira?")
        if a == "limpar":
            tipo = "borradas" if "borr" in str(p.get("tipo") or "").lower() else "duplicados"
            if tipo == "duplicados":
                alvos = [x for g in _ultimo["duplicados"] for x in g[1:]]
            else:
                alvos = [x for x, _v in _ultimo["borradas"]]
            alvos = [x for x in alvos if x.exists()]
            if not alvos:
                return "Primeiro preciso procurar. Diga 'procura duplicados' ou 'acha fotos borradas'."
            total = sum(x.stat().st_size for x in alvos)

            def executar() -> str:
                from send2trash import send2trash
                ok = 0
                for x in alvos:
                    try:
                        send2trash(str(x))
                        ok += 1
                    except Exception:
                        pass
                _ultimo[tipo] = []
                return f"Mandei {ok} arquivo(s) para a lixeira ({tamanho(total)}). Dá para recuperar de lá."
            return confirmar(f"duplicados_{tipo}", f"Mandar {len(alvos)} {tipo} para a lixeira?",
                             f"{len(alvos)} arquivo(s), {tamanho(total)}. Vão para a lixeira (dá para recuperar).",
                             executar)
        return "Use duplicados, borradas ou limpar."
    except Exception as e:
        return f"A busca falhou: {e}"
