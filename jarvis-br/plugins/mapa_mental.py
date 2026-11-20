"""
Mapa mental (fork PT-BR 3.8) — transforma um assunto falado num mapa mental bonito, que abre no navegador.

    "Jarvis, faz um mapa mental de redes de computadores"            (o Gemini sugere os ramos)
    "Jarvis, mapa mental da apresentação do SENAI: problema: …; solução: …, …; demonstração: …"
    "Jarvis, adiciona no mapa do SENAI o ramo custos: luz, internet"
    "Jarvis, abre o mapa mental do SENAI"        "Jarvis, quais mapas mentais eu tenho?"

Formato dos ramos: "ramo: item, item; outro ramo: item" (ou um ramo por linha). O mapa fica guardado e
abre como página (Documentos/JARVIS/Mapas mentais): dá para arrastar, aproximar com a roda do mouse ou
com dois dedos, clicar num ramo para esconder os itens e imprimir. Funciona sem internet.
"""
from __future__ import annotations

import html
import json
import re
import time

from plugins import _comum
from plugins._lote2 import P, carregar, guardar, norm, rodar

PLUGIN = P("mapa_mental", "Mind maps: turn a topic and its branches into an interactive mind map page (offline), saved to reopen and extend.",
           "criar | adicionar | abrir | listar | apagar",
           "criar: tema, ramos as text 'branch: item, item; branch: item' (if the user gives only the topic, YOU write 4-7 useful branches "
           "with 2-5 short items each in Portuguese). adicionar: tema (existing map), ramos. abrir/apagar: tema. listar: saved maps.",
           "tema ramos")

CORES = ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#fb7185", "#60a5fa", "#f97316"]
MAX_RAMOS, MAX_ITENS = 12, 10


def ler_ramos(texto) -> list[dict]:
    """'a: x, y; b: z' (ou linhas) → [{'nome': 'a', 'itens': ['x','y']}, …]. Pura."""
    ramos = []
    for parte in re.split(r"[;\n]+", str(texto or "")):
        parte = parte.strip(" -•*\t")
        if not parte:
            continue
        if ":" in parte:
            nome, resto = parte.split(":", 1)
            itens = [i.strip(" .") for i in re.split(r",|\s+e\s+(?=\S+$)", resto) if i.strip(" .")]
        else:
            nome, itens = parte, []
        nome = nome.strip(" .")
        if nome:
            ramos.append({"nome": nome[:60], "itens": [i[:80] for i in itens][:MAX_ITENS]})
    return ramos[:MAX_RAMOS]


def juntar(ramos: list[dict], novos: list[dict]) -> list[dict]:
    """Ramo com o mesmo nome ganha os itens novos (sem repetir); ramo novo entra no fim. Pura."""
    out = [dict(r, itens=list(r["itens"])) for r in ramos]
    for n in novos:
        alvo = next((r for r in out if norm(r["nome"]) == norm(n["nome"])), None)
        if alvo:
            alvo["itens"] += [i for i in n["itens"] if norm(i) not in {norm(x) for x in alvo["itens"]}]
            alvo["itens"] = alvo["itens"][:MAX_ITENS]
        elif len(out) < MAX_RAMOS:
            out.append(n)
    return out


def chave(tema) -> str:
    t = re.sub(r"\b(mapa|mental|mentais|de|da|do|das|dos|sobre|o|a)\b", " ", norm(tema))
    return re.sub(r"\s+", " ", t).strip()


def _est() -> dict:
    return carregar("mapa_mental", {"mapas": {}})


def _achar(e: dict, tema) -> str | None:
    k = chave(tema)
    if not k:
        return None
    if k in e["mapas"]:
        return k
    perto = [m for m in e["mapas"] if k in m or m in k or set(k.split()) & set(m.split())]
    return perto[0] if len(perto) == 1 else None


