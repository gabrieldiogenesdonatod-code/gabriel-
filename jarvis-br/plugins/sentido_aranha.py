"""
Sentido de aranha (2.21): o JARVIS percebe problema ANTES de acontecer, pela tendência dos números.

    "Em 9 dias o disco C enche, no ritmo atual."
    "As vendas da loja caíram três semanas seguidas."
    "Você está bebendo menos água desde segunda."
    "O hábito ler está escapando: 2 dos últimos 7 dias."

Ele guarda um retrato diário do disco e olha as séries que o `sonhos` já junta (vendas, água,
horas, corrida, treino, hábitos). Só avisa quando a tendência é clara, e no máximo uma vez por dia.
"""

from __future__ import annotations

import shutil
import statistics as st
import time
from datetime import date, timedelta

from plugins._lote2 import P, carregar, guardar, rodar

PLUGIN = P("sentido_aranha", "Spider-sense: warns about problems before they happen from trends — disk filling up (days left), store sales "
           "falling for weeks, less water, habits slipping, work hours creeping up.",
           "sentir | disco | historico",
           "sentir: check all trends now. disco: days until each disk fills at the current rate. historico: past warnings.",
           "")


def inclinacao(pontos: list[tuple[float, float]]) -> float:
    """Inclinação da reta (mínimos quadrados). Pura."""
    xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
    mx, my = st.mean(xs), st.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in pontos) / den if den else 0.0


def dias_ate_encher(hist: list[tuple[float, float]], total: float) -> float | None:
    """hist = [(dia ordinal, bytes usados)]. Dias até encher no ritmo atual (só se está enchendo). Pura."""
    if len(hist) < 5:
        return None
    k = inclinacao(hist[-21:])
    if k <= total * 0.001:                          # cresce menos de 0,1% do disco por dia: tranquilo
        return None
    return (total - hist[-1][1]) / k


def semanas_caindo(serie: dict[str, float], ref: date, n: int = 3) -> list[float] | None:
    """Totais das últimas n+1 semanas se cada uma foi menor que a anterior (e caiu 15%+ no total). Pura."""
    tot = []
    for w in range(n, -1, -1):
        ini = ref - timedelta(7 * (w + 1))
        tot.append(sum(v for d, v in serie.items() if ini <= date.fromisoformat(d) < ini + timedelta(7)))
    if min(tot) <= 0 or not all(b < a for a, b in zip(tot, tot[1:])) or tot[-1] > tot[0] * 0.85:
        return None
    return tot


def queda_recente(serie: dict[str, float], ref: date) -> float | None:
    """% de queda da média dos últimos 7 dias contra os 21 anteriores (só quedas de 25%+). Pura."""
    rec = [v for d, v in serie.items() if 0 < (ref - date.fromisoformat(d)).days <= 7]
    ant = [v for d, v in serie.items() if 7 < (ref - date.fromisoformat(d)).days <= 28]
    if len(rec) < 4 or len(ant) < 10 or not st.mean(ant):
        return None
    q = (1 - st.mean(rec) / st.mean(ant)) * 100
    return q if q >= 25 else None


def _discos() -> list[str]:
    import os
    if os.name == "nt":
        return [f"{l}:\\" for l in "CDEFG" if os.path.exists(f"{l}:\\")]
    return ["/"]


def retrato_disco() -> None:
    d = carregar("aranha_disco", {})
    hoje = date.today().toordinal()
    for raiz in _discos():
        try:
            u = shutil.disk_usage(raiz)
        except OSError:
            continue
        h = d.setdefault(raiz, {"total": u.total, "hist": []})
        h["total"] = u.total
        if not h["hist"] or h["hist"][-1][0] != hoje:
            h["hist"].append([hoje, u.used])
            h["hist"] = h["hist"][-60:]
    guardar("aranha_disco", d)


