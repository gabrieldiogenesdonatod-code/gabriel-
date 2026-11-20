"""
Mapa de calor do ano (3.0): igual ao quadradinho verde do GitHub, só que para a sua vida inteira —
um mapa por assunto: vendas da loja, uso do JARVIS, água, corrida, treino, hábitos e commits.

    "Jarvis, gera o mapa de calor do meu ano."
    "Jarvis, mapa de calor com os commits do projeto jarvis-br."
    "Jarvis, resumo do meu ano em números."
"""

from __future__ import annotations

import html
import time
from datetime import date, timedelta
from pathlib import Path

from plugins._lote2 import P, num1, pagina, rodar

PLUGIN = P("mapa_calor", "Year heatmap of your life (GitHub-style) for sales, JARVIS use, water, runs, training, habits and git commits.",
           "gerar | resumo", "ano (default current), pasta (git repo for commits, optional).", "ano pasta")

CORES = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]


def series_do_ano(ano: int, pasta: str = "") -> dict[str, dict[str, float]]:
    s: dict[str, dict[str, float]] = {}
    try:
        from plugins.sonhos import series
        s.update(series())
    except Exception:
        pass
    try:
        from core import registro_uso
        uso: dict[str, float] = {}
        for c in registro_uso.chamadas(desde=time.mktime((ano, 1, 1, 0, 0, 0, 0, 0, -1))):
            d = time.strftime("%Y-%m-%d", time.localtime(c["ts"]))
            uso[d] = uso.get(d, 0) + 1
        if uso:
            s["uso do JARVIS"] = uso
    except Exception:
        pass
    if pasta and Path(pasta).expanduser().is_dir():
        try:
            from plugins.commit_mentiroso import git
            com: dict[str, float] = {}
            for d in git(Path(pasta).expanduser(), "log", f"--since={ano}-01-01", "--format=%ad", "--date=short").split():
                com[d] = com.get(d, 0) + 1
            if com:
                s["commits"] = com
        except Exception:
            pass
    return {k: {d: v for d, v in serie.items() if d.startswith(str(ano))} for k, serie in s.items() if any(d.startswith(str(ano)) for d in serie)}


def nivel(v: float, cortes: list[float]) -> int:
    return 0 if v <= 0 else 1 + sum(v > c for c in cortes)


def cortes(vals: list[float]) -> list[float]:
    pos = sorted(v for v in vals if v > 0)
    if not pos:
        return [0, 0, 0]
    return [pos[int(len(pos) * q)] for q in (0.25, 0.5, 0.75)]


def maior_sequencia(dias: set[str]) -> int:
    melhor = atual = 0
    ant = None
    for d in sorted(dias):
        dd = date.fromisoformat(d)
        atual = atual + 1 if ant and (dd - ant).days == 1 else 1
        melhor, ant = max(melhor, atual), dd
    return melhor


def svg(serie: dict[str, float], ano: int) -> str:
    c, ini = cortes(list(serie.values())), date(ano, 1, 1)
    inicio = ini - timedelta(ini.weekday())
    q = []
    for k in range((date(ano, 12, 31) - inicio).days + 1):
        d = inicio + timedelta(k)
        if d.year != ano:
            continue
        v = serie.get(d.isoformat(), 0)
        q.append(f"<rect x='{(k // 7) * 13}' y='{d.weekday() * 13}' width='11' height='11' rx='2' fill='{CORES[nivel(v, c)]}'>"
                 f"<title>{d:%d/%m}: {v:g}</title></rect>")
    return f"<svg width='{54 * 13}' height='{7 * 13}' role='img'>{''.join(q)}</svg>"


def resumo(s: dict[str, dict[str, float]]) -> list[str]:
    out = []
    for nome, serie in s.items():
        ativos = {d for d, v in serie.items() if v > 0}
        if not ativos:
            continue
        melhor = max(serie, key=serie.get)
        out.append(f"{nome}: {len(ativos)} dia(s) ativo(s), maior sequência {maior_sequencia(ativos)} dia(s), melhor dia {melhor[8:]}/{melhor[5:7]} ({serie[melhor]:g})")
    return out


def _go(p, pl):
    ano = int(num1(p, "ano", date.today().year))
    s = series_do_ano(ano, str(p.get("pasta") or ""))
    if not s:
        return f"Ainda não tenho dados de {ano}. Use o caixa, a água, os hábitos, a corrida ou o treino e o mapa vai se pintando."
    linhas = resumo(s)
    if p["action"] == "resumo":
        return "\n".join(linhas)
    corpo = "".join(f"<h3>{html.escape(nome)}</h3>{svg(serie, ano)}" for nome, serie in s.items())
    legenda = "<p>Menos " + "".join(f"<span style='display:inline-block;width:11px;height:11px;background:{c};margin:0 2px'></span>"
                                    for c in CORES) + " Mais</p>"
    arq = pagina("Mapa de calor", f"Meu ano de {ano}", legenda + corpo + "<h3>Resumo</h3><p>" + "<br>".join(map(html.escape, linhas)) + "</p>")
    return f"Mapa de calor de {ano} com {len(s)} assunto(s) pronto: {arq}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"gerar": _go, "resumo": _go}, player, "Mapa de calor")
