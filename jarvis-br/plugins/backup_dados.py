"""Backup dos dados (2.19): guarda num zip tudo que o JARVIS sabe (memórias, listas, loja, modos) e restaura quando precisar."""
from __future__ import annotations

import time
import zipfile
from pathlib import Path

from plugins._comum import MEMORIA, pasta_jarvis
from plugins._lote2 import P, rodar

PLUGIN = P("backup_dados", "Back up all JARVIS data (memories, lists, store, modes) to a zip in Documents/JARVIS/Backups; list and restore.",
           "fazer | listar | restaurar | limpar",
           "restaurar: nome (file from listar; makes a safety backup first). limpar keeps only the 5 newest backups.",
           "nome")

FORA = {".py", ".pyc"}


def arquivos(pasta: Path):
    return [f for f in pasta.rglob("*") if f.is_file() and f.suffix not in FORA and "__pycache__" not in f.parts]


def fazer(destino: Path, origem: Path, etiqueta: str = "backup") -> Path:
    arq = destino / f"jarvis_{etiqueta}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED) as z:
        for f in arquivos(origem):
            z.write(f, f.relative_to(origem).as_posix())
    return arq


def restaurar(arq: Path, origem: Path) -> int:
    n = 0
    with zipfile.ZipFile(arq) as z:
        for m in z.infolist():
            alvo = (origem / m.filename).resolve()
            if m.is_dir() or Path(m.filename).suffix in FORA or origem.resolve() not in alvo.parents:
                continue                                   # nunca escreve fora da pasta de dados
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(z.read(m))
            n += 1
    return n


def _go(p, pl):
    a, pasta = p["action"], pasta_jarvis("Backups")
    zips = sorted(pasta.glob("jarvis_*.zip"), key=lambda f: f.stat().st_mtime, reverse=True)
    if a == "fazer":
        arq = fazer(pasta, MEMORIA)
        return f"Backup feito: {arq.name} ({arq.stat().st_size // 1024} KB), em {pasta}."
    if a == "listar":
        return "\n".join(f"{f.name} ({f.stat().st_size // 1024} KB)" for f in zips[:15]) or "Nenhum backup ainda."
    if a == "limpar":
        for f in zips[5:]:
            f.unlink()
        return f"Mantive os {min(5, len(zips))} mais novos e apaguei {max(0, len(zips) - 5)}."
    q = str(p.get("nome") or "").strip()
    alvo = next((f for f in zips if q and q in f.name), zips[0] if zips and not q else None)
    if not alvo:
        return "Não achei esse backup. Diga 'listar'."
    fazer(pasta, MEMORIA, "antes_de_restaurar")
    return f"Restaurei {restaurar(alvo, MEMORIA)} arquivo(s) de {alvo.name}. Guardei antes uma cópia do estado atual. Reinicie o JARVIS."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("fazer listar restaurar limpar".split(), _go), player, "Backup")