def html_mapa(tema: str, ramos: list[dict]) -> str:
    """A página do mapa: SVG desenhado no navegador (arrastar, zoom, esconder ramo, imprimir). Pura."""
    dados = json.dumps({"tema": tema, "ramos": ramos, "cores": CORES}, ensure_ascii=False).replace("</", "<\\/")
    return """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>""" + html.escape(tema) + """ · mapa mental</title>
<style>
:root{--fundo:#f7f8fb;--tinta:#1f2937;--linha:#cbd5e1;--cartao:#ffffff}
@media (prefers-color-scheme:dark){:root{--fundo:#0b1220;--tinta:#e5e7eb;--linha:#334155;--cartao:#111a2e}}
html,body{margin:0;height:100%;background:var(--fundo);color:var(--tinta);font-family:system-ui,sans-serif;overflow:hidden}
#topo{position:fixed;top:0;left:0;right:0;display:flex;gap:8px;align-items:center;padding:10px 14px;z-index:2;flex-wrap:wrap}
#topo h1{font-size:16px;margin:0 auto 0 0;font-weight:600}
button{border:1px solid var(--linha);background:var(--cartao);color:var(--tinta);border-radius:8px;padding:6px 10px;font-size:14px;cursor:pointer}
svg{width:100%;height:100%;touch-action:none;cursor:grab}
.no rect{fill:var(--cartao);stroke-width:2}.no text{fill:var(--tinta);font-size:14px}
.centro text{font-size:18px;font-weight:700}.item text{font-size:13px}
.ramo{cursor:pointer}
@media print{#topo{display:none}html,body{overflow:visible}}
</style></head><body>
<div id="topo"><h1></h1><button id="mais">+</button><button id="menos">−</button><button id="centro">Centralizar</button>
<button onclick="print()">Imprimir</button></div>
<svg id="s"><g id="g"></g></svg>
<script>
const D = """ + dados + """;
document.querySelector("h1").textContent = D.tema;
const NS = "http://www.w3.org/2000/svg", g = document.getElementById("g"), s = document.getElementById("s");
const fechados = new Set();
let vx = 0, vy = 0, zoom = 1;
function el(t, a, pai) { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); (pai || g).appendChild(e); return e; }
function caixa(x, y, texto, cor, classe, aoClicar) {
  const n = el("g", { class: "no " + classe }), t = el("text", { x: x, y: y + 5, "text-anchor": "middle" }, n);
  t.textContent = texto;
  const w = Math.max(40, t.getComputedTextLength() + 24), h = classe === "centro" ? 44 : 32;
  const r = el("rect", { x: x - w / 2, y: y - h / 2, width: w, height: h, rx: h / 2, stroke: cor }, n);
  n.insertBefore(r, t);
  if (aoClicar) n.addEventListener("click", aoClicar);
  return n;
}
function desenhar() {
  g.innerHTML = "";
  const R = D.ramos, n = Math.max(1, R.length), raio = 190 + n * 14, oval = innerHeight > innerWidth ? 1.7 : 0.72;  // celular em pé: mapa alto
  R.forEach((ramo, i) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / n, cor = D.cores[i % D.cores.length];
    const x = Math.cos(a) * raio, y = Math.sin(a) * raio * oval;
    el("path", { d: `M0,0 Q${x * 0.5},${y * 0.1} ${x},${y}`, stroke: cor, "stroke-width": 4, fill: "none", opacity: 0.8 });
    if (!fechados.has(i)) {
      const m = ramo.itens.length;
      ramo.itens.forEach((item, j) => {
        const b = a + (j - (m - 1) / 2) * Math.min(0.32, 1.4 / Math.max(1, m));
        const r2 = raio + 150 + (j % 2) * 26, ix = Math.cos(b) * r2, iy = Math.sin(b) * r2 * oval;
        el("path", { d: `M${x},${y} L${ix},${iy}`, stroke: cor, "stroke-width": 2, fill: "none", opacity: 0.55 });
        caixa(ix, iy, item, cor, "item");
      });
    }
    const rotulo = ramo.nome + (ramo.itens.length && fechados.has(i) ? ` (+${ramo.itens.length})` : "");
    caixa(x, y, rotulo, cor, "ramo", () => { fechados.has(i) ? fechados.delete(i) : fechados.add(i); desenhar(); });
  });
  caixa(0, 0, D.tema, "#22d3ee", "centro");
  aplicar();
}
function aplicar() { g.setAttribute("transform", `translate(${innerWidth / 2 + vx},${innerHeight / 2 + 20 + vy}) scale(${zoom})`); }
function ajustar() { const b = g.getBBox(); zoom = Math.min(1.2, (innerWidth - 40) / b.width, (innerHeight - 90) / b.height); vx = vy = 0; aplicar(); }
let arrasto = null, dedos = new Map(), dist0 = 0, zoom0 = 1;
s.addEventListener("pointerdown", e => { dedos.set(e.pointerId, e); if (dedos.size === 1) arrasto = { x: e.clientX - vx, y: e.clientY - vy };
  if (dedos.size === 2) { const [a, b] = [...dedos.values()]; dist0 = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY); zoom0 = zoom; } });
s.addEventListener("pointermove", e => { if (!dedos.has(e.pointerId)) return; dedos.set(e.pointerId, e);
  if (dedos.size === 2) { const [a, b] = [...dedos.values()]; zoom = Math.max(0.2, Math.min(3, zoom0 * Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) / dist0)); aplicar(); }
  else if (arrasto) { vx = e.clientX - arrasto.x; vy = e.clientY - arrasto.y; aplicar(); } });
["pointerup", "pointercancel", "pointerleave"].forEach(t => s.addEventListener(t, e => { dedos.delete(e.pointerId); if (!dedos.size) arrasto = null; }));
s.addEventListener("wheel", e => { e.preventDefault(); zoom = Math.max(0.2, Math.min(3, zoom * (e.deltaY < 0 ? 1.1 : 0.9))); aplicar(); }, { passive: false });
document.getElementById("mais").onclick = () => { zoom = Math.min(3, zoom * 1.2); aplicar(); };
document.getElementById("menos").onclick = () => { zoom = Math.max(0.2, zoom / 1.2); aplicar(); };
document.getElementById("centro").onclick = ajustar;
addEventListener("resize", () => { desenhar(); ajustar(); });
desenhar(); ajustar();
</script></body></html>"""


