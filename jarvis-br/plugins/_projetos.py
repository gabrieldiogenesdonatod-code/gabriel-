"""
Ajudantes para projetos de código (fork PT-BR 1.6). Começa com "_": não é ferramenta.

Quais projetos você tem (os que você cadastrou, os que a linha do tempo viu
no VS Code e os repositórios git das pastas de sempre), commits, linguagens
e a lista de pacotes instalados para checar vulnerabilidades (OSV).
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from plugins._comum import BASE, CONFIG, ler_json, rodar, tem

ARQ = CONFIG / "projetos.json"
EXT_LINGUAGEM = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript",
                 ".html": "HTML", ".css": "CSS", ".java": "Java", ".kt": "Kotlin", ".c": "C", ".h": "C", ".cpp": "C++",
                 ".cs": "C#", ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".ino": "Arduino",
                 ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell", ".bat": "Batch", ".dart": "Dart", ".lua": "Lua",
                 ".vue": "Vue", ".svelte": "Svelte", ".json": "JSON", ".md": "Markdown"}
PULAR = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build", ".next", "target", ".idea",
         ".vscode", ".mypy_cache", ".pytest_cache"}
_cache = {"repos": ([], 0.0)}


def cadastrados() -> list[str]:
    return list((ler_json(ARQ, {}) or {}).get("pastas", []))


def repos(profundidade: int = 3) -> list[Path]:
    """O JARVIS, os cadastrados e repositórios git em Documentos/Área de Trabalho/projetos (cache 1 h)."""
    lista, quando = _cache["repos"]
    if lista and time.time() - quando < 3600:
        return lista
    achados = {BASE.resolve()}
    for p in cadastrados():
        if Path(p).is_dir():
            achados.add(Path(p).resolve())
    casa = Path.home()
    for base in [casa / "Documents", casa / "Documentos", casa / "Desktop", casa / "OneDrive" / "Desktop",
                 casa / "projetos", casa / "Projects", casa / "source" / "repos", casa / "dev"]:
        if not base.is_dir():
            continue
        for raiz, dirs, _arqs in os.walk(base):
            nivel = len(Path(raiz).relative_to(base).parts)
            if ".git" in dirs:
                achados.add(Path(raiz).resolve())
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in PULAR and not d.startswith(".")] if nivel < profundidade else []
    _cache["repos"] = (sorted(achados), time.time())
    return _cache["repos"][0]


def eh_git(pasta: Path) -> bool:
    return (pasta / ".git").exists() and tem("git")


def commits(pasta: Path, desde: float) -> list[dict]:
    """Commits desde 'desde' com arquivos e linhas mudadas."""
    if not eh_git(pasta):
        return []
    data = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(desde))
    _c, out = rodar(["git", "-C", str(pasta), "log", f"--since={data}", "--numstat", "--date=unix",
                     "--pretty=format:@@%H|%at|%an|%s"], timeout=20, encoding="utf-8")
    return ler_log(out)


def ler_log(out: str) -> list[dict]:
    """Saída do git log com --numstat → commits (pura)."""
    saida: list[dict] = []
    for linha in (out or "").splitlines():
        if linha.startswith("@@"):
            partes = linha[2:].split("|", 3)
            if len(partes) == 4:
                saida.append({"hash": partes[0][:8], "ts": float(partes[1] or 0), "autor": partes[2],
                              "msg": partes[3], "arquivos": []})
        else:
            m = re.match(r"^(\d+|-)\s+(\d+|-)\s+(.+)$", linha)
            if m and saida:
                saida[-1]["arquivos"].append((m.group(3), int(m.group(1)) if m.group(1).isdigit() else 0,
                                              int(m.group(2)) if m.group(2).isdigit() else 0))
    return saida


def linguagem(arquivo: str) -> str | None:
    return EXT_LINGUAGEM.get(Path(arquivo).suffix.lower())


def pacotes_instalados() -> list[tuple[str, str]]:
    from importlib.metadata import distributions
    vistos = {}
    for d in distributions():
        nome = (d.metadata.get("Name") or "").strip()
        if nome:
            vistos[nome.lower()] = (nome, d.version)
    return sorted(vistos.values())


def requisitos(pasta: Path) -> list[tuple[str, str]]:
    """Pacotes com versão FIXA (==) do requirements.txt de um projeto (pura no texto)."""
    arq = pasta / "requirements.txt"
    return ler_requisitos(arq.read_text(encoding="utf-8", errors="replace")) if arq.exists() else []


def ler_requisitos(texto: str) -> list[tuple[str, str]]:
    saida = []
    for linha in texto.splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*==\s*([A-Za-z0-9_.\-+]+)", linha)
        if m:
            saida.append((m.group(1), m.group(2)))
    return saida


def vulnerabilidades(pacotes: list[tuple[str, str]]) -> dict[str, list[str]]:
    """{pacote==versão: [ids]} pela base pública OSV (osv.dev), sem chave."""
    import requests
    achados: dict[str, list[str]] = {}
    for i in range(0, len(pacotes), 500):
        lote = pacotes[i:i + 500]
        r = requests.post("https://api.osv.dev/v1/querybatch", timeout=60, json={"queries": [
            {"package": {"name": n, "ecosystem": "PyPI"}, "version": v} for n, v in lote]})
        r.raise_for_status()
        for (n, v), res in zip(lote, r.json().get("results", [])):
            ids = [x.get("id") for x in (res.get("vulns") or []) if x.get("id")]
            if ids:
                achados[f"{n}=={v}"] = ids
    return achados
