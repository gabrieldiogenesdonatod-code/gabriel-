"""Checklists (2.18): listas reutilizáveis (abrir a loja, viagem, publicar app) com progresso; reinicia para usar de novo."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, lista, norm, rodar

PLUGIN = P("checklists", "Reusable checklists (open store, trip, deploy): create, check items, what's left, reset, list.",
           "criar | marcar | falta | reiniciar | listar | apagar",
           "criar: nome, itens (comma). marcar: nome, itens (text or number). falta: nome. reiniciar: nome.",
           "nome itens")

C = Colecao("checklists")


def marcar(c: dict, alvo: str) -> list[str]:
    feitos = []
    for x in lista(alvo):
        for i, it in enumerate(c["itens"]):
            if (x.isdigit() and int(x) == i + 1) or norm(x) in norm(it["t"]):
                it["ok"] = True
                feitos.append(it["t"])
                break
    return feitos


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), p.get("nome")
    if a == "criar":
        C.por(nome, {"itens": [{"t": t, "ok": False} for t in lista(p.get("itens"))]})
        return f"Checklist '{nome}' criado."
    if a == "listar":
        return ", ".join(C.nomes()) or "Nenhum checklist."
    c = C.pegar(nome)
    if not c:
        return "Não achei esse checklist."
    if a == "apagar":
        C.tirar(nome)
        return "Apagado."
    if a == "reiniciar":
        for it in c["itens"]:
            it["ok"] = False
    if a == "marcar":
        marcar(c, p.get("itens"))
    C.por(c["nome"], c)
    falta = [f"{i + 1}. {it['t']}" for i, it in enumerate(c["itens"]) if not it["ok"]]
    feito = len(c["itens"]) - len(falta)
    return f"{c['nome']}: {feito}/{len(c['itens'])}." + (" Falta:\n" + "\n".join(falta) if falta else " Tudo feito!")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("criar marcar falta reiniciar listar apagar".split(), _go), player, "Checklist")
