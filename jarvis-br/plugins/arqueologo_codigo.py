"""
Arqueólogo do código (3.0): "por que essa linha existe?". O JARVIS escava o histórico do Git e as
suas anotações da época e conta a história daquela linha ou função.

    "Jarvis, por que existe a linha 120 do main.py?"
    → "Ela veio no commit 'fix: áudio cortava no Windows' (14/08/2026). Nesse mesmo commit mudaram
       2 arquivos. No dia, você anotou no segundo cérebro: 'bug do áudio é a placa…'."
    "Jarvis, conta a história da função tocar() do musica.py."
"""

from __future__ import annotations

import ast
import re
import time
from collections import Counter
from pathlib import Path

from plugins._lote2 import P, norm, num1, rodar
from plugins.commit_mentiroso import git

PLUGIN = P("arqueologo_codigo", "Code archaeologist: why a line or function exists — git blame, the commit, files changed together, your notes from then.",
           "linha | funcao | historia",
           "arquivo = path inside a git repo. linha: linha (number). funcao: nome (function/class name). historia: last changes of the file.",
           "arquivo linha nome")


def blame(arq: Path, ini: int, fim: int) -> list[dict]:
    bruto = git(arq.parent, "blame", "--porcelain", "-L", f"{ini},{fim}", "--", arq.name)
    commits, por_linha, atual = {}, [], None
    for l in bruto.splitlines():
        m = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", l)
        if m:
            atual = commits.setdefault(m.group(1), {"hash": m.group(1)[:8]})
            por_linha.append(atual)
        elif atual is not None and l.startswith("summary "):
            atual["assunto"] = l[8:]
        elif atual is not None and l.startswith("author-time "):
            atual["quando"] = int(l[12:])
        elif atual is not None and l.startswith("author "):
            atual["autor"] = l[7:]
    return por_linha


def notas_da_epoca(quando: float, palavras: list[str]) -> list[str]:
    """Anotações do segundo cérebro e ideias de até 3 dias perto do commit que falam do assunto."""
    out = []
    try:
        from plugins import ideias, segundo_cerebro
        itens = [(n.get("criada", 0), f"{n.get('titulo', '')}: {n.get('texto', '')}") for n in segundo_cerebro.dados().get("notas", [])]
        itens += [(i.get("criada", 0), i.get("texto", "")) for i in ideias.dados().get("ideias", [])]
    except Exception:
        return out
    ws = [norm(w) for w in palavras if len(w) > 3]
    for t, txt in itens:
        if abs(float(t or 0) - quando) <= 3 * 86400 and (not ws or any(w in norm(txt) for w in ws)):
            out.append(txt[:160])
    return out[:3]


def _data(ts: float) -> str:
    return time.strftime("%d/%m/%Y", time.localtime(ts))


def contar(arq: Path, info: dict, palavras: list[str]) -> str:
    outros = [l for l in git(arq.parent, "show", "--name-only", "--format=", info["hash"]).splitlines() if l.strip()]
    txt = f"Veio no commit {info['hash']} \"{info.get('assunto', '?')}\" de {info.get('autor', '?')}, em {_data(info.get('quando', 0))}."
    if len(outros) > 1:
        txt += f" Nesse commit também mudaram: {', '.join(outros[:5])}" + ("…" if len(outros) > 5 else "") + "."
    notas = notas_da_epoca(info.get("quando", 0), palavras)
    if notas:
        txt += " Suas anotações daqueles dias: " + " | ".join(notas)
    return txt


def achar_funcao(src: str, nome: str) -> tuple[int, int] | None:
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == nome:
            return n.lineno, getattr(n, "end_lineno", n.lineno)
    return None


def _go(p, pl):
    arq = Path(str(p.get("arquivo") or "").strip().strip('"')).expanduser().resolve()
    if not arq.is_file():
        return "Não achei esse arquivo."
    a = p["action"]
    if a == "historia":
        log = git(arq.parent, "log", "-n", "10", "--follow", "--format=%h %ad %s", "--date=short", "--", arq.name)
        return f"Últimas mudanças em {arq.name}:\n{log.strip()}" if log.strip() else "Esse arquivo ainda não tem histórico no Git."
    if a == "linha":
        n = int(num1(p, "linha", 1))
        info = blame(arq, n, n)[0]
        linha = arq.read_text(encoding="utf-8", errors="ignore").splitlines()[n - 1].strip()
        palavras = re.findall(r"[A-Za-z_]{4,}", linha)[:5]
        return f"Linha {n}: `{linha[:90]}`\n" + contar(arq, info, palavras)
    nome = str(p.get("nome") or "").strip().rstrip("()")
    faixa = achar_funcao(arq.read_text(encoding="utf-8", errors="ignore"), nome) if arq.suffix == ".py" else None
    if not faixa:
        return f"Não achei a função ou classe '{nome}' em {arq.name}."
    por_linha = blame(arq, *faixa)
    cont = Counter(c["hash"] for c in por_linha)
    unicos = {c["hash"]: c for c in por_linha}
    ordem = sorted(unicos.values(), key=lambda c: c.get("quando", 0))
    mais = unicos[cont.most_common(1)[0][0]]
    return (f"{nome}() tem {faixa[1] - faixa[0] + 1} linhas vindas de {len(unicos)} commit(s). Nasceu em {_data(ordem[0].get('quando', 0))} "
            f"(\"{ordem[0].get('assunto', '?')}\"); a última mudança foi em {_data(ordem[-1].get('quando', 0))} "
            f"(\"{ordem[-1].get('assunto', '?')}\"). A maior parte veio de: " + contar(arq, mais, [nome]))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"linha": _go, "funcao": _go, "historia": _go}, player, "Arqueólogo")
