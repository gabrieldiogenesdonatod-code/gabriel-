'''
Gerador de projetos (fork PT-BR 1.6).

    "Jarvis, cria um projeto Flask com login chamado loja"
    "Jarvis, cria uma API FastAPI chamada estoque"
    "Jarvis, cria um programa de linha de comando chamado renomeador"
    "Jarvis, cria um app de janela PyQt chamado cronometro"
    "Jarvis, cria um site chamado cristal"
    "Jarvis, cria um projeto de bot de Discord"   (sem modelo pronto: a IA monta)

Monta a estrutura completa (código, testes, requirements, README, .gitignore)
em Documentos\\JARVIS\\projetos\\<nome>, roda os testes e abre no VS Code.
Com "e instala", cria o ambiente virtual (.venv) e instala as dependências.
'''

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from plugins._comum import CNW, WIN, abrir_no_sistema, iniciar, mostrar, pasta_usuario

PLUGIN = {
    "name": "gerador_projetos",
    "brief": "Creates a full project skeleton (Flask with login, FastAPI, CLI, PyQt app, static site, or AI-built).",
    "description": (
        "Project generator: tipo = flask_login | fastapi | cli | pyqt | site, or any description (then AI builds it); "
        "nome = project name; instalar = true to create .venv and install requirements. Creates code, tests, "
        "requirements, README and .gitignore in Documents/JARVIS/projetos/<nome>, runs the tests and opens it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"tipo": {"type": "STRING"}, "nome": {"type": "STRING"}, "instalar": {"type": "BOOLEAN"}},
        "required": ["tipo"],
    },
}

GITIGNORE = "__pycache__/\n*.pyc\n.venv/\nvenv/\n.env\n*.db\n.pytest_cache/\nnode_modules/\n"

