"""
Assistente de Git (fork PT-BR 2.17).

    "Jarvis, quais projetos têm mudança não commitada?"     (varre a pasta de projetos)
    "Jarvis, como está o repositório do jarvis?"             (branch, mudanças, atrás/à frente)
    "Jarvis, faz commit no jarvis"                           → mensagem escrita pela IA a partir do diff, com CONFIRMAÇÃO
    "Jarvis, puxa as atualizações do jarvis"                 (git pull --ff-only, seguro)

Nunca dá push, nunca força nada. A pasta de projetos fica em ⚙ → Assistente de Git
(padrão: Documentos, Desktop e a pasta do usuário, até 3 níveis).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from plugins._comum import cfg, confirmar, mostrar, pasta_usuario

PLUGIN = {
    "name": "git_assistente",
    "brief": "Git helper: scan projects for uncommitted changes, repo status, AI commit message (confirmed), safe pull.",
    "description": (
        "Git helper. action='varrer' lists repos with uncommitted changes or unpushed commits. action='status' with "
        "projeto (name or path). action='commit' with projeto (optional mensagem; otherwise written from the diff) asks "
        "on-screen confirmation. action='pull' with projeto (fast-forward only). Never pushes."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "projeto": {"type": "STRING"},
                                                    "mensagem": {"type": "STRING"}}, "required": ["action"]},
}

PLUGIN_SETTINGS = {"namespace": "git_assistente", "title": "Assistente de Git",
                   "fields": [{"key": "pastas", "label": "Pastas de projetos (uma por linha)", "type": "text", "default": ""}]}


def git(repo: Path, *args, timeout: float = 30) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r.stdout


def repos() -> list[Path]:
    raizes = [Path(x).expanduser() for x in str(cfg("git_assistente", PLUGIN_SETTINGS).get("pastas") or "").split()]
    raizes = raizes or [pasta_usuario("Documents"), pasta_usuario("Desktop"), Path.home() / "source", Path.home() / "projetos"]
    achados = []
    for raiz in raizes:
        if not raiz.exists():
            continue
        base = len(raiz.parts)
        for d, subs, _ in os.walk(raiz):
            if ".git" in subs:
                achados.append(Path(d))
                subs[:] = []
                continue
            subs[:] = [s for s in subs if not s.startswith(".") and s not in ("node_modules", "venv", ".venv")]
            if len(Path(d).parts) - base >= 3:
                subs[:] = []
    return achados


def achar(nome: str) -> Path | None:
    if nome and Path(nome).expanduser().joinpath(".git").exists():
        return Path(nome).expanduser()
    n = str(nome or "").lower()
    cands = [r for r in repos() if n in r.name.lower()]
    return min(cands, key=lambda r: len(r.name)) if cands else None


def resumo_status(saida: str) -> dict:
    """'git status --porcelain=v1 -b' → contagens (pura)."""
    linhas = saida.splitlines()
    cab = linhas[0] if linhas and linhas[0].startswith("##") else ""
    import re
    frente = int(re.search(r"ahead (\d+)", cab).group(1)) if "ahead" in cab else 0
    atras = int(re.search(r"behind (\d+)", cab).group(1)) if "behind" in cab else 0
    corpo = [l for l in linhas if not l.startswith("##")]
    return {"branch": cab[3:].split("...")[0] if cab else "?", "mudados": sum(1 for l in corpo if not l.startswith("??")),
            "novos": sum(1 for l in corpo if l.startswith("??")), "frente": frente, "atras": atras}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "varrer").lower()
    try:
        if a == "varrer":
            linhas = []
            for r in repos():
                try:
                    s = resumo_status(git(r, "status", "--porcelain=v1", "-b"))
                except Exception:
                    continue
                if s["mudados"] or s["novos"] or s["frente"]:
                    linhas.append(f"{r.name}: {s['mudados']} mudado(s), {s['novos']} novo(s), {s['frente']} commit(s) sem push")
            if not linhas:
                return "Todos os projetos estão limpos."
            mostrar(player, "GIT — PENDÊNCIAS", "\n".join(linhas))
            return f"{len(linhas)} projeto(s) com pendência: " + "; ".join(linhas[:4]) + "."
        r = achar(str(p.get("projeto") or ""))
        if not r:
            return "Não achei esse repositório."
        if a == "status":
            s = resumo_status(git(r, "status", "--porcelain=v1", "-b"))
            ult = git(r, "log", "-1", "--format=%s (%cr)").strip()
            return (f"{r.name} no branch {s['branch']}: {s['mudados']} mudado(s), {s['novos']} novo(s), {s['frente']} "
                    f"à frente, {s['atras']} atrás. Último commit: {ult}.")
        if a == "pull":
            return f"{r.name}: " + (git(r, "pull", "--ff-only", timeout=90).strip().splitlines() or ["ok"])[-1]
        if a == "commit":
            diff = git(r, "diff", "HEAD", "--stat") + git(r, "diff", "HEAD")[:8000]
            novos = git(r, "ls-files", "--others", "--exclude-standard").split()
            if not diff.strip() and not novos:
                return "Não há nada para commitar."
            msg = str(p.get("mensagem") or "").strip()
            if not msg:
                from plugins import _ia
                msg = (_ia.perguntar("Escreva UMA mensagem de commit curta (até 72 letras), em português, no imperativo, "
                                     f"para estas mudanças. Só a mensagem.\nArquivos novos: {novos[:20]}\n{diff}", False, 30)
                       or "Atualiza projeto").strip().strip('"').splitlines()[0][:72]

            def fazer() -> str:
                git(r, "add", "-A")
                git(r, "commit", "-m", msg)
                return f"Commit feito em {r.name}: {msg}"
            return confirmar(f"git_commit_{r.name}", f"Commit em {r.name}", f"Mensagem: {msg}\n(git add -A; sem push)", fazer)
        return "Use varrer, status, commit ou pull."
    except FileNotFoundError:
        return "O Git não está instalado (winget install Git.Git)."
    except Exception as e:
        return f"O Git reclamou: {e}"
