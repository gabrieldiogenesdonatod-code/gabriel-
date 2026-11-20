"""
E se… (3.0): o seu universo paralelo em números. O JARVIS calcula o que teria acontecido se você
tivesse feito diferente, usando os SEUS dados quando existem.

    "E se eu tivesse guardado 50 reais por semana desde janeiro?"
    "E se eu tivesse cancelado as assinaturas que não uso há 6 meses?"
    "E se eu não tivesse gasto com delivery desde março?"            (usa os seus gastos anotados)
    "E se eu tivesse corrido 10 km por semana desde julho?"
    "E se a loja tivesse vendido 100 reais a mais por dia desde agosto?"
"""

from __future__ import annotations

import re
from datetime import date

from plugins._lote2 import P, norm, numeros, reais, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("e_se", "What-if with your data: saved X per week since a date, cancelled subscriptions, skipped an expense, ran N km, sold more per day.",
           "calcular | exemplos",
           "calcular: texto (the what-if in Portuguese, e.g. 'guardado 50 por semana desde janeiro a 10% ao ano').", "texto")

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
POR = {"dia": 1, "semana": 7, "mes": 30.44, "ano": 365.25}


def desde(texto: str, hoje: date) -> date | None:
    t = norm(texto)
    m = re.search(r"desde\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", t)
    if m:
        return ler_data(m.group(1))
    for i, nome in enumerate(MESES):
        if re.search(rf"desde\s+(o comeco de |o inicio de )?{nome}", t):
            ano = hoje.year if i + 1 <= hoje.month else hoje.year - 1
            return date(ano, i + 1, 1)
    m = re.search(r"(?:ha|faz)\s+(\d+)\s+(dia|semana|mes|meses|ano)", t)
    if m:
        dias = int(m.group(1)) * POR["mes" if m.group(2).startswith("mes") else m.group(2)]
        return date.fromordinal(hoje.toordinal() - int(dias))
    return None


def periodo(texto: str) -> str | None:
    t = norm(texto)
    m = re.search(r"por\s+(dia|semana|mes|ano)", t) or re.search(r"\b(diari|seman|mensa|anua)", t)
    if not m:
        return None
    g = m.group(1)
    return {"diari": "dia", "seman": "semana", "mensa": "mes", "anua": "ano"}.get(g, g)


def guardado(valor: float, por: str, inicio: date, hoje: date, taxa_aa: float = 0.0) -> tuple[float, float]:
    """(total posto, total com rendimento) de aportes iguais a cada período. Pura."""
    passo = POR[por]
    n = int((hoje - inicio).days // passo) + 1 if hoje >= inicio else 0
    i = (1 + taxa_aa / 100) ** (passo / 365.25) - 1
    fv = valor * n if i == 0 else valor * ((1 + i) ** n - 1) / i
    return valor * n, fv


def _gastos_categoria(cat: str, inicio: date) -> tuple[float, int]:
    from plugins import gastos
    linhas = gastos.ler(gastos._ARQ)
    sel = [g for g in linhas if norm(cat) in norm(g.get("categoria", "") + " " + g.get("descricao", ""))
           and str(g.get("data", "")) >= inicio.isoformat()]
    return sum(float(str(g.get("valor", 0)).replace(",", ".") or 0) for g in sel), len(sel)


def calcular(texto: str, hoje: date | None = None) -> str:
    hoje, t = hoje or date.today(), norm(texto)
    ini = desde(texto, hoje)
    if not ini:
        return "Desde quando? Ex.: 'desde janeiro', 'desde 01/03/2026', 'há 6 meses'."
    meses = (hoje - ini).days / 30.44
    nums = numeros(re.sub(r"desde.*|ha \d+.*", "", t))
    taxa = numeros(re.search(r"(\d+(?:[.,]\d+)?)\s*%", t).group(1))[0] if "%" in t else 0.0
    if re.search(r"\b(guard|economiz|poup|junta)", t):
        por = periodo(t) or "mes"
        if not nums:
            return "Quanto por período?"
        posto, fv = guardado(nums[0], por, ini, hoje, taxa)
        return (f"No universo paralelo você teria {reais(fv)}" + (f" ({reais(fv - posto)} só de rendimento)" if fv > posto else "") +
                f", guardando {reais(nums[0])} por {por.replace('mes', 'mês')} desde {ini:%d/%m/%Y}.")
    if "assinatura" in t:
        from plugins._lote2 import Colecao
        from plugins.assinaturas import mensal
        subs = [s for s in Colecao("assinaturas").tudo().values() if s.get("nao_uso") or "todas" in t]
        if not subs:
            return "Não tenho assinaturas marcadas como 'sem uso'. Diga ao plugin de assinaturas quais você não usa."
        v = sum(mensal(s) for s in subs) * meses
        return f"Se tivesse cancelado {', '.join(s['nome'] for s in subs)} desde {ini:%m/%Y}, você teria {reais(v)} a mais hoje."
    if re.search(r"\b(gast|comprad|pedid)", t):
        cat = re.sub(r".*?(?:gasto|gastado|comprado|pedido)\s+(?:com|em|de)\s+", "", t)
        cat = re.split(r"\s+desde|\s+ha\s", cat)[0].strip()
        try:
            v, n = _gastos_categoria(cat, ini)
        except Exception:
            return "Não consegui ler os seus gastos anotados."
        if not n:
            return f"Não achei gastos com '{cat}' desde {ini:%d/%m/%Y} nos seus registros."
        return f"Sem os {n} gastos com {cat} desde {ini:%d/%m/%Y}, você teria {reais(v)} a mais (média de {reais(v / max(1, meses))} por mês)."
    if re.search(r"\b(corr|caminh|pedal)", t):
        por, km = periodo(t) or "semana", (nums or [5])[0]
        total = km * ((hoje - ini).days / POR[por])
        return (f"Seriam {total:.0f} km — mais ou menos {total / 42.195:.1f} maratonas".replace(".", ",") +
                f" — e uns {total * 60:,.0f} kcal gastas.".replace(",", "."))
    if re.search(r"\b(vend|fatur)", t):
        por, extra = periodo(t) or "dia", (nums or [0])[0]
        dias_loja = (hoje - ini).days * (6 / 7)
        return f"Com {reais(extra)} a mais por {por.replace('mes', 'mês')} desde {ini:%d/%m}, a loja teria faturado {reais(extra * dias_loja / POR[por])} a mais (contando 6 dias abertos por semana)."
    return exemplos()


def exemplos() -> str:
    return ("Exemplos: 'e se eu tivesse guardado 50 por semana desde janeiro a 10% ao ano', 'cancelado as assinaturas sem uso há 6 "
            "meses', 'não tivesse gasto com delivery desde março', 'corrido 10 km por semana desde julho', 'vendido 100 a mais por dia "
            "desde agosto'.")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"calcular": lambda p, pl: calcular(str(p.get("texto") or "")), "exemplos": lambda p, pl: exemplos()}, player)
