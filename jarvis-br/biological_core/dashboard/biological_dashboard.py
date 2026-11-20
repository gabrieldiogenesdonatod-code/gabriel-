"""
Painel de saúde geral do organismo — o "Sistema de Saúde Geral".

    dados(org)      tudo o que o painel mostra, em JSON (a aba "Corpo" do celular usa direto)
    svg(dados)      o organismo desenhado: cada órgão com a sua cor, os vasos com o fluxo de dados
                    e o coração batendo no ritmo dos eventos
    pagina(dados)   a página HTML completa (sinais vitais, 8 camadas do sistema imune, incidentes,
                    isolados, pedidos de autorização, decisões do cérebro, aprendizado, diário)
    escrever(org)   grava memory/biological/painel.html (o coração regrava a cada batimento
                    enquanto o painel está aberto; a página se recarrega sozinha a cada 10 s)

Cores: azul = normal · amarelo = atenção · vermelho = falha ou ameaça · verde = recuperação concluída.
"""

from __future__ import annotations

import html
import time
from pathlib import Path

from biological_core.config import agora_txt

CORES = {"azul": "#3fa9ff", "amarelo": "#f5c542", "vermelho": "#ff4d5e", "verde": "#34d399"}
POS = {"cerebro": (180, 52), "nervos": (58, 160), "celulas": (180, 160), "imune": (302, 160), "coracao": (180, 272),
       "dna": (58, 384), "circulacao": (302, 384), "regeneracao": (180, 470)}
VASOS = [("cerebro", "nervos"), ("cerebro", "celulas"), ("cerebro", "imune"), ("nervos", "coracao"), ("celulas", "coracao"),
         ("imune", "coracao"), ("coracao", "dna"), ("coracao", "circulacao"), ("coracao", "regeneracao"),
         ("dna", "regeneracao"), ("circulacao", "regeneracao"), ("nervos", "celulas"), ("celulas", "imune")]
ICONES = {"cerebro": "M-9 2c-3 0-4-6 0-8 1-5 7-5 9-3 2-2 8-2 9 3 4 2 3 8 0 8M0-6v14",
          "coracao": "M0 8l-9-9a5 5 0 017-7l2 2 2-2a5 5 0 017 7z",
          "nervos": "M-9 0h4l3-7 4 14 3-7h4", "imune": "M0-9l8 3v5c0 5-4 8-8 10-4-2-8-5-8-10v-5z",
          "dna": "M-5-9c10 6 0 12 10 18M5-9c-10 6 0 12-10 18M-4-4h8M-4 4h8",
          "circulacao": "M-8 0a8 8 0 0116 0M8 0a8 8 0 01-16 0M8 0l-3-3M-8 0l3 3",
          "regeneracao": "M-7 3a7 7 0 1012-6M5-7v4h4", "celulas": "M-5-3a3 3 0 110 .1M4-4a2.5 2.5 0 110 .1M0 5a3 3 0 110 .1"}


def dados(org) -> dict:
    s = org.saude.ultimo
    orgaos = org.estado_orgaos()
    v = org.coracao.vitais or {}
    abertos = org.memoria.abertos()
    est = org.memoria.estatisticas(time.time() - 7 * 86400)
    return {
        "ts": time.time(), "nota": s.get("nota", 100), "cor": s.get("cor", "azul"), "problemas": s.get("problemas", []),
        "tendencia": org.saude.tendencia(), "historico": [n for _t, n in list(org.saude.historico)[-120:]],
        "orgaos": orgaos, "vitais": {k: v.get(k) for k in ("cpu_jarvis", "ram_jarvis_mb", "ram_pc", "disco_livre_pct",
                                                          "temp_cpu", "threads", "bpm")},
        "batimentos": org.coracao.batimentos, "febre": org.coracao.febre,
        "camadas": org.imune.camadas(), "protecao": org.imune.nivel_protecao(),
        "incidentes": [{k: i[k] for k in ("id", "modulo", "acao", "categoria", "gravidade", "estado", "ocorrencias", "mensagem",
                                          "tratamento", "causa")} for i in abertos[:12]],
        "isolados": org.imune.isolamento.listar(), "pedidos": org.autorizacoes.pendentes(),
        "decisoes": [{k: d[k] for k in ("incidente", "tratamento", "explicacao", "resultado", "ts")} for d in org.memoria.decisoes(6)],
        "aprendizado": org.cerebro.aprendizado(), "semana": est, "diario": list(org.celula_memoria.diario)[-12:],
        "dna": org.dna.resumo(), "circulacao": org.circulacao.estado(), "nervos": org.bus.estado(),
        "inicializacao": org.coracao.inicializacao, "avisos": list(org.avisos)[-5:],
    }


