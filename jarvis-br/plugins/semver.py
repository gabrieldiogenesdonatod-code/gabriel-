"""Versões e commits (2.18): confere mensagem no padrão Conventional Commits e calcula a próxima versão (semver)."""
from __future__ import annotations

import re

from plugins._lote2 import P, rodar

PLUGIN = P("semver", "Conventional Commits checker (feat/fix/docs…) and semantic version bump: next version from a list of commit messages.",
           "validar | proxima | comparar",
           "validar: texto (commit message). proxima: versao (current, e.g. 1.4.2), texto (commit messages, one per line). "
           "comparar: versao, texto (other version).",
           "texto versao")

TIPOS = "feat fix docs style refactor perf test build ci chore revert".split()
_RX = re.compile(r"^(?P<tipo>\w+)(\((?P<escopo>[\w\-./ ]+)\))?(?P<quebra>!)?: (?P<desc>.+)")


def validar(msg: str) -> tuple[bool, str]:
    linha = msg.strip().splitlines()[0] if msg.strip() else ""
    m = _RX.match(linha)
    if not m:
        return False, "Formato: tipo(escopo opcional): descrição — ex.: 'feat(loja): adiciona fiado'."
    if m["tipo"] not in TIPOS:
        return False, f"Tipo '{m['tipo']}' fora do padrão. Use: {', '.join(TIPOS)}."
    if len(linha) > 72:
        return False, "A primeira linha passou de 72 caracteres."
    return True, "Mensagem no padrão."


def ler(v: str) -> tuple[int, int, int]:
    n = [int(x) for x in re.findall(r"\d+", v)[:3]]
    return tuple(n + [0] * (3 - len(n)))


def proxima(versao: str, commits: list[str]) -> str:
    ma, mi, pa = ler(versao)
    nivel = 0
    for c in commits:
        m = _RX.match(c.strip())
        if (m and m["quebra"]) or "BREAKING CHANGE" in c:
            nivel = 3
        elif m and m["tipo"] == "feat":
            nivel = max(nivel, 2)
        elif m and m["tipo"] in ("fix", "perf"):
            nivel = max(nivel, 1)
    if nivel == 3:
        return f"{ma + 1}.0.0"
    if nivel == 2:
        return f"{ma}.{mi + 1}.0"
    return f"{ma}.{mi}.{pa + 1}" if nivel == 1 else f"{ma}.{mi}.{pa}"


def _go(p, pl):
    a, t = str(p.get("action")).lower(), str(p.get("texto") or "")
    if a == "validar":
        return validar(t)[1]
    if a == "comparar":
        x, y = ler(str(p.get("versao"))), ler(t)
        return "Iguais." if x == y else f"{p.get('versao')} é {'mais nova' if x > y else 'mais antiga'}."
    nova = proxima(str(p.get("versao") or "0.1.0"), t.splitlines())
    return f"Próxima versão: {nova}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("validar proxima comparar".split(), _go), player)
