"""
Currículo e portfólio automáticos (fork PT-BR 1.6).

A partir dos seus repositórios PÚBLICOS do GitHub, monta:
    • um portfólio (página HTML bonita, pronta para publicar no GitHub Pages);
    • um currículo (HTML para imprimir/salvar em PDF), com as linguagens que
      você mais usa e os projetos em destaque.
Com a chave do Gemini, ele melhora as descrições dos projetos e escreve o
"sobre mim". Seus dados (nome, cidade, contato, formação) vêm do que você
disser — nada é inventado.

    "Jarvis, gera meu portfólio do GitHub usuario123"
    "Jarvis, faz meu currículo: sou programador em Goiânia, email tal, curso tal"
"""

from __future__ import annotations

import html
from collections import Counter
from datetime import datetime

from plugins._comum import MEMORIA, abrir_no_sistema, gravar_json, ler_json, pasta_usuario

PLUGIN = {
    "name": "portfolio",
    "brief": "Builds a portfolio page and a résumé (HTML) from the user's public GitHub repositories.",
    "description": (
        "Résumé and portfolio from public GitHub repos: usuario = GitHub username (remembered); optional dados = what "
        "the user said about themselves (name, city, contact, education, experience — never invent); action = "
        "'portfolio' | 'curriculo' | 'ambos' (default)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}, "usuario": {"type": "STRING"}, "dados": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "portfolio.json"


def repos_github(usuario: str) -> tuple[dict, list[dict]]:
    import requests
    h = {"Accept": "application/vnd.github+json"}
    perfil = requests.get(f"https://api.github.com/users/{usuario}", headers=h, timeout=20)
    if perfil.status_code == 404:
        raise RuntimeError(f"o usuário {usuario} não existe no GitHub")
    perfil.raise_for_status()
    r = requests.get(f"https://api.github.com/users/{usuario}/repos?per_page=100&sort=updated", headers=h, timeout=30)
    r.raise_for_status()
    return perfil.json(), [x for x in r.json() if not x.get("fork")]


def destaques(repos: list[dict], n: int = 8) -> list[dict]:
    """Os projetos que mais mostram você: estrelas, descrição, atividade (pura)."""
    def peso(x):
        return (x.get("stargazers_count", 0) * 3 + x.get("forks_count", 0) * 2 + (2 if x.get("description") else 0)
                + (1 if x.get("homepage") else 0))
    return sorted(repos, key=lambda x: (peso(x), x.get("pushed_at") or ""), reverse=True)[:n]


def linguagens(repos: list[dict]) -> list[tuple[str, int]]:
    return Counter(x["language"] for x in repos if x.get("language")).most_common(8)


def _cartao(x: dict, descricao: str) -> str:
    e = html.escape
    link = f"<a href='{e(x['html_url'])}'>código</a>" + (f" · <a href='{e(x['homepage'])}'>ver online</a>"
                                                        if x.get("homepage") else "")
    return (f"<article><h3>{e(x['name'])}</h3><p>{e(descricao or 'Sem descrição.')}</p><div class='meta'>"
            f"{e(x.get('language') or '')} · ★ {x.get('stargazers_count', 0)} · {link}</div></article>")


_CSS = """:root{--bg:#f7f8fb;--card:#fff;--txt:#14202b;--mudo:#5d6b78;--cor:#2563eb}
@media (prefers-color-scheme: dark){:root{--bg:#0b1118;--card:#121b25;--txt:#e3ebf3;--mudo:#8796a5;--cor:#5aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:Segoe UI,system-ui,sans-serif;line-height:1.5}
main{max-width:920px;margin:0 auto;padding:32px 16px}header{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
header img{width:96px;height:96px;border-radius:50%}h1{margin:0}a{color:var(--cor)}.mudo{color:var(--mudo)}
.grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-top:18px}
article{background:var(--card);border-radius:14px;padding:16px}article h3{margin:0 0 6px}.meta{font-size:13px;color:var(--mudo)}
.tags span{display:inline-block;background:var(--card);border-radius:20px;padding:4px 12px;margin:4px 6px 0 0;font-size:13px}
@media print{body{background:#fff;color:#000}article{break-inside:avoid;border:1px solid #ddd}}"""


def pagina_portfolio(perfil: dict, repos: list[dict], sobre: str, descricoes: dict) -> str:
    e = html.escape
    tags = "".join(f"<span>{e(l)} ({n})</span>" for l, n in linguagens(repos))
    cartoes = "".join(_cartao(x, descricoes.get(x["name"]) or x.get("description") or "") for x in destaques(repos))
    nome = perfil.get("name") or perfil.get("login")
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
            f"initial-scale=1'><title>{e(nome)} — Portfólio</title><style>{_CSS}</style></head><body><main><header>"
            f"<img src='{e(perfil.get('avatar_url', ''))}' alt=''><div><h1>{e(nome)}</h1><div class='mudo'>"
            f"{e(perfil.get('bio') or '')} {e(perfil.get('location') or '')}</div><a href='{e(perfil.get('html_url', ''))}'>"
            f"github.com/{e(perfil.get('login', ''))}</a></div></header>"
            + (f"<h2>Sobre mim</h2><p>{e(sobre)}</p>" if sobre else "")
            + f"<h2>Tecnologias</h2><div class='tags'>{tags}</div><h2>Projetos</h2><div class='grade'>{cartoes}</div>"
            f"<p class='mudo'>Atualizado em {datetime.now():%d/%m/%Y}.</p></main></body></html>")


def pagina_curriculo(perfil: dict, repos: list[dict], dados: str, sobre: str, descricoes: dict) -> str:
    e = html.escape
    nome = perfil.get("name") or perfil.get("login")
    projetos = "".join(f"<li><b>{e(x['name'])}</b> ({e(x.get('language') or '—')}): "
                       f"{e(descricoes.get(x['name']) or x.get('description') or '')} — {e(x['html_url'])}</li>"
                       for x in destaques(repos, 5))
    dados_html = "".join(f"<p>{e(l)}</p>" for l in dados.splitlines() if l.strip())
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Currículo — {e(nome)}</title>"
            f"<style>{_CSS} main{{max-width:760px}} li{{margin:6px 0}}</style></head><body><main><h1>{e(nome)}</h1>"
            f"<div class='mudo'>{e(perfil.get('location') or '')} · github.com/{e(perfil.get('login', ''))}</div>"
            + (f"<h2>Resumo</h2><p>{e(sobre)}</p>" if sobre else "") + (f"<h2>Dados</h2>{dados_html}" if dados_html else "")
            + "<h2>Tecnologias</h2><p>" + ", ".join(e(l) for l, _n in linguagens(repos)) + "</p>"
            + f"<h2>Projetos</h2><ul>{projetos}</ul><p class='mudo'>Para PDF: Ctrl+P → Salvar como PDF.</p></main></body></html>")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "ambos").lower()
    try:
        guardado = ler_json(_ARQ, {}) or {}
        usuario = str(p.get("usuario") or guardado.get("usuario") or "").strip().lstrip("@")
        if not usuario:
            return "Qual é o seu usuário do GitHub?"
        dados = str(p.get("dados") or guardado.get("dados") or "")
        gravar_json(_ARQ, {"usuario": usuario, "dados": dados})
        perfil, repos = repos_github(usuario)
        if not repos:
            return f"O {usuario} não tem repositórios públicos (sem contar forks)."
        sobre, descricoes = "", {}
        from plugins import _ia
        if _ia.disponivel():
            r = _ia.perguntar_json(
                "Melhore as descrições destes projetos do GitHub (1 frase clara cada, sem inventar funções que não estão "
                "no nome/descrição) e escreva um 'sobre mim' de 2 frases usando SÓ estes dados: " + (dados or "(nenhum)")
                + ". Projetos: " + "; ".join(f"{x['name']}: {x.get('description') or ''} ({x.get('language') or ''})"
                                             for x in destaques(repos)) +
                '. Responda SÓ JSON {"sobre": "...", "descricoes": {"nome_do_repo": "..."}} em português do Brasil.', True, 60)
            if isinstance(r, dict):
                sobre, descricoes = str(r.get("sobre") or ""), dict(r.get("descricoes") or {})
        pasta = pasta_usuario("Documents") / "JARVIS" / "portfolio"
        pasta.mkdir(parents=True, exist_ok=True)
        feitos = []
        if acao in ("portfolio", "ambos"):
            (pasta / "index.html").write_text(pagina_portfolio(perfil, repos, sobre, descricoes), encoding="utf-8")
            feitos.append("portfólio (index.html)")
        if acao in ("curriculo", "currículo", "ambos"):
            (pasta / "curriculo.html").write_text(pagina_curriculo(perfil, repos, dados, sobre, descricoes), encoding="utf-8")
            feitos.append("currículo (curriculo.html)")
        abrir_no_sistema(str(pasta / ("index.html" if "portfólio (index.html)" in feitos else "curriculo.html")))
        return (f"Pronto: {' e '.join(feitos)} em {pasta}, com {len(destaques(repos))} projetos em destaque. Para publicar "
                "o portfólio, crie o repositório usuario.github.io e suba o index.html."
                + ("" if dados else " Me diga seus dados (cidade, contato, formação) para o currículo ficar completo."))
    except Exception as e:
        return f"O portfólio falhou: {e}"
