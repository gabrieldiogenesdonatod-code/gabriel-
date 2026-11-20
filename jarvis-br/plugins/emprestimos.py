"""Coisas emprestadas (2.18): o que você emprestou (ou pegou), para quem e há quanto tempo."""
from __future__ import annotations

from datetime import date

from plugins._lote2 import Colecao, P, hoje, rodar

PLUGIN = P("emprestimos", "Lent/borrowed things tracker: who has my controller/book/tool, since when; mark returned.",
           "emprestei | peguei | devolvido | lista | com_quem",
           "emprestei/peguei: nome (object), pessoa. devolvido: nome. com_quem: nome or pessoa.",
           "nome pessoa")

E = Colecao("emprestimos")


def _go(p, pl):
    a, nome, pessoa = str(p.get("action")).lower(), p.get("nome"), str(p.get("pessoa") or "")
    if a in ("emprestei", "peguei"):
        E.por(nome, {"pessoa": pessoa, "dir": a, "desde": hoje()})
        return f"Anotado: {nome} {'com ' + pessoa if a == 'emprestei' else 'é de ' + pessoa}."
    if a == "devolvido":
        return "Baixa dada." if E.tirar(nome) else "Não estava anotado."

    def linha(e):
        dias = (date.today() - date.fromisoformat(e["desde"])).days
        return f"{e['nome']} {'com' if e['dir'] == 'emprestei' else 'de'} {e['pessoa']} há {dias} dia(s)"
    tudo = list(E.tudo().values())
    if a == "com_quem":
        q = str(nome or pessoa).lower()
        tudo = [e for e in tudo if q in e["nome"].lower() or q in e["pessoa"].lower()]
    return "\n".join(map(linha, tudo)) or "Nada emprestado."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("emprestei peguei devolvido lista com_quem".split(), _go), player)
