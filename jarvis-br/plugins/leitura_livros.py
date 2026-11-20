"""Livros (2.18): estante, página atual, quantas páginas por dia para terminar na data, e lidos no ano."""
from __future__ import annotations

from datetime import date

from plugins._lote2 import Colecao, P, numeros, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("leitura_livros", "Reading tracker: books, current page, pages/day to finish by a date, finished this year.",
           "adicionar | pagina | meta | estante | terminei | apagar",
           "adicionar: nome, paginas. pagina: nome, valor (current page). meta: nome, data (dd/mm). estante. terminei: nome.",
           "nome paginas valor data")

L = Colecao("livros")


def por_dia(total: int, atual: int, hoje_: date, fim: date) -> int:
    dias = max(1, (fim - hoje_).days)
    return -(-(total - atual) // dias)


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), p.get("nome")
    if a == "adicionar":
        L.por(nome, {"paginas": int((numeros(p.get("paginas")) or [0])[0]), "atual": 0, "fim": None, "lido": None})
        return f"'{nome}' na estante."
    if a == "estante":
        ano = str(date.today().year)
        livros = list(L.tudo().values())
        lidos = sum(1 for b in livros if str(b.get("lido") or "").startswith(ano))
        ativos = [f"{b['nome']}: {b['atual']}/{b['paginas']}" for b in livros if not b.get("lido")]
        return "\n".join(ativos) + f"\nLidos em {ano}: {lidos}." if livros else "Estante vazia."
    b = L.pegar(nome)
    if not b:
        return "Não achei esse livro."
    if a == "apagar":
        L.tirar(nome)
        return "Tirei da estante."
    if a == "terminei":
        b.update(atual=b["paginas"], lido=date.today().isoformat())
    elif a == "pagina":
        b["atual"] = int((numeros(p.get("valor")) or [b["atual"]])[0])
    elif a == "meta":
        b["fim"] = ler_data(p.get("data")).isoformat()
    L.por(b["nome"], b)
    msg = f"{b['nome']}: {b['atual']}/{b['paginas']} ({b['atual'] * 100 // max(1, b['paginas'])}%)."
    if b.get("fim") and not b.get("lido"):
        msg += f" Leia {por_dia(b['paginas'], b['atual'], date.today(), date.fromisoformat(b['fim']))} páginas por dia."
    return msg


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("adicionar pagina meta estante terminei apagar".split(), _go), player, "Livros")
