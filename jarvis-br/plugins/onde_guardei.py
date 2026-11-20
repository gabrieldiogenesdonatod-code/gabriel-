"""Onde guardei (2.19): você diz onde guardou cada coisa da casa e depois pergunta — "onde está o passaporte?"."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, hoje, norm, rodar

PLUGIN = P("onde_guardei", "Remember where things are stored at home: 'guardei o passaporte na gaveta do escritório', then 'onde está o passaporte?'; list by place.",
           "guardar | onde | no_lugar | listar | apagar",
           "guardar: objeto, lugar. onde: objeto. no_lugar: lugar -> everything stored there.",
           "objeto lugar")

O = Colecao("onde_guardei")


def _go(p, pl):
    a, obj, lugar = p["action"], p.get("objeto"), str(p.get("lugar") or "").strip()
    if a == "guardar":
        if not obj or not lugar:
            return "Diga o objeto e o lugar."
        O.por(obj, {"lugar": lugar, "desde": hoje()})
        return f"Anotado: {obj} está em {lugar}."
    if a == "listar":
        return "\n".join(f"{x['nome']}: {x['lugar']}" for x in O.tudo().values()) or "Nada anotado ainda."
    if a == "no_lugar":
        q = norm(lugar or obj)
        achei = [x["nome"] for x in O.tudo().values() if q and q in norm(x["lugar"])]
        return f"Em {lugar or obj}: {', '.join(achei)}." if achei else "Não anotei nada nesse lugar."
    x = O.pegar(obj)
    if not x:
        return f"Não anotei onde está {obj}."
    if a == "apagar":
        O.tirar(obj)
        return "Apagado."
    return f"{x['nome']} está em {x['lugar']} (anotado em {x['desde'][8:]}/{x['desde'][5:7]})."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("guardar onde no_lugar listar apagar".split(), _go), player, "Onde guardei")
