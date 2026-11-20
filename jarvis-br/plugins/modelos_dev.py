"""Modelos de arquivo (2.18): .gitignore, LICENSE MIT, .editorconfig, Dockerfile e .env.example na pasta do projeto."""
from __future__ import annotations

import time
from pathlib import Path

from plugins._comum import nome_usuario
from plugins._lote2 import P, norm, rodar

PLUGIN = P("modelos_dev", "Project boilerplate files: .gitignore (python/node/unity/arduino), MIT LICENSE, .editorconfig, Dockerfile (python), .env.example.",
           "gitignore | licenca | editorconfig | dockerfile | env | ci | listar",
           "pasta = project folder. gitignore: tipo (python|node|unity|arduino). Never overwrites an existing file.",
           "pasta tipo")

GI = {"python": "__pycache__/\n*.py[cod]\n.venv/\nvenv/\n.env\n*.egg-info/\ndist/\nbuild/\n.pytest_cache/\n.idea/\n.vscode/\n",
      "node": "node_modules/\ndist/\n.env\nnpm-debug.log*\n.next/\ncoverage/\n",
      "unity": "[Ll]ibrary/\n[Tt]emp/\n[Oo]bj/\n[Bb]uild/\n[Ll]ogs/\n[Uu]ser[Ss]ettings/\n*.csproj\n*.sln\n",
      "arduino": ".pio/\nbuild/\n*.bin\n*.elf\n.vscode/\nsecrets.h\n"}
GI_COMUM = "\n# sistema\n.DS_Store\nThumbs.db\n*.log\n"
MIT = """MIT License

Copyright (c) {ano} {nome}

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
EDITOR = "root = true\n\n[*]\ncharset = utf-8\nend_of_line = lf\nindent_style = space\nindent_size = 4\n" \
         "insert_final_newline = true\ntrim_trailing_whitespace = true\n\n[*.{js,ts,json,html,css,yml}]\nindent_size = 2\n"
DOCKER = "FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n" \
         "COPY . .\nCMD [\"python\", \"main.py\"]\n"
CI = """name: testes
on: [push, pull_request]
jobs:
  testes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt pytest
      - run: pytest -q
"""
ENV = "# Copie para .env e preencha. Nunca suba o .env para o GitHub.\nAPI_KEY=\nDEBUG=false\n"


def conteudo(acao: str, tipo: str = "python") -> tuple[str, str]:
    if acao == "gitignore":
        return ".gitignore", GI.get(norm(tipo), GI["python"]) + GI_COMUM
    if acao == "licenca":
        return "LICENSE", MIT.format(ano=time.strftime("%Y"), nome=nome_usuario() or "Autor")
    return {"editorconfig": (".editorconfig", EDITOR), "dockerfile": ("Dockerfile", DOCKER), "env": (".env.example", ENV),
            "ci": (".github/workflows/testes.yml", CI)}[acao]


def _go(p, pl):
    a = str(p.get("action")).lower()
    if a == "listar":
        return "Modelos: gitignore (python, node, unity, arduino), licenca MIT, editorconfig, dockerfile, env, ci (testes no GitHub Actions)."
    pasta = Path(str(p.get("pasta") or ".")).expanduser()
    if not pasta.is_dir():
        return "Pasta não encontrada."
    nome, txt = conteudo(a, str(p.get("tipo") or "python"))
    alvo = pasta / nome
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if alvo.exists():
        return f"{nome} já existe; não sobrescrevi."
    alvo.write_text(txt, encoding="utf-8")
    return f"Criei {alvo}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("gitignore licenca editorconfig dockerfile env ci listar".split(), _go), player)