MODELOS: dict[str, dict[str, str]] = {
    "flask_login": {
        "app.py": '''"""__NOME__ — Flask com cadastro, login e área restrita (SQLite)."""
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BANCO = Path(__file__).with_name("dados.db")


def criar_app(banco: Path = BANCO) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave")
    app.config["BANCO"] = str(banco)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["BANCO"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, email TEXT UNIQUE, senha TEXT)")
        return g.db

    @app.teardown_appcontext
    def fechar(_erro):
        conexao = g.pop("db", None)
        if conexao is not None:
            conexao.close()

    def login_obrigatorio(view):
        @wraps(view)
        def protegida(*a, **k):
            if "usuario" not in session:
                return redirect(url_for("login"))
            return view(*a, **k)
        return protegida

    @app.route("/")
    def inicio():
        return redirect(url_for("painel" if "usuario" in session else "login"))

    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro():
        if request.method == "POST":
            email, senha = request.form.get("email", "").strip().lower(), request.form.get("senha", "")
            if not email or len(senha) < 6:
                flash("E-mail e senha (mínimo 6 caracteres) são obrigatórios.")
            else:
                try:
                    db().execute("INSERT INTO usuarios (email, senha) VALUES (?, ?)", (email, generate_password_hash(senha)))
                    db().commit()
                    flash("Conta criada. Faça login.")
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    flash("Esse e-mail já tem conta.")
        return render_template("cadastro.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email, senha = request.form.get("email", "").strip().lower(), request.form.get("senha", "")
            u = db().execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
            if u and check_password_hash(u["senha"], senha):
                session.clear()
                session["usuario"] = u["email"]
                return redirect(url_for("painel"))
            flash("E-mail ou senha incorretos.")
        return render_template("login.html")

    @app.route("/painel")
    @login_obrigatorio
    def painel():
        return render_template("painel.html", usuario=session["usuario"])

    @app.route("/sair")
    def sair():
        session.clear()
        return redirect(url_for("login"))

    return app


if __name__ == "__main__":
    criar_app().run(debug=True)
''',
        "templates/base.html": '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__NOME__</title>
<style>body{font-family:system-ui,sans-serif;max-width:420px;margin:60px auto;padding:0 16px}
input,button{display:block;width:100%;padding:10px;margin:8px 0;box-sizing:border-box}.aviso{color:#b45309}</style></head>
<body><h1>__NOME__</h1>{% for m in get_flashed_messages() %}<p class="aviso">{{ m }}</p>{% endfor %}
{% block conteudo %}{% endblock %}</body></html>
''',
        "templates/login.html": '''{% extends "base.html" %}{% block conteudo %}
<form method="post"><input name="email" type="email" placeholder="E-mail" required>
<input name="senha" type="password" placeholder="Senha" required><button>Entrar</button></form>
<a href="{{ url_for('cadastro') }}">Criar conta</a>{% endblock %}
''',
        "templates/cadastro.html": '''{% extends "base.html" %}{% block conteudo %}
<form method="post"><input name="email" type="email" placeholder="E-mail" required>
<input name="senha" type="password" placeholder="Senha (mín. 6)" required><button>Cadastrar</button></form>
<a href="{{ url_for('login') }}">Já tenho conta</a>{% endblock %}
''',
        "templates/painel.html": '''{% extends "base.html" %}{% block conteudo %}
<p>Olá, {{ usuario }}! Esta área só aparece para quem fez login.</p><a href="{{ url_for('sair') }}">Sair</a>{% endblock %}
''',
        "tests/test_app.py": '''import tempfile
import unittest
from pathlib import Path

from app import criar_app


class TestLogin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cliente = criar_app(Path(self.tmp.name) / "t.db").test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_painel_exige_login(self):
        self.assertIn("/login", self.cliente.get("/painel").headers["Location"])

    def test_cadastro_e_login(self):
        self.cliente.post("/cadastro", data={"email": "a@b.com", "senha": "segredo1"})
        r = self.cliente.post("/login", data={"email": "a@b.com", "senha": "segredo1"})
        self.assertIn("/painel", r.headers["Location"])
        self.assertIn("a@b.com", self.cliente.get("/painel").get_data(as_text=True))

    def test_senha_errada(self):
        self.cliente.post("/cadastro", data={"email": "a@b.com", "senha": "segredo1"})
        r = self.cliente.post("/login", data={"email": "a@b.com", "senha": "errada"})
        self.assertIn("incorretos", r.get_data(as_text=True))
''',
        "requirements.txt": "flask>=3,<4\n",
        "README.md": "# __NOME__\n\nFlask com cadastro, login e área restrita (SQLite).\n\n```bash\npython -m venv .venv\n"
                     ".venv\\Scripts\\activate\npython -m pip install -r requirements.txt\npython app.py\n"
                     "python -m unittest discover -s tests\n```\n\nAbra http://127.0.0.1:5000. Em produção, defina a "
                     "variável SECRET_KEY.\n",
    },
    "fastapi": {
        "main.py": '''"""__NOME__ — API FastAPI com CRUD (em memória; troque por um banco depois)."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="__NOME__")
_itens: dict[int, dict] = {}


class Item(BaseModel):
    nome: str
    preco: float = 0.0
    quantidade: int = 0


@app.get("/itens")
def listar():
    return [{"id": i, **v} for i, v in _itens.items()]


@app.post("/itens", status_code=201)
def criar(item: Item):
    novo = max(_itens, default=0) + 1
    _itens[novo] = item.model_dump()
    return {"id": novo, **_itens[novo]}


@app.get("/itens/{item_id}")
def obter(item_id: int):
    if item_id not in _itens:
        raise HTTPException(404, "item não encontrado")
    return {"id": item_id, **_itens[item_id]}


@app.delete("/itens/{item_id}", status_code=204)
def apagar(item_id: int):
    if _itens.pop(item_id, None) is None:
        raise HTTPException(404, "item não encontrado")
''',
        "tests/test_main.py": '''import unittest

from fastapi.testclient import TestClient

from main import app


class TestApi(unittest.TestCase):
    def test_crud(self):
        c = TestClient(app)
        novo = c.post("/itens", json={"nome": "camiseta", "preco": 39.9, "quantidade": 3}).json()
        self.assertEqual(c.get(f"/itens/{novo['id']}").json()["nome"], "camiseta")
        self.assertEqual(c.delete(f"/itens/{novo['id']}").status_code, 204)
        self.assertEqual(c.get(f"/itens/{novo['id']}").status_code, 404)
''',
        "requirements.txt": "fastapi>=0.110,<1\nuvicorn>=0.27,<1\nhttpx>=0.27,<1\n",
        "README.md": "# __NOME__\n\n```bash\npython -m pip install -r requirements.txt\nuvicorn main:app --reload\n```\n\n"
                     "Documentação automática em http://127.0.0.1:8000/docs\n",
    },
    "cli": {
        "__MOD__.py": '''"""__NOME__ — programa de linha de comando."""
import argparse


def processar(texto: str, maiusculas: bool = False) -> str:
    """A lógica fica aqui, separada da linha de comando, para dar para testar."""
    return texto.upper() if maiusculas else texto


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="__NOME__", description="Descreva o que o programa faz.")
    p.add_argument("texto")
    p.add_argument("-m", "--maiusculas", action="store_true")
    a = p.parse_args(argv)
    print(processar(a.texto, a.maiusculas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        "tests/test___MOD__.py": '''import unittest

from __MOD__ import main, processar


class TestCli(unittest.TestCase):
    def test_processar(self):
        self.assertEqual(processar("oi", True), "OI")

    def test_main(self):
        self.assertEqual(main(["oi"]), 0)
''',
        "requirements.txt": "",
        "README.md": "# __NOME__\n\n```bash\npython __MOD__.py \"olá\" --maiusculas\npython -m unittest discover -s tests\n```\n",
    },
    "pyqt": {
        "app.py": '''"""__NOME__ — app de janela com PyQt6."""
import sys

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


class Janela(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("__NOME__")
        self.cliques = 0
        self.rotulo = QLabel("Nenhum clique ainda")
        botao = QPushButton("Clique aqui")
        botao.clicked.connect(self.clicar)
        layout = QVBoxLayout(self)
        layout.addWidget(self.rotulo)
        layout.addWidget(botao)
        self.resize(320, 160)

    def clicar(self):
        self.cliques += 1
        self.rotulo.setText(f"{self.cliques} clique(s)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    j = Janela()
    j.show()
    sys.exit(app.exec())
''',
        "requirements.txt": "PyQt6>=6.6,<7\n",
        "README.md": "# __NOME__\n\n```bash\npython -m pip install -r requirements.txt\npython app.py\n```\n",
    },
    "site": {
        "index.html": '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__NOME__</title>
<link rel="stylesheet" href="style.css"></head><body>
<header><h1>__NOME__</h1><nav><a href="#sobre">Sobre</a><a href="#contato">Contato</a></nav></header>
<main><section id="sobre"><h2>Sobre</h2><p>Escreva aqui.</p></section>
<section id="contato"><h2>Contato</h2><button id="zap">Chamar no WhatsApp</button></section></main>
<script src="script.js"></script></body></html>
''',
        "style.css": ''':root{--cor:#2563eb;--fundo:#fff;--texto:#14202b}
@media (prefers-color-scheme: dark){:root{--fundo:#0b1118;--texto:#e3ebf3}}
body{margin:0;font-family:system-ui,sans-serif;background:var(--fundo);color:var(--texto)}
header{display:flex;justify-content:space-between;align-items:center;padding:16px;gap:12px;flex-wrap:wrap}
nav a{margin-left:12px;color:var(--cor);text-decoration:none} main{max-width:860px;margin:0 auto;padding:0 16px}
button{background:var(--cor);color:#fff;border:0;border-radius:10px;padding:12px 18px;font-size:16px}
''',
        "script.js": '''document.getElementById("zap").addEventListener("click", () => {
  window.open("https://wa.me/55DDDNUMERO?text=" + encodeURIComponent("Olá! Vim pelo site."), "_blank");
});
''',
        "README.md": "# __NOME__\n\nSite estático: abra o index.html. Troque 55DDDNUMERO no script.js pelo seu WhatsApp.\n",
    },
}
APELIDOS = {"flask": "flask_login", "login": "flask_login", "fastapi": "fastapi", "api": "fastapi",
            "linha de comando": "cli", "cli": "cli", "terminal": "cli", "pyqt": "pyqt", "janela": "pyqt",
            "desktop": "pyqt", "site": "site", "pagina": "site", "página": "site", "landing": "site"}


def tipo_de(texto: str) -> str | None:
    t = (texto or "").lower()
    if t in MODELOS:
        return t
    for chave, tipo in APELIDOS.items():
        if chave in t:
            return tipo
    return None


def slug(nome: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:40] or "projeto"


def arquivos_do_modelo(tipo: str, nome: str) -> dict[str, str]:
    mod = slug(nome)
    saida = {k.replace("__MOD__", mod): v.replace("__NOME__", nome).replace("__MOD__", mod)
             for k, v in MODELOS[tipo].items()}
    saida[".gitignore"] = GITIGNORE
    if any(k.startswith("tests/") for k in saida):
        saida["tests/__init__.py"] = ""
    return saida


def arquivos_da_ia(descricao: str, nome: str) -> dict[str, str]:
    from plugins import _ia
    if not _ia.disponivel():
        raise RuntimeError("não tenho modelo pronto para isso e, sem a chave do Gemini, não consigo montar")
    r = _ia.perguntar_json(
        f"Monte um projeto inicial completo e funcional: {descricao}. Nome: {nome}. Inclua README.md em português, "
        "requirements.txt (se for Python), .gitignore e testes em tests/. Código limpo, comentários em português. "
        'Responda SÓ JSON {"arquivos": {"caminho/relativo": "conteúdo"}} com no máximo 15 arquivos.', True, 150)
    arquivos = (r or {}).get("arquivos") if isinstance(r, dict) else None
    if not isinstance(arquivos, dict) or not arquivos:
        raise RuntimeError("a IA não devolveu os arquivos")
    return {str(k): str(v) for k, v in arquivos.items()}


def escrever(raiz: Path, arquivos: dict[str, str]) -> int:
    n = 0
    for rel, conteudo in arquivos.items():
        destino = (raiz / rel).resolve()
        if raiz.resolve() not in destino.parents:              # nada fora da pasta do projeto
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
        n += 1
    return n


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    descricao = str(p.get("tipo") or "").strip()
    nome = str(p.get("nome") or "").strip() or "meu_projeto"
    try:
        raiz = pasta_usuario("Documents") / "JARVIS" / "projetos" / slug(nome)
        if raiz.exists() and any(raiz.iterdir()):
            return f"Já existe um projeto em {raiz}. Escolha outro nome."
        tipo = tipo_de(descricao)
        arquivos = arquivos_do_modelo(tipo, nome) if tipo else arquivos_da_ia(descricao, nome)
        n = escrever(raiz, arquivos)
        extra = ""
        if p.get("instalar") and (raiz / "requirements.txt").exists():
            subprocess.run([sys.executable, "-m", "venv", str(raiz / ".venv")], timeout=180, **CNW)
            py = raiz / ".venv" / ("Scripts/python.exe" if WIN else "bin/python")
            r = subprocess.run([str(py), "-m", "pip", "install", "-r", str(raiz / "requirements.txt")],
                               capture_output=True, timeout=600, **CNW)
            extra = " Ambiente .venv criado e dependências instaladas." if r.returncode == 0 else \
                " Criei o .venv, mas a instalação falhou (veja o requirements)."
            if (raiz / "tests").is_dir():
                t = subprocess.run([str(py), "-m", "unittest", "discover", "-s", "tests"], cwd=str(raiz),
                                   capture_output=True, timeout=300, **CNW)
                extra += " Testes passando." if t.returncode == 0 else " Os testes ainda não passam."
        vscode = shutil.which("code")
        if not (vscode and iniciar([vscode, str(raiz)])):
            abrir_no_sistema(str(raiz))
        mostrar(player, f"PROJETO {nome}", f"{raiz}\n\n" + "\n".join(sorted(arquivos)))
        return (f"Criei o projeto {nome} ({tipo or 'montado pela IA'}) com {n} arquivo(s) em {raiz}.{extra}"
                + ("" if p.get("instalar") else " Se quiser o .venv pronto, peça o próximo projeto com 'e instala'."))
    except Exception as e:
        return f"O gerador de projetos falhou: {e}"
