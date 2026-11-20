"""Qualidade do código (2.19): mini-revisor de Python — funções complexas, except genérico, print esquecido, default mutável e mais."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("qualidade_codigo", "Mini Python linter: cyclomatic complexity, bare except, leftover print, mutable default args, too many params, missing docstrings, long lines.",
           "analisar | resumo", "pasta = project folder or a .py file. analisar lists the worst findings; resumo counts by type.", "pasta")

DESVIOS = (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler, ast.With, ast.IfExp, ast.comprehension)
PULAR = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "tests"}


def complexidade(func: ast.AST) -> int:
    return 1 + sum(isinstance(n, DESVIOS) for n in ast.walk(func))


def analisar_codigo(src: str) -> list[tuple[int, str, str]]:
    """(linha, tipo, detalhe) de cada achado. Pura."""
    out = [(i, "linha longa", f"{len(l)} caracteres") for i, l in enumerate(src.splitlines(), 1) if len(l) > 130]
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            c = complexidade(n)
            if c > 12:
                out.append((n.lineno, "função complexa", f"{n.name}() complexidade {c}"))
            if len(n.args.args) > 6:
                out.append((n.lineno, "muitos parâmetros", f"{n.name}() tem {len(n.args.args)}"))
            if any(isinstance(d, (ast.List, ast.Dict, ast.Set)) for d in n.args.defaults):
                out.append((n.lineno, "default mutável", f"{n.name}() usa [] ou {{}} como padrão"))
            if not n.name.startswith("_") and not ast.get_docstring(n) and len(n.body) > 8:
                out.append((n.lineno, "sem docstring", f"{n.name}()"))
        elif isinstance(n, ast.ExceptHandler) and n.type is None:
            out.append((n.lineno, "except genérico", "use 'except Exception' ou o erro certo"))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print":
            out.append((n.lineno, "print esquecido", "troque por log se não for de propósito"))
    return sorted(out)


def _go(p, pl):
    alvo = Path(str(p.get("pasta") or ".")).expanduser()
    arqs = [alvo] if alvo.is_file() else [f for f in alvo.rglob("*.py") if not PULAR & set(f.parts)] if alvo.is_dir() else []
    if not arqs:
        return "Não achei arquivos Python aí."
    achados, cont = [], Counter()
    for f in arqs:
        try:
            for linha, tipo, det in analisar_codigo(f.read_text(encoding="utf-8", errors="ignore")):
                cont[tipo] += 1
                if tipo not in ("print esquecido", "linha longa", "sem docstring"):
                    achados.append(f"{f.name}:{linha} {tipo}: {det}")
        except SyntaxError as e:
            achados.append(f"{f.name}:{e.lineno} ERRO DE SINTAXE: {e.msg}")
    resumo = f"{len(arqs)} arquivo(s). " + (", ".join(f"{n} {t}" for t, n in cont.most_common()) or "Nada a apontar") + "."
    return resumo if p["action"] == "resumo" else resumo + ("\n" + "\n".join(achados[:40]) if achados else "")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"analisar": _go, "resumo": _go}, player, "Qualidade")
