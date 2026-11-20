"""
Análise de código sem IA (fork PT-BR 1.6). Começa com "_": não é ferramenta.

Usado pelo "explica esse repositório", pelo gerador de testes e pela
documentação automática. Tudo aqui é puro (está nos testes).
"""

from __future__ import annotations

import ast
import os
import re
from collections import Counter
from pathlib import Path

from plugins._projetos import EXT_LINGUAGEM, PULAR

ENTRADAS = ("main.py", "app.py", "manage.py", "server.py", "index.js", "server.js", "main.go", "Program.cs",
            "index.html", "setup.py", "pyproject.toml", "package.json", "Dockerfile", "docker-compose.yml",
            "requirements.txt", "Makefile", "Cargo.toml", "go.mod", "pom.xml", "build.gradle")


def estrutura(pasta: Path, max_arquivos: int = 5000) -> dict:
    pasta = Path(pasta)
    linguagens, linhas, arquivos, topo = Counter(), Counter(), 0, Counter()
    entradas, maiores = [], []
    for raiz, dirs, nomes in os.walk(pasta):
        dirs[:] = sorted(d for d in dirs if d not in PULAR and not d.startswith("."))
        rel = Path(raiz).relative_to(pasta)
        for n in nomes:
            arquivos += 1
            if arquivos > max_arquivos:
                break
            p = Path(raiz) / n
            if n in ENTRADAS and len(rel.parts) <= 1:
                entradas.append(str(rel / n).replace("\\", "/"))
            lang = EXT_LINGUAGEM.get(p.suffix.lower())
            if lang and lang not in ("JSON", "Markdown"):
                try:
                    with p.open(encoding="utf-8", errors="ignore") as f:
                        qtd = sum(1 for _ in f)
                except OSError:
                    qtd = 0
                linguagens[lang] += 1
                linhas[lang] += qtd
                topo[rel.parts[0] if rel.parts else "(raiz)"] += qtd
                maiores.append((qtd, str(rel / n).replace("\\", "/")))
    readme = next((p for p in pasta.iterdir() if p.name.lower().startswith("readme")), None) if pasta.is_dir() else None
    return {"arquivos": arquivos, "linguagens": dict(linguagens.most_common()), "linhas": dict(linhas.most_common()),
            "pastas": dict(topo.most_common(12)), "entradas": entradas, "maiores": [m for _q, m in sorted(maiores)[::-1][:10]],
            "readme": readme.read_text(encoding="utf-8", errors="replace")[:3000] if readme else ""}


def funcoes(codigo: str) -> list[dict]:
    """Funções e métodos de um arquivo Python: nome, classe, argumentos, linha, docstring."""
    arvore = ast.parse(codigo)
    saida = []

    def visitar(nos, classe=""):
        for n in nos:
            if isinstance(n, ast.ClassDef):
                visitar(n.body, n.name)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in n.args.args if a.arg not in ("self", "cls")]
                saida.append({"nome": n.name, "classe": classe, "qual": f"{classe}.{n.name}" if classe else n.name,
                              "args": args, "linha": n.lineno, "doc": ast.get_docstring(n) or "",
                              "publica": not n.name.startswith("_"), "assincrona": isinstance(n, ast.AsyncFunctionDef),
                              "corpo_linha": n.body[0].lineno, "coluna": n.body[0].col_offset})
    visitar(arvore.body)
    return saida


def classes(codigo: str) -> list[dict]:
    return [{"nome": n.name, "doc": ast.get_docstring(n) or "", "linha": n.lineno}
            for n in ast.parse(codigo).body if isinstance(n, ast.ClassDef)]


def inserir_docstrings(codigo: str, docs: dict[str, str]) -> str:
    """Põe docstrings nas funções que ainda não têm ({'Classe.metodo' | 'funcao': texto})."""
    linhas = codigo.splitlines(keepends=True)
    inserir = []
    for f in funcoes(codigo):
        texto = (docs.get(f["qual"]) or "").strip()
        if not texto or f["doc"] or f["corpo_linha"] == f["linha"] and _mesma_linha(linhas, f):
            continue
        recuo = " " * f["coluna"]
        texto = texto.replace('"""', "'''")
        bloco = f'{recuo}"""{texto}"""\n' if "\n" not in texto else \
            f'{recuo}"""' + texto.replace("\n", "\n" + recuo) + f'\n{recuo}"""\n'
        inserir.append((f["corpo_linha"] - 1, bloco))
    for idx, bloco in sorted(inserir, reverse=True):
        linhas.insert(idx, bloco)
    novo = "".join(linhas)
    ast.parse(novo)                                           # nunca devolve código quebrado
    return novo


def _mesma_linha(linhas: list[str], f: dict) -> bool:
    """def f(): return 1  (corpo na mesma linha do def): não dá para pôr docstring sem reescrever."""
    return bool(re.match(r"\s*(async\s+)?def\s", linhas[f["linha"] - 1])) and f["corpo_linha"] == f["linha"]


def resumo_texto(e: dict) -> str:
    langs = ", ".join(f"{k} ({e['linhas'].get(k, 0)} linhas)" for k in list(e["linguagens"])[:4])
    return (f"{e['arquivos']} arquivos; linguagens: {langs or 'nenhuma reconhecida'}. Pastas com mais código: "
            + ", ".join(f"{k} ({v})" for k, v in list(e["pastas"].items())[:6])
            + (f". Pontos de entrada/configuração: {', '.join(e['entradas'][:8])}" if e["entradas"] else "") + ".")
