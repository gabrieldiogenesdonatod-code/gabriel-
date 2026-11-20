"""Festa (2.19): lista de convidados com confirmação e a conta de salgados, doces, bolo e bebida para quem vai.

Exemplos: "lista de convidados do aniversário", "a Ana confirmou com dois acompanhantes", "quantos salgados para
40 pessoas", "quem ainda não respondeu o convite", "planejar a festa de criança".
"""
from __future__ import annotations

import math

from plugins._lote2 import P, carregar, guardar, lista, norm, num1, rodar

PLUGIN = P("festa", "Party planner: guest list with RSVP (confirmed/declined/pending, plus-ones) and quantities of snacks, sweets, cake and drinks.",
           "nova | convidar | confirmar | recusar | convidados | quantidades",
           "nova: nome. convidar: nomes (comma). confirmar: nome, acompanhantes. quantidades: pessoas (default: confirmed).",
           "nome nomes acompanhantes pessoas")


def quantidades(pessoas: int) -> dict:
    """Regra de buffet: 12 salgados, 5 doces, 100 g de bolo e 500 ml de bebida por pessoa. Pura."""
    return {"salgados": pessoas * 12, "docinhos": pessoas * 5, "bolo (kg)": math.ceil(pessoas * 0.1 * 10) / 10,
            "refrigerante/suco (L)": math.ceil(pessoas * 0.5), "água (L)": math.ceil(pessoas * 0.2),
            "copos": math.ceil(pessoas * 3), "pratinhos": math.ceil(pessoas * 2)}


def confirmados(f: dict) -> int:
    return sum(1 + c.get("extra", 0) for c in f["convidados"].values() if c["st"] == "sim")


def _go(p, pl):
    a, f = p["action"], carregar("festa", {"nome": "Festa", "convidados": {}})
    if a == "nova":
        f = {"nome": str(p.get("nome") or "Festa"), "convidados": {}}
    elif a == "convidar":
        for n in lista(p.get("nomes") or p.get("nome")):
            f["convidados"].setdefault(norm(n), {"nome": n, "st": "?", "extra": 0})
    elif a in ("confirmar", "recusar"):
        k = norm(p.get("nome"))
        c = f["convidados"].setdefault(k, {"nome": str(p.get("nome")), "st": "?", "extra": 0})
        c["st"], c["extra"] = ("sim", int(num1(p, "acompanhantes"))) if a == "confirmar" else ("não", 0)
    elif a == "quantidades":
        n = int(num1(p, "pessoas")) or confirmados(f)
        if not n:
            return "Ninguém confirmou ainda. Diga para quantas pessoas."
        return f"Para {n} pessoa(s): " + ", ".join(f"{v:g} {k}" for k, v in quantidades(n).items()) + "."
    guardar("festa", f)
    cs = f["convidados"].values()
    pend = [c["nome"] for c in cs if c["st"] == "?"]
    return (f"{f['nome']}: {confirmados(f)} confirmado(s), {sum(c['st'] == 'não' for c in cs)} não vai(ão), "
            f"{len(pend)} sem resposta" + (f" ({', '.join(pend[:12])})." if pend else "."))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("nova convidar confirmar recusar convidados quantidades".split(), _go), player, "Festa")
