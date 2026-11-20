"""Segredos no código (2.19): procura chaves de API, tokens e senhas esquecidos no projeto antes de você subir para o GitHub."""
from __future__ import annotations

import re
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("segredos_codigo", "Scan a project for leaked secrets before pushing: API keys, tokens, private keys, passwords in URLs or assignments (values masked).",
           "varrer | padroes", "pasta = project folder (default current).", "pasta")

PADROES = [("chave Google", r"AIza[0-9A-Za-z_\-]{35}"), ("chave AWS", r"AKIA[0-9A-Z]{16}"), ("token GitHub", r"gh[pousr]_[A-Za-z0-9]{36,}"),
           ("token Slack", r"xox[baprs]-[A-Za-z0-9\-]{10,}"), ("chave estilo sk-", r"\bsk-[A-Za-z0-9_\-]{20,}"),
           ("chave privada", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), ("senha em URL", r"://[^/\s:@]+:[^/\s:@]{3,}@"),
           ("segredo em atribuição", r"(?i)\b(?:api[_-]?key|secret|token|senha|password|passwd)\b\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']")]
PULAR = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
TEXTO = {".py", ".js", ".ts", ".json", ".env", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".txt", ".md", ".html", ".sh", ".bat",
         ".ps1", ".ino", ".h", ".cpp", ".java", ".cs", ".php", ".go", ".rb", ""}


def achar(texto: str) -> list[tuple[int, str, str]]:
    """(linha, tipo, trecho mascarado) de cada segredo aparente. Pura."""
    out = []
    for i, l in enumerate(texto.splitlines(), 1):
        for tipo, rx in PADROES:
            m = re.search(rx, l)
            if m and "exemplo" not in l.lower() and "example" not in l.lower():
                s = m.group(0)
                out.append((i, tipo, s[:6] + "…" + s[-2:]))
                break
    return out


def _go(p, pl):
    if p["action"] == "padroes":
        return "Procuro: " + ", ".join(t for t, _ in PADROES) + "."
    pasta = Path(str(p.get("pasta") or ".")).expanduser()
    if not pasta.is_dir():
        return "Pasta não encontrada."
    achados = []
    for f in pasta.rglob("*"):
        if f.is_file() and f.suffix.lower() in TEXTO and not PULAR & set(f.parts) and f.stat().st_size < 1_000_000:
            for linha, tipo, trecho in achar(f.read_text(encoding="utf-8", errors="ignore")):
                achados.append(f"{f.relative_to(pasta)}:{linha} {tipo} ({trecho})")
    if not achados:
        return "Nenhum segredo aparente. Pode subir."
    return (f"{len(achados)} possível(is) segredo(s). Tire do código, ponha no .env e troque a chave se já subiu:\n" + "\n".join(achados[:50]))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"varrer": _go, "padroes": _go}, player, "Segredos")