def sentir(ref: date | None = None) -> list[str]:
    ref = ref or date.today()
    avisos = []
    for raiz, h in carregar("aranha_disco", {}).items():
        dias = dias_ate_encher([tuple(x) for x in h["hist"]], h["total"])
        if dias is not None and dias < 60:
            avisos.append(f"Em uns {dias:.0f} dias o disco {raiz} enche, no ritmo atual. Bom fazer uma limpeza antes.")
    try:
        from plugins.sonhos import series
        s = series()
    except Exception:
        s = {}
    if "vendas da loja" in s:
        t = semanas_caindo(s["vendas da loja"], ref)
        if t:
            avisos.append(f"As vendas da loja caíram {len(t) - 1} semanas seguidas ({t[0]:.0f} → {t[-1]:.0f} reais). Hora de uma promoção ou post?")
    for nome, frase in (("água bebida", "Você está bebendo {q:.0f}% menos água nesta semana."),
                        ("km corridos", "Você correu {q:.0f}% menos nesta semana."),
                        ("volume de treino", "O treino caiu {q:.0f}% nesta semana.")):
        if nome in s:
            q = queda_recente(s[nome], ref)
            if q:
                avisos.append(frase.format(q=q))
    for nome, serie in s.items():
        if nome.startswith("hábito"):
            ult = [serie.get((ref - timedelta(k)).isoformat(), 0) for k in range(1, 8)]
            ant = [serie.get((ref - timedelta(k)).isoformat()) for k in range(8, 29)]
            ant = [x for x in ant if x is not None]
            if len(ant) >= 14 and st.mean(ant) >= 0.6 and sum(ult) <= 3:
                avisos.append(f"O {nome} está escapando: só {int(sum(ult))} dos últimos 7 dias (antes era quase todo dia).")
    if "horas trabalhadas" in s:
        rec = [v for d, v in s["horas trabalhadas"].items() if 0 < (ref - date.fromisoformat(d)).days <= 7]
        if len(rec) >= 5 and st.mean(rec) > 10:
            avisos.append(f"Você está trabalhando {st.mean(rec):.1f} horas por dia nesta semana. Cuidado com o cansaço.")
    return avisos


def passo(player) -> None:
    """Uma volta do relógio central (a cada 3 h): retrato do disco e, uma vez por dia, os avisos."""
    from plugins._comum import avisar
    retrato_disco()
    est = carregar("aranha", {"dia": "", "hist": []})
    if est["dia"] != date.today().isoformat() and 9 <= time.localtime().tm_hour < 21:
        av = sentir()
        est["dia"] = date.today().isoformat()
        if av:
            est["hist"] = (est["hist"] + [{"dia": est["dia"], "avisos": av}])[-60:]
            avisar(player, "Meu sentido de aranha disparou: " + " ".join(av), "SENTIDO DE ARANHA")
        guardar("aranha", est)


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("sentido_aranha", lambda: passo(player), a_cada_s=3 * 3600, primeira_em_s=180)


def _go(p, pl):
    a = p["action"]
    if a == "historico":
        return "\n".join(f"{h['dia']}: " + " | ".join(h["avisos"]) for h in carregar("aranha", {"hist": []})["hist"][-10:]) or "Nenhum aviso ainda."
    retrato_disco()
    if a == "disco":
        out = []
        for raiz, h in carregar("aranha_disco", {}).items():
            livre = (h["total"] - h["hist"][-1][1]) / 1e9
            dias = dias_ate_encher([tuple(x) for x in h["hist"]], h["total"])
            out.append(f"{raiz}: {livre:.0f} GB livres, " + (f"enche em uns {dias:.0f} dias." if dias else
                                                           ("ritmo estável." if len(h["hist"]) >= 5 else f"medindo ({len(h['hist'])} de 5 dias).")))
        return " ".join(out) or "Não consegui ler os discos."
    av = sentir()
    return ("Meu sentido de aranha disparou: " + " ".join(av)) if av else "Nada no radar. Tudo tranquilo por enquanto."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("sentir disco historico".split(), _go), player, "Sentido de aranha")
