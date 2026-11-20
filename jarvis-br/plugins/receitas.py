"""Receitas (2.18): guardar, ajustar porções, buscar pelo que tem em casa e mandar ingredientes para a lista de compras."""
from __future__ import annotations

import re

from plugins._lote2 import Colecao, P, lista, norm, numeros, rodar

PLUGIN = P("receitas", "Recipe box: save, read, scale portions, find by ingredients you have, send missing items to shopping list.",
           "salvar | ver | porcoes | tenho | listar | apagar | para_lista",
           "salvar: nome, ingredientes (comma list with amounts), preparo, porcoes. porcoes: nome, porcoes (new). "
           "tenho: ingredientes I have -> best recipes. para_lista: nome -> shopping list.",
           "nome ingredientes preparo porcoes")

R = Colecao("receitas")


def escalar(ing: list[str], fator: float) -> list[str]:
    def troca(m):
        v = float(m.group(0).replace(",", ".")) * fator
        return f"{v:g}".replace(".", ",")
    return [re.sub(r"\d+(?:[.,]\d+)?", troca, i, count=1) for i in ing]


def palavra_chave(ing: str) -> str:
    w = [x for x in re.findall(r"[a-zà-ú]+", ing.lower()) if x not in
         "de da do g kg ml l xicara xicaras colher colheres sopa cha cha pitada a gosto litro gramas unidade unidades".split()]
    return norm(w[-1] if w else ing)


def combina(tenho: list[str], receitas: list[dict]) -> list[tuple[float, str, list[str]]]:
    t = {norm(x) for x in tenho}
    out = []
    for r in receitas:
        chaves = [palavra_chave(i) for i in r.get("ingredientes", [])]
        falta = [c for c in chaves if not any(c in x or x in c for x in t)]
        if chaves:
            out.append((1 - len(falta) / len(chaves), r["nome"], falta))
    return sorted(out, reverse=True)


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), p.get("nome")
    if a == "salvar":
        R.por(nome, {"ingredientes": lista(p.get("ingredientes")), "preparo": p.get("preparo") or "",
                     "porcoes": (numeros(p.get("porcoes")) or [4])[0]})
        return f"Receita '{nome}' guardada."
    if a == "listar":
        return ", ".join(R.nomes()) or "Nenhuma receita salva."
    if a == "tenho":
        top = combina(lista(p.get("ingredientes")), list(R.tudo().values()))[:3]
        return "\n".join(f"{n}: {int(s*100)}% — falta {', '.join(f) or 'nada'}" for s, n, f in top) or "Nenhuma receita salva."
    r = R.pegar(nome)
    if not r:
        return "Não achei essa receita."
    if a == "apagar":
        R.tirar(nome)
        return "Apagada."
    if a == "para_lista":
        from core import registro_ferramentas
        return registro_ferramentas.executar("lista_compras", {"action": "adicionar", "itens": ", ".join(
            palavra_chave(i) for i in r["ingredientes"])}, pl)
    ing = r["ingredientes"]
    if a == "porcoes":
        novo = (numeros(p.get("porcoes")) or [r["porcoes"]])[0]
        ing = escalar(ing, novo / (r["porcoes"] or 1))
    return f"{r['nome']}:\n- " + "\n- ".join(ing) + f"\n\n{r.get('preparo', '')}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("salvar ver porcoes tenho listar apagar para_lista".split(), _go), player, "Receita")
