"""
Painel de produtividade dev (fork PT-BR 1.6).

Horas programando (pela linha do tempo: VS Code, PyCharm, terminal…), por
projeto e por dia, commits dos seus repositórios e as linguagens que você
mais mexeu — num painel com gráficos que abre no navegador.

    "Jarvis, mostra meu painel de programação"      "Jarvis, quanto eu codei essa semana?"
"""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, abrir_no_sistema

PLUGIN = {
    "name": "painel_dev",
    "brief": "Developer productivity: coding hours per day/project, commits and languages, with charts.",
    "description": (
        "Developer productivity dashboard: coding hours (from the activity timeline) per day and project, git commits "
        "and most used languages, opened as a page with charts. dias = period in days (default 7)."
    ),
    "parameters": {"type": "OBJECT", "properties": {"dias": {"type": "INTEGER"}}, "required": []},
}

APPS_CODIGO = {"VS Code", "PyCharm", "Terminal", "PowerShell", "Notepad++", "Visual Studio", "Cursor", "Arduino IDE"}
_HTML = MEMORIA / "painel_dev.html"


def horas(focos: list[dict]) -> tuple[dict, dict]:
    """(segundos por dia, segundos por projeto) só dos apps de código (pura)."""
    por_dia, por_proj = defaultdict(float), defaultdict(float)
    for f in focos:
        if f.get("app") in APPS_CODIGO or f.get("atividade") in APPS_CODIGO:
            s = f["fim"] - f["inicio"]
            por_dia[date.fromtimestamp(f["inicio"]).isoformat()] += s
            por_proj[f.get("projeto") or "(sem projeto)"] += s
    return dict(por_dia), dict(por_proj)


def barras_svg(dados: list[tuple[str, float]], unidade: str = "h", largura: int = 640) -> str:
    """Gráfico de barras horizontal em SVG (puro)."""
    if not dados:
        return "<p class='vazio'>Sem dados no período.</p>"
    maximo = max(v for _k, v in dados) or 1
    alt, partes = 28, []
    for i, (rot, v) in enumerate(dados):
        w = max(2, (largura - 220) * v / maximo)
        y = i * alt
        partes.append(f"<text x='0' y='{y + 18}' class='rot'>{html.escape(rot[:26])}</text>"
                      f"<rect x='180' y='{y + 6}' width='{w:.0f}' height='16' rx='4' class='barra'/>"
                      f"<text x='{186 + w:.0f}' y='{y + 19}' class='val'>{v:.1f}{unidade}</text>")
    return f"<svg viewBox='0 0 {largura} {alt * len(dados)}' width='100%' role='img'>{''.join(partes)}</svg>"


def coletar(dias: int) -> dict:
    desde = datetime.combine(date.today() - timedelta(days=dias - 1), datetime.min.time()).timestamp()
    focos = []
    try:
        from plugins import _monitor_db
        focos = _monitor_db.focos(desde)
    except Exception:
        pass
    por_dia, por_proj = horas(focos)
    commits, linguagens, por_repo = 0, Counter(), Counter()
    try:
        from plugins import _projetos
        for repo in _projetos.repos():
            for c in _projetos.commits(repo, desde):
                commits += 1
                por_repo[repo.name] += 1
                for arq, mais, menos in c["arquivos"]:
                    lang = _projetos.linguagem(arq)
                    if lang:
                        linguagens[lang] += mais + menos
    except Exception:
        pass
    return {"dias": dias, "desde": desde, "por_dia": por_dia, "por_proj": por_proj, "commits": commits,
            "por_repo": dict(por_repo), "linguagens": dict(linguagens)}


def pagina(d: dict) -> str:
    dias = [(date.today() - timedelta(days=i)).isoformat() for i in range(d["dias"] - 1, -1, -1)]
    total = sum(d["por_dia"].values()) / 3600
    ling_total = sum(d["linguagens"].values()) or 1
    secoes = [
        ("Horas programando por dia", barras_svg([(datetime.fromisoformat(x).strftime("%a %d/%m"), d["por_dia"].get(x, 0) / 3600)
                                                  for x in dias])),
        ("Por projeto", barras_svg(sorted(((k, v / 3600) for k, v in d["por_proj"].items()), key=lambda x: -x[1])[:10])),
        ("Commits por repositório", barras_svg(sorted(((k, float(v)) for k, v in d["por_repo"].items()),
                                                      key=lambda x: -x[1])[:10], "")),
        ("Linguagens (linhas mudadas nos commits)", barras_svg(sorted(((k, 100 * v / ling_total) for k, v in
                                                                       d["linguagens"].items()), key=lambda x: -x[1])[:8], "%")),
    ]
    corpo = "".join(f"<section><h2>{t}</h2>{s}</section>" for t, s in secoes)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Painel dev — J.A.R.V.I.S</title>
<style>:root{{--bg:#f6f8fb;--card:#fff;--txt:#14202b;--mudo:#5d6b78;--cor:#2563eb}}
@media (prefers-color-scheme: dark){{:root{{--bg:#0b1118;--card:#121b25;--txt:#e3ebf3;--mudo:#8796a5;--cor:#5aa2ff}}}}
body{{margin:0;background:var(--bg);color:var(--txt);font-family:Segoe UI,system-ui,sans-serif}}
main{{max-width:860px;margin:0 auto;padding:24px 16px}} h1{{font-size:22px;margin:0 0 4px}}
.kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}} .kpi{{background:var(--card);border-radius:12px;padding:14px 18px;flex:1;min-width:140px}}
.kpi b{{font-size:26px;display:block}} .kpi span{{color:var(--mudo);font-size:13px}}
section{{background:var(--card);border-radius:12px;padding:14px 18px;margin:12px 0}} h2{{font-size:15px;margin:0 0 10px}}
.rot,.val{{font-size:12px;fill:var(--txt)}} .val{{fill:var(--mudo)}} .barra{{fill:var(--cor)}} .vazio{{color:var(--mudo)}}</style></head>
<body><main><h1>Painel de programação</h1><div style="color:var(--mudo)">Últimos {d['dias']} dias · gerado {datetime.now():%d/%m %H:%M}</div>
<div class="kpis"><div class="kpi"><b>{total:.1f} h</b><span>programando</span></div>
<div class="kpi"><b>{d['commits']}</b><span>commits</span></div>
<div class="kpi"><b>{len(d['por_proj'])}</b><span>projetos</span></div></div>{corpo}</main></body></html>"""


def run(parameters: dict, player=None, session_memory=None) -> str:
    dias = max(1, min(90, int((parameters or {}).get("dias") or 7)))
    try:
        d = coletar(dias)
        _HTML.write_text(pagina(d), encoding="utf-8")
        abrir_no_sistema(str(_HTML))
        total = sum(d["por_dia"].values()) / 3600
        top = max(d["por_proj"].items(), key=lambda x: x[1])[0] if d["por_proj"] else ""
        lang = max(d["linguagens"].items(), key=lambda x: x[1])[0] if d["linguagens"] else ""
        return (f"Nos últimos {dias} dias: {total:.1f} h programando" + (f", mais no {top}" if top else "")
                + f", {d['commits']} commit(s)" + (f", mais em {lang}" if lang else "") + ". Abri o painel com os gráficos.")
    except Exception as e:
        return f"O painel dev falhou: {e}"

