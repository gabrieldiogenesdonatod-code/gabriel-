"""Presentes (2.18): ideias por pessoa, orçamento, o que já deu (para não repetir) e lista de desejos sua."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, hoje, norm, numeros, reais, rodar

PLUGIN = P("presentes", "Gift ideas per person with budget, gifts already given (avoid repeats), and my own wishlist.",
           "ideia | ver | dei | orcamento | desejo | meus_desejos",
           "ideia: pessoa, texto. ver: pessoa. dei: pessoa, texto. orcamento: pessoa, valor. desejo: texto (my wishlist).",
           "pessoa texto valor")

G = Colecao("presentes")


def _go(p, pl):
    a, pessoa, txt = str(p.get("action")).lower(), str(p.get("pessoa") or "eu"), str(p.get("texto") or "")
    if a in ("desejo", "meus_desejos"):
        pessoa = "eu (desejos)"
    g = G.pegar(pessoa) or {"ideias": [], "dados": [], "orc": 0}
    if a in ("ideia", "desejo"):
        g["ideias"].append(txt)
    elif a == "dei":
        g["dados"].append([hoje(), txt])
        g["ideias"] = [i for i in g["ideias"] if norm(i) != norm(txt)]
    elif a == "orcamento":
        g["orc"] = (numeros(p.get("valor")) or [0])[0]
    G.por(pessoa, g)
    if a in ("ver", "meus_desejos"):
        ja = "; ".join(f"{t} ({d[:4]})" for d, t in g["dados"]) or "nada"
        return f"{pessoa}: ideias {', '.join(g['ideias']) or 'nenhuma'}. Já dei: {ja}." + \
            (f" Orçamento {reais(g['orc'])}." if g["orc"] else "")
    return "Anotado."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("ideia ver dei orcamento desejo meus_desejos".split(), _go), player)
