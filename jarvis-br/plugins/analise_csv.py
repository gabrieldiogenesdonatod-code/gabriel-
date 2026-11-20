"""Análise de CSV (2.19): pergunte a uma planilha CSV — colunas, soma e média, valores mais comuns, soma por grupo e filtro."""
from __future__ import annotations

from collections import Counter

from plugins._lote2 import P, norm, num1, reais, rodar
from plugins.conversor_dados import _ler, csv_para_lista

PLUGIN = P("analise_csv", "Ask a CSV file questions: columns and types, sum/mean/min/max of a column, most common values, sum grouped by another column, filter rows.",
           "colunas | estatisticas | top | somar_por | filtrar",
           "arquivo = CSV path or text. estatisticas/top: coluna. somar_por: coluna (numeric), por (group column). filtrar: coluna, valor.",
           "arquivo coluna por valor quantidade")


def numero_br(s) -> float | None:
    """'1.234,56' / 'R$ 20,00' / '15.5' → float; texto → None. Pura."""
    t = str(s or "").replace("R$", "").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def coluna(linhas: list[dict], nome: str) -> str | None:
    cols = list(linhas[0]) if linhas else []
    q = norm(nome)
    return next((c for c in cols if norm(c) == q), None) or next((c for c in cols if q and q in norm(c)), None)


def somar_por(linhas: list[dict], col: str, por: str) -> list[tuple[str, float]]:
    tot: dict = {}
    for l in linhas:
        v = numero_br(l.get(col))
        if v is not None:
            tot[l.get(por, "")] = tot.get(l.get(por, ""), 0) + v
    return sorted(tot.items(), key=lambda kv: -kv[1])


def _go(p, pl):
    a, linhas = p["action"], csv_para_lista(_ler(str(p.get("arquivo") or ""))[0])
    if not linhas:
        return "O CSV está vazio."
    if a == "colunas":
        def tipo(c):
            return "número" if sum(numero_br(l[c]) is not None for l in linhas[:50]) > len(linhas[:50]) * .8 else "texto"
        return f"{len(linhas)} linha(s). " + "; ".join(f"{c} ({tipo(c)}, ex.: {linhas[0][c]})" for c in linhas[0])
    c = coluna(linhas, p.get("coluna"))
    if not c:
        return "Não achei essa coluna. Tenho: " + ", ".join(linhas[0]) + "."
    if a == "estatisticas":
        v = [x for x in (numero_br(l[c]) for l in linhas) if x is not None]
        if not v:
            return f"A coluna {c} não tem números."
        return f"{c}: {len(v)} valores, soma {reais(sum(v))[3:]}, média {sum(v) / len(v):.2f}, mínimo {min(v):g}, máximo {max(v):g}."
    if a == "top":
        return "; ".join(f"{k or '(vazio)'}: {n}" for k, n in Counter(l[c] for l in linhas).most_common(int(num1(p, "quantidade", 8))))
    if a == "somar_por":
        g = coluna(linhas, p.get("por"))
        if not g:
            return "Agrupar por qual coluna?"
        return "\n".join(f"{k or '(vazio)'}: {reais(v)[3:]}" for k, v in somar_por(linhas, c, g)[:20])
    q = norm(p.get("valor"))
    achou = [l for l in linhas if q in norm(l[c])]
    return f"{len(achou)} linha(s) com '{p.get('valor')}' em {c}.\n" + "\n".join(" | ".join(map(str, l.values())) for l in achou[:5])


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("colunas estatisticas top somar_por filtrar".split(), _go), player, "CSV")
