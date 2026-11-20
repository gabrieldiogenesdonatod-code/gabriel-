"""Lixeira (2.19): o que você apagou das listas do JARVIS (receitas, metas, snippets, livros…) dá para trazer de volta."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, carregar, guardar, norm, rodar

PLUGIN = P("lixeira", "Trash for items deleted from JARVIS lists (recipes, goals, snippets, pets…): list, restore by name, empty.",
           "listar | restaurar | esvaziar", "restaurar: nome (deleted item).", "nome")


def _go(p, pl):
    a, lixo = p["action"], carregar("_lixeira", [])
    if a == "listar":
        return "\n".join(f"{x['item'].get('nome', '?')} ({x['colecao']}, {x['quando']})" for x in lixo[-30:]) or "Lixeira vazia."
    if a == "esvaziar":
        guardar("_lixeira", [])
        return f"Lixeira esvaziada ({len(lixo)} item(ns))."
    q = norm(p.get("nome"))
    for i in range(len(lixo) - 1, -1, -1):
        item = lixo[i]["item"]
        if q and q in norm(item.get("nome")):
            Colecao(lixo[i]["colecao"]).por(item["nome"], item)
            del lixo[i]
            guardar("_lixeira", lixo)
            return f"'{item['nome']}' voltou para a lista."
    return "Não achei isso na lixeira."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("listar restaurar esvaziar".split(), _go), player, "Lixeira")