def _e(t) -> str:
    return html.escape(str(t if t is not None else "—"))


def svg(d: dict, largura: str = "100%") -> str:
    org = d["orgaos"]
    bpm = d.get("vitais", {}).get("bpm") or 0
    pulso = max(0.5, min(1.6, 60 / max(40.0, float(bpm) + 40)))
    linhas = []
    for a, b in VASOS:
        (x1, y1), (x2, y2) = POS[a], POS[b]
        cor = CORES.get(org.get(b, {}).get("cor"), CORES["azul"])
        linhas.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{cor}" stroke-opacity=".25" stroke-width="2"/>'
                      f'<line class="fluxo" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{cor}" stroke-width="2"/>')
    nos = []
    for nome, (x, y) in POS.items():
        o = org.get(nome, {})
        cor = CORES.get(o.get("cor"), CORES["azul"])
        r = 34 if nome == "coracao" else 28
        classe = ' class="pulso"' if nome == "coracao" else ""
        nos.append(f'<g transform="translate({x} {y})"><g{classe}>'
                   f'<circle r="{r + 6}" fill="{cor}" fill-opacity=".10"/>'
                   f'<circle r="{r}" fill="#081422" stroke="{cor}" stroke-width="2.5"/>'
                   f'<path d="{ICONES[nome]}" fill="none" stroke="{cor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>'
                   f'<text y="{r + 17}" text-anchor="middle" class="rot">{_e(o.get("titulo", nome))}</text></g>')
    return (f'<svg viewBox="-28 0 416 530" width="{largura}" role="img" aria-label="Organismo do JARVIS" '
            f'style="--pulso:{pulso:.2f}s">'
            '<style>.rot{font:600 12px system-ui,sans-serif;fill:#cfe6ff;paint-order:stroke;stroke:#040a12;stroke-width:4px}.fluxo{stroke-dasharray:4 14;animation:flui 1.6s linear infinite}'
            '@keyframes flui{to{stroke-dashoffset:-36}}.pulso{animation:bate var(--pulso) ease-in-out infinite;transform-origin:center}'
            '@keyframes bate{0%,100%{transform:scale(1)}15%{transform:scale(1.12)}30%{transform:scale(.98)}45%{transform:scale(1.06)}}'
            '@media (prefers-reduced-motion:reduce){.fluxo,.pulso{animation:none}}</style>'
            + "".join(linhas) + "".join(nos) + "</svg>")


def _faixa(hist: list[int]) -> str:
    if len(hist) < 2:
        return ""
    w, h = 300, 46
    pts = " ".join(f"{i * w / (len(hist) - 1):.1f},{h - n * h / 100:.1f}" for i, n in enumerate(hist))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" aria-label="histórico da nota">'
            f'<polyline points="{pts}" fill="none" stroke="#38d6ff" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>')


