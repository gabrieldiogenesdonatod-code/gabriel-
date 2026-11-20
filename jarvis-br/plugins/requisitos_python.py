"""Requisitos Python (2.18): compara os imports do projeto com o requirements.txt — o que falta e o que sobra."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("requisitos_python", "Python project deps check: imports vs requirements.txt (missing / unused), and write a requirements.txt draft.",
           "verificar | gerar",
           "pasta = project folder. gerar writes requirements_sugerido.txt.", "pasta")

APELIDOS = {"cv2": "opencv-python", "PIL": "pillow", "yaml": "pyyaml", "sklearn": "scikit-learn", "bs4": "beautifulsoup4",
            "dotenv": "python-dotenv", "serial": "pyserial", "docx": "python-docx", "dateutil": "python-dateutil",
            "google": "google-genai", "win32api": "pywin32", "win32con": "pywin32", "win32com": "pywin32", "Crypto": "pycryptodome",
            "googleapiclient": "google-api-python-client", "pptx": "python-pptx", "piper": "piper-tts",
            "paho": "paho-mqtt", "multipart": "python-multipart", "win10toast": "win10toast"}
IGNORAR = {"tests", "setup"}


def imports(pasta: Path) -> set[str]:
    locais = {p.stem for p in pasta.rglob("*.py")} | {p.name for p in pasta.iterdir() if p.is_dir()}
    nomes: set[str] = set()
    for f in pasta.rglob("*.py"):
        if any(x in f.parts for x in (".venv", "venv", "node_modules", "__pycache__")):
            continue
        try:
            arv = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for n in ast.walk(arv):
            if isinstance(n, ast.Import):
                nomes |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                nomes.add(n.module.split(".")[0])
    std = set(getattr(sys, "stdlib_module_names", ()))
    return {n for n in nomes if n not in std and n not in locais and n not in IGNORAR and not n.startswith("_")}


def requisitos(pasta: Path) -> set[str]:
    arq = pasta / "requirements.txt"
    if not arq.is_file():
        return set()
    linhas = (l.split("#")[0].strip() for l in arq.read_text(encoding="utf-8").splitlines())
    return {re.split(r"[<>=!~\[; ]", l)[0].lower() for l in linhas if l and not l.startswith("-")}


def comparar(usados: set[str], req: set[str]) -> tuple[list[str], list[str]]:
    pacotes = {APELIDOS.get(u, u).lower().replace("_", "-") for u in usados}
    reqn = {r.replace("_", "-") for r in req}
    return sorted(pacotes - reqn), sorted(reqn - pacotes)


def _go(p, pl):
    pasta = Path(str(p.get("pasta") or ".")).expanduser()
    if not pasta.is_dir():
        return "Pasta não encontrada."
    usados = imports(pasta)
    if str(p.get("action")).lower() == "gerar":
        (pasta / "requirements_sugerido.txt").write_text("\n".join(sorted(APELIDOS.get(u, u) for u in usados)) + "\n")
        return f"Escrevi requirements_sugerido.txt com {len(usados)} pacote(s)."
    falta, sobra = comparar(usados, requisitos(pasta))
    return f"Faltam no requirements: {', '.join(falta) or 'nada'}.\nTalvez sem uso (podem ser opcionais): {', '.join(sobra) or 'nada'}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"verificar": _go, "gerar": _go}, player, "Requisitos")