def _escrever_e_abrir(tema: str, ramos: list[dict], abrir: bool = True) -> str:
    pasta = _comum.pasta_jarvis("Mapas mentais")
    arq = pasta / f"{re.sub(r'[^a-z0-9]+', '_', norm(tema))[:40] or 'mapa'}.html"
    arq.write_text(html_mapa(tema, ramos), encoding="utf-8")
    if abrir:
        _comum.abrir_no_sistema(str(arq))
    return str(arq)


def _criar(p, pl):
    tema = str(p.get("tema") or "").strip(" .")
    if not tema:
        return "Qual o assunto do mapa mental?"
    ramos = ler_ramos(p.get("ramos"))
    if not ramos:
        return (f"Para o mapa de '{tema}', mande os ramos: 'ramo: item, item; outro ramo: item'. "
                "Se o usuário só deu o assunto, escreva você 4 a 7 ramos úteis com 2 a 5 itens curtos e chame criar de novo.")
    e = _est()
    k = chave(tema) or norm(tema)
    e["mapas"][k] = {"tema": tema, "ramos": ramos, "ts": time.time()}
    _gravar(e)
    _escrever_e_abrir(tema, ramos)
    itens = sum(len(r["itens"]) for r in ramos)
    return f"Mapa mental '{tema}' aberto: {len(ramos)} ramos e {itens} itens ({', '.join(r['nome'] for r in ramos)})."


def _gravar(e: dict) -> None:
    guardar("mapa_mental", e)


def _adicionar(p, pl):
    e = _est()
    k = _achar(e, p.get("tema"))
    if not k:
        return "Em qual mapa? " + (_listar(p, pl) if e["mapas"] else "Ainda não há mapas: crie um primeiro.")
    novos = ler_ramos(p.get("ramos"))
    if not novos:
        return "O que eu adiciono? Formato: 'ramo: item, item'."
    m = e["mapas"][k]
    m["ramos"] = juntar(m["ramos"], novos)
    m["ts"] = time.time()
    _gravar(e)
    _escrever_e_abrir(m["tema"], m["ramos"])
    return f"Adicionei no mapa '{m['tema']}': " + "; ".join(f"{n['nome']}" + (f" ({', '.join(n['itens'])})" if n["itens"] else "") for n in novos) + "."


def _abrir(p, pl):
    e = _est()
    k = _achar(e, p.get("tema"))
    if not k:
        return "Qual mapa? " + (_listar(p, pl) if e["mapas"] else "Ainda não há mapas.")
    m = e["mapas"][k]
    _escrever_e_abrir(m["tema"], m["ramos"])
    return f"Mapa '{m['tema']}' aberto."


def _listar(p, pl):
    ms = sorted(_est()["mapas"].values(), key=lambda m: -m.get("ts", 0))
    if not ms:
        return "Nenhum mapa mental guardado."
    return "Mapas mentais: " + "; ".join(f"{m['tema']} ({len(m['ramos'])} ramos)" for m in ms[:15]) + "."


def _apagar(p, pl):
    e = _est()
    k = _achar(e, p.get("tema"))
    if not k:
        return "Qual mapa eu apago? Diga o nome."
    tema = e["mapas"].pop(k)["tema"]
    _gravar(e)
    return f"Apaguei o mapa '{tema}'."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"criar": _criar, "adicionar": _adicionar, "abrir": _abrir, "listar": _listar, "apagar": _apagar}, player)