def pagina(d: dict, recarregar_s: int = 10) -> str:
    cor = CORES.get(d["cor"], CORES["azul"])
    v = d["vitais"]

    def tile(rot, val, suf=""):
        return f'<div class="tile"><span>{rot}</span><b>{_e(val)}{suf if val not in (None, "—") else ""}</b></div>'

    vit = "".join([tile("CPU do JARVIS", v.get("cpu_jarvis"), "%"), tile("Memória do JARVIS", v.get("ram_jarvis_mb"), " MB"),
                   tile("RAM do PC", v.get("ram_pc"), "%"), tile("Disco livre", v.get("disco_livre_pct"), "%"),
                   tile("Temperatura CPU", v.get("temp_cpu"), " °C"), tile("Threads", v.get("threads")),
                   tile("Eventos/min", v.get("bpm")), tile("Batimentos", d.get("batimentos"))])
    orgs = "".join(f'<li><i style="background:{CORES.get(o["cor"], CORES["azul"])}"></i><b>{_e(o["titulo"])}</b>'
                   f'<span>{_e(o["detalhe"])}</span></li>' for o in d["orgaos"].values())
    cam = "".join(f'<li><i class="{"ok" if c["ok"] else ("nd" if c["ok"] is None else "ruim")}"></i><b>{c["camada"]} · {_e(c["nome"])}</b>'
                  f'<span>{_e(c["detalhe"])}</span></li>' for c in d["camadas"])
    inc = "".join(f'<li><b>#{i["id"]} {_e(i["modulo"])}</b> <em class="g-{i["gravidade"]}">{_e(i["gravidade"])}</em>'
                  f'<span>{_e(i["categoria"])} · {_e(i["estado"])} · {i["ocorrencias"]}× — {_e(str(i["mensagem"])[:120])}</span></li>'
                  for i in d["incidentes"]) or "<li><span>Nenhum problema aberto.</span></li>"
    iso = "".join(f'<li><b>{_e(i["chave"].replace("|*", "").replace("|", " → "))}</b><span>{_e(i["tipo"])} · {_e(i["motivo"])}</span></li>'
                  for i in d["isolados"]) or "<li><span>Nada isolado.</span></li>"
    ped = "".join(f'<li><b>{_e(p["id"])} · {_e(p["titulo"])}</b><span>{_e(p["detalhe"])}</span></li>' for p in d["pedidos"])
    ped = (ped + '<li><span>Para aprovar: o banner CONFIRMAR do HUD, a aba Corpo do celular, ou diga "Jarvis, mostra os '
                 'reparos pendentes".</span></li>') if ped else "<li><span>Nenhum pedido esperando você.</span></li>"
    dec = "".join(f'<li><b>{_e(x["tratamento"])}</b> <em>{_e(x.get("resultado") or "em andamento")}</em><span>{_e(x["explicacao"])}</span></li>'
                  for x in d["decisoes"]) or "<li><span>O cérebro ainda não precisou decidir nada.</span></li>"
    apr = d["aprendizado"]
    tab = "".join(f'<tr><td>{_e(t["categoria"])}</td><td>{_e(t["tratamento"])}</td><td>{t["sucessos"]}/{t["sucessos"] + t["falhas"]}</td></tr>'
                  for t in apr.get("tratamentos", [])[:8]) or '<tr><td colspan="3" class="vazio">Ainda sem experiência: cada reparo que der certo (ou errado) entra aqui.</td></tr>'
    dia = "".join(f'<li><b>{agora_txt(x["ts"])}</b><span>{_e(x["tipo"])}: {_e(x["texto"])}</span></li>'
                  for x in reversed(d["diario"])) or "<li><span>Diário vazio.</span></li>"
    prob = "".join(f"<li><span>{_e(p)}</span></li>" for p in d["problemas"]) or "<li><span>Nenhum desconto na nota.</span></li>"
    sem = d["semana"]
    cl = apr.get("classificador", {})
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="{recarregar_s}">
<title>Biological Core</title><style>
:root{{--fundo:#040a12;--painel:#0a1624;--borda:#17324d;--texto:#d9ecff;--fraco:#86a7c4;--acento:#38d6ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--fundo);color:var(--texto);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{display:flex;flex-wrap:wrap;align-items:center;gap:16px;padding:18px 16px;border-bottom:1px solid var(--borda);
background:linear-gradient(90deg,#071425,#040a12)}}
h1{{font-size:15px;letter-spacing:.18em;margin:0;color:var(--acento)}}h1 small{{display:block;color:var(--fraco);letter-spacing:.05em;font-weight:400}}
.nota{{margin-left:auto;display:flex;align-items:baseline;gap:8px}}.nota b{{font-size:38px;color:{cor};font-variant-numeric:tabular-nums}}
.nota span{{color:var(--fraco)}}main{{display:grid;gap:14px;padding:14px 16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}}
section{{background:var(--painel);border:1px solid var(--borda);border-radius:10px;padding:14px;min-width:0}}
h2{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--acento);margin:0 0 10px}}
ul{{list-style:none;margin:0;padding:0}}li{{padding:7px 0;border-top:1px solid #10263b;display:grid;grid-template-columns:auto 1fr;column-gap:8px}}
li:first-child{{border-top:0}}li span{{grid-column:1/-1;color:var(--fraco);font-size:13px;overflow-wrap:anywhere}}
li i{{width:10px;height:10px;border-radius:50%;margin-top:5px}}i.ok{{background:#34d399}}i.ruim{{background:#ff4d5e}}i.nd{{background:#5b7896}}
em{{font-style:normal;font-size:12px;color:var(--fraco)}}.g-alta,.g-critica{{color:#ff4d5e}}.g-media{{color:#f5c542}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}}
.tile{{border:1px solid #10263b;border-radius:8px;padding:8px}}.tile span{{display:block;color:var(--fraco);font-size:12px}}
.tile b{{font-size:18px;font-variant-numeric:tabular-nums}}table{{width:100%;border-collapse:collapse;font-size:13px}}
td{{padding:5px 4px;border-top:1px solid #10263b}}td:last-child{{text-align:right;font-variant-numeric:tabular-nums}}
.org{{grid-row:span 2}}.org svg{{display:block;max-width:440px;margin:0 auto}}
@media (min-width:900px){{.org{{grid-column:span 2}}}}.faixa{{color:var(--fraco);font-size:12px;margin:10px 0 2px}}
td.vazio{{text-align:left;color:var(--fraco)}}.legenda{{display:flex;flex-wrap:wrap;gap:10px;color:var(--fraco);font-size:12px;margin-top:8px}}
.legenda i{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px}}
footer{{color:var(--fraco);font-size:12px;padding:0 16px 18px}}
</style></head><body>
<header><h1>J.A.R.V.I.S · BIOLOGICAL CORE<small>organismo digital — saúde, defesa e regeneração</small></h1>
<div class="nota"><b>{d['nota']}</b><span>/100 · {_e(d['cor'])} · {_e(d['tendencia'])}{' · FEBRE' if d.get('febre') else ''}</span></div></header>
<main>
<section class="org"><h2>Organismo</h2>{svg(d)}
<div class="legenda"><span><i style="background:#3fa9ff"></i>normal</span><span><i style="background:#f5c542"></i>atenção</span>
<span><i style="background:#ff4d5e"></i>falha/ameaça</span><span><i style="background:#34d399"></i>recuperado</span></div>
{'<p class="faixa">Nota de saúde nos últimos batimentos</p>' + _faixa(d['historico']) if len(d['historico']) > 1 else ''}</section>
<section><h2>Órgãos</h2><ul>{orgs}</ul></section>
<section><h2>Sinais vitais</h2><div class="tiles">{vit}</div></section>
<section><h2>Sistema imunológico · proteção {d['protecao']}%</h2><ul>{cam}</ul></section>
<section><h2>Por que a nota</h2><ul>{prob}</ul></section>
<section><h2>Problemas em aberto</h2><ul>{inc}</ul></section>
<section><h2>Isolados</h2><ul>{iso}</ul></section>
<section><h2>Esperando o seu sim</h2><ul>{ped}</ul></section>
<section><h2>Decisões do cérebro</h2><ul>{dec}</ul></section>
<section><h2>Aprendizado</h2><table>{tab}</table>
<p style="color:var(--fraco);font-size:12px;margin:10px 0 0">Classificador: {cl.get('exemplos', 0)} exemplos, {cl.get('aprendidos_com_voce', 0)} aprendidos com você ·
{sem.get('total', 0)} problema(s) na semana, {sem.get('resolvidos', 0)} curado(s), {sem.get('automaticos', 0)} sozinho.</p></section>
<section><h2>Diário do organismo</h2><ul>{dia}</ul></section>
</main><footer>Atualizado {agora_txt(d['ts'])} · DNA {_e(d['dna'].get('situacao'))} ({d['dna'].get('arquivos', 0)} arquivos) ·
circulação {d['circulacao'].get('entregues', 0)} eventos entregues · a página se atualiza sozinha.</footer></body></html>"""


def escrever(org, caminho: Path | None = None) -> Path:
    caminho = Path(caminho or org.pasta / "painel.html")
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(pagina(dados(org)), encoding="utf-8")
    tmp.replace(caminho)
    return caminho
