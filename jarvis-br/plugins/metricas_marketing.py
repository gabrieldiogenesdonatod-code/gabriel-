"""Métricas de marketing (2.19): engajamento, ROAS e ponto de equilíbrio do anúncio, CAC, conversão, ticket médio, CPM e CPC.

Exemplos: "quanto o anúncio do Instagram rendeu", "o impulsionamento valeu a pena", "taxa de engajamento do post",
"quanto custou cada cliente novo", "ticket médio da loja".
"""
from __future__ import annotations

from plugins._lote2 import P, num1, reais, rodar

PLUGIN = P("metricas_marketing", "Marketing math: engagement rate, ROAS and break-even ROAS, CAC, conversion rate, average ticket, CPM/CPC/CTR.",
           "engajamento | roas | cac | conversao | ticket_medio | anuncio",
           "engajamento: interacoes (likes+comments+shares+saves), seguidores. roas: receita, gasto, margem (%). cac: gasto, clientes. "
           "conversao: vendas, visitas. ticket_medio: receita, vendas. anuncio: gasto, impressoes, cliques.",
           "interacoes seguidores receita gasto margem clientes vendas visitas impressoes cliques")


def engajamento(interacoes, seguidores) -> float:
    return interacoes / seguidores * 100


def roas_equilibrio(margem_pct) -> float:
    """ROAS mínimo para o anúncio se pagar: 1 / margem."""
    return 100 / margem_pct


def _go(p, pl):
    a = p["action"]
    x = lambda k, d=0.0: num1(p, k, d)  # noqa: E731
    if a == "engajamento":
        e = engajamento(x("interacoes"), x("seguidores", 1))
        nivel = "ótimo" if e >= 6 else "bom" if e >= 3 else "na média" if e >= 1 else "baixo"
        return f"Engajamento de {e:.2f}% ({nivel})."
    if a == "roas":
        r = x("receita") / x("gasto", 1)
        msg = f"ROAS {r:.2f}: cada real em anúncio trouxe {reais(r)}."
        if x("margem"):
            eq = roas_equilibrio(x("margem"))
            msg += f" Com margem de {x('margem'):g}% o mínimo para empatar é {eq:.2f}: " + ("deu lucro." if r > eq else "deu prejuízo.")
        return msg
    if a == "cac":
        return f"Cada cliente novo custou {reais(x('gasto') / x('clientes', 1))}."
    if a == "conversao":
        return f"Conversão de {x('vendas') / x('visitas', 1) * 100:.2f}%: 1 venda a cada {x('visitas', 1) / max(1, x('vendas')):.0f} visitas."
    if a == "ticket_medio":
        return f"Ticket médio de {reais(x('receita') / x('vendas', 1))}."
    imp, cli, g = x("impressoes", 1), x("cliques", 1), x("gasto")
    return f"CPM {reais(g / imp * 1000)}, CPC {reais(g / cli)}, CTR {cli / imp * 100:.2f}%."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("engajamento roas cac conversao ticket_medio anuncio".split(), _go), player)
