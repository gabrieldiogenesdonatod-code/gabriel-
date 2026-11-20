"""Raio-X do projeto (2.18): linhas por linguagem, maiores arquivos, TODO/FIXME espalhados e funções gigantes."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("raio_x_projeto", "Project X-ray: lines of code per language, biggest files, TODO/FIXME/HACK list, longest Python functions.",
           "linhas | todos | maiores | funcoes_grandes",
           "pasta = project folder (default current).", "pasta")

EXT = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".html": "HTML", ".css": "CSS", ".ino": "Arduino",
       ".cpp": "C++", ".c": "C", ".h": "C/C++", ".java": "Java", ".cs": "C#", ".lua": "Lua", ".json": "JSON",
       ".md": "Markdown", ".sh": "Shell", ".bat": "Batch", ".go": "Go", ".rs": "Rust", ".php": "PHP"}
PULAR = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}


def arquivos(pasta: Path):
    for f in pasta.rglob("*"):
        if f.is_file() and f.suffix in EXT and not PULAR & set(f.parts) and f.stat().st_size < 2_000_000:
            yield f


def _linhas(f):
    return f.read_text(encoding="utf-8", errors="ignore").splitlines()


def contar(pasta: Path) -> Counter:
    c = Counter()
    for f in arquivos(pasta):
        c[EXT[f.suffix]] += sum(1 for l in _linhas(f) if l.strip())
    return c


def todos(pasta: Path) -> list[str]:
    out = []
    for f in arquivos(pasta):
        for i, l in enumerate(_linhas(f), 1):
            m = re.search(r"\b(TODO|FIXME|HACK|XXX)\b[:\s]*(.*)", l)
            if m:
                out.append(f"{f.relative_to(pasta)}:{i} {m.group(1)} {m.group(2).strip()[:70]}")
    return out


def funcoes_grandes(pasta: Path, minimo: int = 60) -> list[tuple[int, str]]:
    import ast
    out = []
    for f in arquivos(pasta):
        if f.suffix != ".py":
            continue
        try:
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8", errors="ignore"))):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    tam = (n.end_lineno or n.lineno) - n.lineno + 1
                    if tam >= minimo:
                        out.append((tam, f"{f.relative_to(pasta)}:{n.lineno} {n.name}()"))
        except SyntaxError:
            pass
    return sorted(out, reverse=True)


def _go(p, pl):
    a, pasta = str(p.get("action")).lower(), Path(str(p.get("pasta") or ".")).expanduser()
    if not pasta.is_dir():
        return "Pasta não encontrada."
    if a == "todos":
        t = todos(pasta)
        return f"{len(t)} marcação(ões):\n" + "\n".join(t[:60]) if t else "Nenhum TODO/FIXME."
    if a == "maiores":
        fs = sorted(arquivos(pasta), key=lambda f: -len(_linhas(f)))[:10]
        return "\n".join(f"{len(_linhas(f))} linhas  {f.relative_to(pasta)}" for f in fs)
    if a == "funcoes_grandes":
        return "\n".join(f"{n} linhas  {s}" for n, s in funcoes_grandes(pasta)[:15]) or "Nenhuma função com 60+ linhas."
    c = contar(pasta)
    return "\n".join(f"{k}: {v:,}".replace(",", ".") for k, v in c.most_common()) + f"\nTotal: {sum(c.values()):,}".replace(",", ".")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("linhas todos maiores funcoes_grandes".split(), _go), player, "Raio-X")
