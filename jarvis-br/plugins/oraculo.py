"""
Oráculo (3.0): o JARVIS prevê quanto a loja vai vender em cada dia da próxima semana e, quando a
semana acaba, CONFERE o quanto errou. O placar de acerto fica guardado.

    "Jarvis, quanto a loja vai vender semana que vem?"
    "Jarvis, como foi a previsão da semana passada?"     "Jarvis, qual o seu placar de acerto?"

Como prevê: para cada dia da semana, a mediana das últimas 4 vezes daquele dia (as sextas olham as
sextas), ajustada pela tendência das 2 últimas semanas. Usa as vendas do `caixa_loja`. Todo
domingo à noite ele faz a previsão sozinho e confere a da semana que terminou.
"""

from __future__ import annotations

import statistics as st
import time
from datetime import date, timedelta

from plugins._lote2 import P, carregar, guardar, reais, rodar

PLUGIN = P("oraculo", "Sales oracle: predicts next week's store sales per weekday from the cash register history, then checks its own "
           "error when the week ends and keeps an accuracy score.",
           "prever | conferir | placar",
           "prever: next week's forecast per day (also auto-checks finished weeks). conferir: compare past forecasts with what "
           "happened. placar: accuracy history.", "")

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def segunda_que_vem(ref: date) -> date:
    return ref + timedelta(7 - ref.weekday())


def prever_semana(serie: dict[str, float], inicio: date) -> dict[str, float]:
    """{data iso: previsão} para os 7 dias a partir de 'inicio' (uma segunda). Pura."""
    hist = {date.fromisoformat(d): v for d, v in serie.items() if date.fromisoformat(d) < inicio}
    if len(hist) < 7:
        return {}
    ult28 = [v for d, v in hist.items() if (inicio - d).days <= 28] or list(hist.values())
    geral = st.median(ult28)
    # Tendência: cada dia comparado com o normal do MESMO dia da semana (não depende de quantos dias têm caixa).
    normal = {wd: st.median([v for d, v in hist.items() if d.weekday() == wd] or [geral]) for wd in range(7)}
    razoes = lambda a, b: [v / normal[d.weekday()] for d, v in hist.items() if a < (inicio - d).days <= b and normal[d.weekday()]]  # noqa: E731
    rec, ant = razoes(0, 14), razoes(14, 28)
    tendencia = min(1.15, max(0.85, st.mean(rec) / st.mean(ant))) if len(rec) >= 5 and len(ant) >= 5 and st.mean(ant) else 1.0
    # 3.3: dia da semana que nunca teve caixa em 3+ semanas de histórico = loja fechada (não inventa venda no domingo).
    fechados = set(range(7)) - {d.weekday() for d in hist} if (max(hist) - min(hist)).days >= 20 else set()
    out = {}
    for k in range(7):
        dia = inicio + timedelta(k)
        if dia.weekday() in fechados:
            continue
        mesmos = [v for d, v in sorted(hist.items()) if d.weekday() == dia.weekday()][-4:]
        base = st.median(mesmos) if len(mesmos) >= 2 else geral
        out[dia.isoformat()] = round(base * tendencia, 2)
    return out


def erro(previsao: dict[str, float], serie: dict[str, float]) -> tuple[float, float, int] | None:
    """(erro do total da semana %, erro médio por dia %, dias comparados). Só dias com caixa registrado. Pura."""
    pares = [(p, serie[d]) for d, p in previsao.items() if d in serie and serie[d] > 0]
    if len(pares) < 3:
        return None
    tot_p, tot_r = sum(p for p, _ in pares), sum(r for _, r in pares)
    return abs(tot_p - tot_r) / tot_r * 100, st.mean(abs(p - r) / r * 100 for p, r in pares), len(pares)


def _vendas() -> dict[str, float]:
    from plugins.sonhos import series
    return series().get("vendas da loja", {})


def conferir_tudo(hoje: date | None = None) -> list[str]:
    hoje, est, serie = hoje or date.today(), carregar("oraculo", {"previsoes": []}), _vendas()
    out = []
    for prev in est["previsoes"]:
        fim = date.fromisoformat(prev["semana"]) + timedelta(7)
        if prev.get("erro") is None and fim <= hoje:
            e = erro(prev["dias"], serie)
            prev["erro"] = list(e) if e else "sem dados"
            if e:
                out.append(f"Semana de {prev['semana'][8:]}/{prev['semana'][5:7]}: errei o total por {e[0]:.0f}% "
                           f"(acerto de {max(0, 100 - e[0]):.0f}%).")
    guardar("oraculo", est)
    return out


def prever(hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    conferidas = conferir_tudo(hoje)
    inicio = segunda_que_vem(hoje)
    prev = prever_semana(_vendas(), inicio)
    if not prev:
        return "Ainda não tenho vendas suficientes. Use o caixa da loja por pelo menos uma semana e eu começo a prever."
    est = carregar("oraculo", {"previsoes": []})
    est["previsoes"] = [p for p in est["previsoes"] if p["semana"] != inicio.isoformat()] + \
        [{"semana": inicio.isoformat(), "dias": prev, "feita": hoje.isoformat(), "erro": None}]
    guardar("oraculo", est | {"previsoes": est["previsoes"][-60:]})
    melhor = max(prev, key=prev.get)
    linhas = [f"{DIAS[date.fromisoformat(d).weekday()]}: {reais(v)}" for d, v in prev.items()]
    return ("\n".join(conferidas) + "\n" if conferidas else "") + \
        f"Previsão da semana de {inicio:%d/%m}: total {reais(sum(prev.values()))}. Melhor dia: " \
        f"{DIAS[date.fromisoformat(melhor).weekday()]} ({reais(prev[melhor])}).\n" + "\n".join(linhas)


def placar() -> str:
    feitas = [p for p in carregar("oraculo", {"previsoes": []})["previsoes"] if isinstance(p.get("erro"), list)]
    if not feitas:
        return "Ainda não terminei nenhuma semana prevista. Volto com o placar depois da primeira."
    erros = [p["erro"][0] for p in feitas[-8:]]
    return (f"Acerto médio nas últimas {len(erros)} semana(s): {max(0, 100 - st.mean(erros)):.0f}%. "
            f"Melhor semana: {max(0, 100 - min(erros)):.0f}%, pior: {max(0, 100 - max(erros)):.0f}%.")


def passo(player) -> None:
    """Relógio central: domingo à noite faz a previsão e confere a semana que acabou."""
    agora = time.localtime()
    if agora.tm_wday == 6 and agora.tm_hour >= 19:
        inicio = segunda_que_vem(date.today()).isoformat()
        if not any(p["semana"] == inicio for p in carregar("oraculo", {"previsoes": []})["previsoes"]):
            r = prever()
            if not r.startswith("Ainda não"):
                from plugins._comum import avisar, mostrar
                mostrar(player, "ORÁCULO", r)
                avisar(player, "Fiz a previsão de vendas da semana que vem. Está no painel.", "ORÁCULO")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("oraculo", lambda: passo(player), a_cada_s=3600, primeira_em_s=300)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"prever": lambda p, pl: prever(), "conferir": lambda p, pl: "\n".join(conferir_tudo()) or
                              "Nenhuma semana prevista terminou ainda.", "placar": lambda p, pl: placar()}, player, "Oráculo")
