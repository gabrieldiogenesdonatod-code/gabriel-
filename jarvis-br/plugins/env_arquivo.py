"""Arquivo .env (2.19): lista as chaves sem mostrar os valores, compara com o .env.example e confere se o .env está fora do Git."""
from __future__ import annotations

from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("env_arquivo", ".env helper: list keys with masked values, compare .env with .env.example (missing/extra keys), check .env is git-ignored.",
           "chaves | comparar | protegido", "pasta = project folder (default current).", "pasta")


def ler_env(texto: str) -> dict[str, str]:
    out = {}
    for l in texto.splitlines():
        l = l.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.removeprefix("export ").split("=", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def mascarar(v: str) -> str:
    return "(vazio)" if not v else v[:2] + "•" * min(8, max(3, len(v) - 2)) if len(v) > 4 else "••••"


def ignorado(gitignore: str) -> bool:
    regras = [l.strip() for l in gitignore.splitlines()]
    return any(r in (".env", "*.env", ".env*", "/.env", ".env.*") for r in regras)


def _go(p, pl):
    a, pasta = p["action"], Path(str(p.get("pasta") or ".")).expanduser()
    env = pasta / ".env"
    if not env.is_file():
        return "Não achei um arquivo .env nessa pasta."
    chaves = ler_env(env.read_text(encoding="utf-8", errors="ignore"))
    if a == "chaves":
        return "\n".join(f"{k} = {mascarar(v)}" for k, v in chaves.items()) or "O .env está vazio."
    if a == "comparar":
        ex = next((pasta / n for n in (".env.example", ".env.sample", ".env.exemplo") if (pasta / n).is_file()), None)
        if not ex:
            return "Não há .env.example para comparar."
        modelo = ler_env(ex.read_text(encoding="utf-8", errors="ignore"))
        falta, sobra = sorted(set(modelo) - set(chaves)), sorted(set(chaves) - set(modelo))
        vazias = sorted(k for k, v in chaves.items() if not v)
        return (f"Faltam no .env: {', '.join(falta) or 'nenhuma'}. Não estão no exemplo: {', '.join(sobra) or 'nenhuma'}. "
                f"Sem valor: {', '.join(vazias) or 'nenhuma'}.")
    gi = pasta / ".gitignore"
    ok = gi.is_file() and ignorado(gi.read_text(encoding="utf-8", errors="ignore"))
    return "O .env está no .gitignore. Seguro." if ok else "ATENÇÃO: o .env NÃO está no .gitignore. Adicione uma linha '.env' antes do próximo commit."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"chaves": _go, "comparar": _go, "protegido": _go}, player, ".env")
