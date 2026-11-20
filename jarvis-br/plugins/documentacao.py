"""
Documentação automática (fork PT-BR 1.6).

    "Jarvis, documenta o projeto C:\\projetos\\loja"
        → README_GERADO.md: o que é, como rodar, estrutura, módulos, classes e
          funções (com a assinatura e a 1ª linha da docstring). Com IA, um
          resumo de verdade no começo.
    "Jarvis, escreve as docstrings do calculos.py"
        → escreve docstrings em português nas funções que não têm. Mostra
          antes, aplica só com CONFIRMAR, guarda cópia (.bak) e dá para desfazer.
"""

from __future__ import annotations

import ast
import shutil
import time
from pathlib import Path

from plugins._comum import confirmar, desfazer, mostrar

PLUGIN = {
    "name": "documentacao",
    "brief": "Auto documentation: README from code structure; Portuguese docstrings for functions without them.",
    "description": (
        "Automatic documentation. action='readme' with alvo = project folder (writes README_GERADO.md with "
        "overview, how to run, structure, modules, classes and functions); action='docstrings' with alvo = .py file "
        "(writes missing docstrings in Portuguese; shows a preview and applies only after on-screen confirmation, "
        "with backup and undo)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "readme | docstrings"}, "alvo": {"type": "STRING"}},
        "required": ["alvo"],
    },
}


def readme(pasta: Path, resumo_ia: str = "") -> str:
    """O texto do README a partir do código (pura, a não ser pela leitura dos arquivos)."""
    from plugins._analise_codigo import classes, estrutura, funcoes, resumo_texto
    e = estrutura(pasta)
    partes = [f"# {pasta.name}", "", "> Gerado pelo J.A.R.V.I.S BR a partir do código. Revise antes de publicar.", ""]
    if resumo_ia:
        partes += ["## Visão geral", "", resumo_ia.strip(), ""]
    partes += ["## Estrutura", "", resumo_texto(e), ""]
    if (pasta / "requirements.txt").exists():
        partes += ["## Como rodar", "", "```bash", "python -m pip install -r requirements.txt"]
        partes += [f"python {x}" for x in e["entradas"] if x.endswith(".py") and x in ("main.py", "app.py", "server.py")]
        partes += ["```", ""]
    elif (pasta / "package.json").exists():
        partes += ["## Como rodar", "", "```bash", "npm install", "npm start", "```", ""]
    modulos = sorted(p for p in pasta.rglob("*.py") if not any(x in p.parts for x in ("venv", ".venv", "node_modules",
                                                                                    "__pycache__", "build", "dist")))
    if modulos:
        partes += ["## Módulos", ""]
    for m in modulos[:80]:
        try:
            codigo = m.read_text(encoding="utf-8", errors="replace")
            doc = (ast.get_docstring(ast.parse(codigo)) or "").strip().splitlines()
            fs = [f for f in funcoes(codigo) if f["publica"] and not f["classe"]]
            cs = classes(codigo)
        except SyntaxError:
            continue
        partes += [f"### `{m.relative_to(pasta).as_posix()}`", ""] + ([doc[0], ""] if doc else [])
        for c in cs:
            partes.append(f"- **classe `{c['nome']}`**" + (f" — {c['doc'].splitlines()[0]}" if c["doc"] else ""))
        for f in fs:
            partes.append(f"- `{f['nome']}({', '.join(f['args'])})`" + (f" — {f['doc'].splitlines()[0]}" if f["doc"] else ""))
        partes.append("")
    return "\n".join(partes)


def docstrings(arquivo: Path, player=None) -> str:
    from plugins import _ia
    from plugins._analise_codigo import funcoes, inserir_docstrings
    codigo = arquivo.read_text(encoding="utf-8")
    sem = [f for f in funcoes(codigo) if not f["doc"]]
    if not sem:
        return f"Todas as funções de {arquivo.name} já têm docstring."
    if not _ia.disponivel():
        return f"{len(sem)} função(ões) sem docstring em {arquivo.name}: " + ", ".join(f["qual"] for f in sem[:15]) + \
            ". Para eu escrever as docstrings, preciso da chave do Gemini."
    docs = _ia.perguntar_json(
        "Escreva docstrings curtas em português do Brasil (1 a 3 linhas: o que faz, parâmetros importantes e o que "
        "devolve) para estas funções: " + ", ".join(f["qual"] for f in sem) +
        '. Responda SÓ JSON {"nome_qualificado": "docstring"}.\n\n```python\n' + codigo[:30000] + "\n```", True, 120)
    if not isinstance(docs, dict) or not docs:
        return "Não consegui as docstrings agora."
    novo = inserir_docstrings(codigo, {str(k): str(v) for k, v in docs.items()})
    n = len(sem) - len([f for f in funcoes(novo) if not f["doc"]])
    import difflib
    diff = "".join(difflib.unified_diff(codigo.splitlines(True), novo.splitlines(True), "antes", "depois", n=1))
    mostrar(player, f"DOCSTRINGS — {arquivo.name}", diff[:8000])

    def aplicar() -> str:
        if arquivo.read_text(encoding="utf-8") != codigo:
            return "O arquivo mudou enquanto isso; peça de novo."
        copia = arquivo.with_name(arquivo.name + time.strftime(".bak-%Y%m%d-%H%M%S"))
        shutil.copy2(arquivo, copia)
        arquivo.write_text(novo, encoding="utf-8")
        desfazer(f"docstrings em {arquivo.name}", lambda: (shutil.copy2(copia, arquivo), "Voltei o arquivo.")[1])
        return f"Pus {n} docstring(s) em {arquivo.name} (cópia em {copia.name})."
    return confirmar(f"documentacao:{arquivo}", f"Pôr {n} docstring(s) em {arquivo.name}?", diff[:1500], aplicar)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    alvo = Path(str(p.get("alvo") or "").strip().strip('"')).expanduser()
    acao = str(p.get("action") or ("docstrings" if alvo.suffix == ".py" else "readme")).lower()
    try:
        if acao == "docstrings":
            if alvo.suffix != ".py" or not alvo.is_file():
                return f"Não achei o arquivo Python {alvo}."
            return docstrings(alvo, player)
        if not alvo.is_dir():
            return f"Não achei a pasta {alvo}."
        from plugins import _ia
        resumo = ""
        if _ia.disponivel():
            from plugins._analise_codigo import estrutura, resumo_texto
            e = estrutura(alvo)
            resumo = _ia.perguntar(f"Escreva 1 parágrafo (português do Brasil) dizendo o que é este projeto e para quem. "
                                   f"Estrutura: {resumo_texto(e)}\nREADME atual: {e['readme'][:2000]}", False, 60) or ""
        texto = readme(alvo, resumo)
        destino = alvo / "README_GERADO.md"
        destino.write_text(texto, encoding="utf-8")
        mostrar(player, "README GERADO", texto[:8000])
        return f"Escrevi {destino} ({texto.count(chr(10))} linhas). Revise e renomeie para README.md se gostar."
    except Exception as e:
        return f"A documentação falhou: {e}"
