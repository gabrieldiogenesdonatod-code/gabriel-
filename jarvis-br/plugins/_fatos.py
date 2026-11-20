"""
Fatos da vida (fork PT-BR 3.0): junta, de uma vez, o que os plugins sabem sobre um período —
vendas, hábitos, água, corrida, treino de IA, sonhos, metas. Usado pelo jornal e pelo rap.
Começa com "_": não vira ferramenta.
"""

from __future__ import annotations

import statistics as st
from datetime import date, timedelta


def _soma(serie: dict[str, float], ini: date, fim: date) -> float:
    return sum(v for d, v in serie.items() if ini <= date.fromisoformat(d) <= fim)


def periodo(ini: date, fim: date) -> dict:
    """Fatos entre ini e fim (inclusive), comparando com o período anterior de mesmo tamanho."""
    from plugins._lote2 import Colecao, carregar
    f: dict = {}
    try:
        from plugins.sonhos import series
        s = series()
    except Exception:
        s = {}
    dur = (fim - ini).days + 1
    ant_ini, ant_fim = ini - timedelta(dur), ini - timedelta(1)
    if "vendas da loja" in s:
        v, a = _soma(s["vendas da loja"], ini, fim), _soma(s["vendas da loja"], ant_ini, ant_fim)
        f["vendas"] = {"total": v, "antes": a, "variacao": ((v - a) / a * 100) if a else None}
        dias = {d: x for d, x in s["vendas da loja"].items() if ini <= date.fromisoformat(d) <= fim}
        if dias:
            melhor = max(dias, key=dias.get)
            f["vendas"]["melhor_dia"] = (melhor, dias[melhor])
    if "água bebida" in s:
        vals = [v for d, v in s["água bebida"].items() if ini <= date.fromisoformat(d) <= fim]
        if vals:
            f["agua_media"] = st.mean(vals)
    if "km corridos" in s:
        f["km"] = _soma(s["km corridos"], ini, fim)
    if "volume de treino" in s:
        f["treinos"] = sum(1 for d in s["volume de treino"] if ini <= date.fromisoformat(d) <= fim)
    try:
        from plugins.sequencias import ofensiva
        f["ofensivas"] = {h["nome"]: ofensiva(h["dias"], fim) for h in Colecao("sequencias").tudo().values()}
    except Exception:
        pass
    try:
        exps = [t for t in Colecao("treinos_ia").tudo().values() if t.get("pontos")]
        if exps:
            t = max(exps, key=lambda t: t["pontos"][-1][0])
            f["ia"] = {"nome": t["nome"], "loss": t["pontos"][-1][1], "passo": t["pontos"][-1][0]}
    except Exception:
        pass
    sonhos = [x for x in carregar("sonhos", []) if ini.isoformat() <= x.get("dia", "") <= fim.isoformat() and x.get("achados")]
    if sonhos:
        f["sonho"] = sonhos[-1]["achados"][0]
    try:
        metas = [m for m in Colecao("metas").tudo().values()]
        if metas:
            from plugins.metas_pessoais import percentual
            f["metas"] = {m["nome"]: percentual(m) for m in metas}
    except Exception:
        pass
    return f


def frases(f: dict) -> list[str]:
    """Os fatos em frases curtas, do mais forte para o mais fraco."""
    out = []
    v = f.get("vendas")
    if v and v["total"]:
        var = v.get("variacao")
        out.append(f"a loja vendeu R$ {v['total']:,.0f}".replace(",", ".") +
                   (f", {abs(var):.0f}% {'a mais' if var > 0 else 'a menos'} que antes" if var is not None and abs(var) >= 5 else ""))
    if f.get("sonho"):
        out.append(f"o JARVIS sonhou que {f['sonho'][0].lower() + f['sonho'][1:]}")
    for nome, n in sorted((f.get("ofensivas") or {}).items(), key=lambda x: -x[1])[:2]:
        if n >= 3:
            out.append(f"{n} dias seguidos de {nome}")
    if f.get("km"):
        out.append(f"{f['km']:.0f} km corridos")
    if f.get("ia"):
        out.append(f"a IA {f['ia']['nome']} chegou na loss {f['ia']['loss']:.2f}")
    if f.get("agua_media"):
        out.append(f"média de {f['agua_media'] / 1000:.1f} litros de água por dia".replace(".", ","))
    for nome, pct in (f.get("metas") or {}).items():
        out.append(f"a meta '{nome}' está em {pct}%")
    return out
