"""
Quadro de estudos (fork PT-BR 3.2): uma lousa no navegador onde o JARVIS escreve enquanto explica.

    http://127.0.0.1:8770   (só no seu PC/celular — o servidor não aceita conexão de fora)

O JARVIS põe "blocos" no quadro: título, texto, fórmula, passos numerados, lista, código, tabela,
destaque, pergunta (com a resposta escondida até ele revelar) e GRÁFICO de função (calculado aqui,
com uma calculadora segura — nada de eval). A página se atualiza sozinha. Você desenha por cima
com a caneta (cores, borracha), troca lousa ↔ quadro branco e salva tudo como página HTML em
Documentos/JARVIS/Estudos (com o seu desenho junto).

Usado pelo plugin `estudos`. Sem pacote novo: servidor e página são da biblioteca padrão.
"""

from __future__ import annotations

import ast
import base64
import html
import json
import math
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from plugins._lote2 import carregar, guardar

TIPOS = ("titulo", "texto", "formula", "passos", "lista", "codigo", "tabela", "destaque", "pergunta", "grafico")
PORTA_INICIAL = 8770
_lock = threading.RLock()
_srv: dict = {"servidor": None, "porta": None}
_estado: dict | None = None


# ── estado do quadro ──────────────────────────────────────────────────────────
def estado() -> dict:
    global _estado
    with _lock:
        if _estado is None:
            _estado = carregar("quadro", None) or {}
            _estado.setdefault("versao", 1)
            _estado.setdefault("paginas", [{"titulo": "Quadro", "blocos": []}])
            _estado.setdefault("atual", 0)
        return _estado


def _mudou() -> None:
    e = estado()
    e["versao"] += 1
    e["ts"] = time.time()
    guardar("quadro", e)


def pagina() -> dict:
    e = estado()
    return e["paginas"][e["atual"]]


def nova_pagina(titulo: str = "") -> dict:
    with _lock:
        e = estado()
        e["paginas"].append({"titulo": (titulo or f"Página {len(e['paginas']) + 1}")[:120], "blocos": []})
        e["paginas"] = e["paginas"][-30:]
        e["atual"] = len(e["paginas"]) - 1
        _mudou()
        return pagina()


def titulo(texto: str) -> None:
    with _lock:
        pagina()["titulo"] = str(texto)[:120]
        _mudou()


def limpar() -> None:
    with _lock:
        pagina()["blocos"] = []
        _mudou()


def ir_para(indice: int) -> dict:
    with _lock:
        e = estado()
        e["atual"] = max(0, min(len(e["paginas"]) - 1, int(indice)))
        _mudou()
        return pagina()


def escrever(tipo: str, conteudo, **extra) -> dict:
    """Põe um bloco no quadro. conteudo: texto, ou lista (passos/lista), ou linhas 'a|b|c' (tabela)."""
    tipo = tipo if tipo in TIPOS else "texto"
    if tipo in ("passos", "lista") and isinstance(conteudo, str):
        conteudo = [x.strip(" -•\t") for x in re.split(r"\n|;", conteudo) if x.strip(" -•\t")]
    if tipo == "tabela" and isinstance(conteudo, str):
        conteudo = [[c.strip() for c in linha.split("|")] for linha in re.split(r"\n|;", conteudo) if linha.strip()]
    bloco = {"tipo": tipo, "conteudo": conteudo, "ts": time.time(), **{k: v for k, v in extra.items() if v not in (None, "")}}
    with _lock:
        p = pagina()
        p["blocos"].append(bloco)
        p["blocos"] = p["blocos"][-80:]
        _mudou()
    return bloco


def revelar(n: int | None = None) -> int:
    """Mostra a resposta da pergunta n (1, 2…) ou de todas. Devolve quantas revelou."""
    with _lock:
        perguntas = [b for b in pagina()["blocos"] if b["tipo"] == "pergunta"]
        alvo = perguntas if n is None else perguntas[n - 1:n]
        for b in alvo:
            b["revelada"] = True
        if alvo:
            _mudou()
        return len(alvo)


# ── gráfico: calculadora segura ───────────────────────────────────────────────
_FUNCOES = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "sqrt": math.sqrt, "raiz": math.sqrt, "log": math.log,
            "ln": math.log, "log10": math.log10, "exp": math.exp, "abs": abs, "sen": math.sin, "tg": math.tan,
            "floor": math.floor, "ceil": math.ceil}
_CONST = {"pi": math.pi, "e": math.e}
_NOS = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Call, ast.Load, ast.Add, ast.Sub, ast.Mult,
        ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.FloorDiv)


def preparar(expr: str) -> str:
    """'f(x) = 3x² - 2x + 1' → '3*x**2 - 2*x + 1'. Pura."""
    t = str(expr or "").lower().strip()
    t = re.sub(r"^\s*(y|f\s*\(\s*x\s*\))\s*=", "", t)
    t = t.replace("²", "^2").replace("³", "^3").replace("√", "sqrt").replace("π", "pi").replace(",", ".")
    t = t.replace("^", "**").replace("×", "*").replace("÷", "/")
    t = re.sub(r"(\d)\s*([a-z(])", r"\1*\2", t)                 # 3x, 2(  → 3*x, 2*(
    t = re.sub(r"\)\s*([a-z0-9(])", r")*\1", t)                 # )x, )(  → )*x
    t = re.sub(r"\bx\s*\(", "x*(", t)                            # x(x+1)
    return t


def compilar(expr: str):
    arvore = ast.parse(preparar(expr), mode="eval")
    for no in ast.walk(arvore):
        if not isinstance(no, _NOS):
            raise ValueError(f"não aceito '{type(no).__name__}' na função")
        if isinstance(no, ast.Name) and no.id not in _FUNCOES and no.id not in _CONST and no.id != "x":
            raise ValueError(f"não conheço '{no.id}'")
        if isinstance(no, ast.Call) and not (isinstance(no.func, ast.Name) and no.func.id in _FUNCOES):
            raise ValueError("só funções matemáticas simples")
    codigo = compile(arvore, "<funcao>", "eval")
    return lambda x: eval(codigo, {"__builtins__": {}}, {**_FUNCOES, **_CONST, "x": x})   # noqa: S307 (árvore conferida acima)


def pontos(expr: str, de: float = -10, ate: float = 10, n: int = 241) -> list[list[float]]:
    f = compilar(expr)
    de, ate = (float(de), float(ate)) if float(de) < float(ate) else (float(ate), float(de))
    out = []
    for i in range(n):
        x = de + (ate - de) * i / (n - 1)
        try:
            y = float(f(x))
            out.append([round(x, 4), round(y, 4)] if math.isfinite(y) and abs(y) < 1e7 else [round(x, 4), None])
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            out.append([round(x, 4), None])
    return out


def grafico(expr: str, de: float = -10, ate: float = 10) -> dict:
    return escrever("grafico", str(expr), pontos=pontos(expr, de, ate), de=float(de), ate=float(ate))


# ── exportar ──────────────────────────────────────────────────────────────────
def salvar_html(desenho_png: bytes | None = None, nome: str = "") -> str:
    from plugins._comum import pasta_jarvis
    p = pagina()
    pasta = pasta_jarvis("Estudos")
    base = re.sub(r"[^a-z0-9]+", "_", (nome or p["titulo"]).lower())[:40].strip("_") or "quadro"
    arq = pasta / f"{base}_{time.strftime('%Y%m%d_%H%M%S')}.html"
    img = ""
    if desenho_png:
        img = f'<img alt="desenho" src="data:image/png;base64,{base64.b64encode(desenho_png).decode()}" style="max-width:100%">'
    corpo = "".join(_bloco_html(b, exportando=True) for b in p["blocos"])
    arq.write_text(f"<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>{html.escape(p['titulo'])}</title>"
                   f"<style>{_CSS_EXPORT}</style><body><h1>{html.escape(p['titulo'])}</h1>{corpo}{img}"
                   f"<p class='rodape'>Quadro do J.A.R.V.I.S · {time.strftime('%d/%m/%Y %H:%M')}</p></body></html>", encoding="utf-8")
    return str(arq)


def _bloco_html(b: dict, exportando: bool = False) -> str:
    """Versão estática de um bloco (o arquivo salvo). A página ao vivo desenha em JavaScript."""
    t, c = b["tipo"], b.get("conteudo")
    e = lambda x: html.escape(str(x))   # noqa: E731
    if t == "titulo":
        return f"<h2>{e(c)}</h2>"
    if t == "formula":
        return f"<p class='formula'>{e(c)}</p>"
    if t in ("passos", "lista"):
        tag = "ol" if t == "passos" else "ul"
        return f"<{tag}>" + "".join(f"<li>{e(x)}</li>" for x in (c or [])) + f"</{tag}>"
    if t == "codigo":
        return f"<pre>{e(c)}</pre>"
    if t == "tabela":
        return "<table>" + "".join("<tr>" + "".join(f"<td>{e(x)}</td>" for x in linha) + "</tr>" for linha in (c or [])) + "</table>"
    if t == "destaque":
        return f"<p class='destaque'>{e(c)}</p>"
    if t == "pergunta":
        return f"<p><b>Pergunta:</b> {e(c)}</p>" + (f"<p class='resposta'>Resposta: {e(b.get('resposta', ''))}</p>" if b.get("resposta") else "")
    if t == "grafico":
        return f"<p class='formula'>Gráfico de y = {e(c)} (de {b.get('de')} a {b.get('ate')})</p>"
    return f"<p>{e(c)}</p>"


_CSS_EXPORT = ("body{font:17px/1.6 system-ui,sans-serif;max-width:820px;margin:28px auto;padding:0 16px;color:#1d2433}"
               "h1{font-size:28px}h2{margin-top:28px}.formula{font:22px Georgia,serif;text-align:center;margin:18px 0}"
               "pre{background:#f3f5f8;padding:12px;border-radius:8px;overflow:auto}table{border-collapse:collapse}"
               "td{border:1px solid #b9c2d0;padding:6px 10px}.destaque{background:#fff6d8;border-left:4px solid #e0a800;padding:10px}"
               ".resposta{color:#1b7a46}.rodape{color:#8a93a3;font-size:13px;margin-top:40px}")


# ── servidor local ────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, corpo, tipo="application/json; charset=utf-8", codigo=200):
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        caminho = self.path.split("?")[0]
        if caminho in ("/", "/index.html"):
            return self._enviar(PAGINA.encode(), "text/html; charset=utf-8")
        if caminho == "/estado":
            e = estado()
            return self._enviar({"versao": e["versao"], "atual": e["atual"], "total": len(e["paginas"]),
                                 "pagina": pagina(), "pomodoro": _pomodoro()})
        self._enviar({"erro": "não existe"}, codigo=404)

    def do_POST(self):
        if self.path.split("?")[0] != "/salvar":
            return self._enviar({"erro": "não existe"}, codigo=404)
        tam = int(self.headers.get("Content-Length") or 0)
        if tam > 8_000_000:
            return self._enviar({"erro": "desenho grande demais"}, codigo=413)
        try:
            d = json.loads(self.rfile.read(tam) or b"{}")
            png = base64.b64decode(d["desenho"].split(",", 1)[1]) if str(d.get("desenho", "")).startswith("data:image/png") else None
            return self._enviar({"arquivo": salvar_html(png)})
        except Exception as e:
            return self._enviar({"erro": str(e)}, codigo=500)


def _pomodoro() -> dict | None:
    """O pomodoro do plugin `pomodoro` (se estiver rodando) aparece no canto do quadro."""
    import sys
    m = sys.modules.get("plugins.pomodoro")
    e = getattr(m, "_estado", None) if m else None
    if not e or not e.get("fase") or e.get("pausado"):
        return None
    return {"fase": e["fase"], "restante_s": max(0, int(e.get("fim", 0) - time.time()))}


def iniciar_servidor() -> str:
    """Liga o servidor do quadro (uma vez) e devolve o endereço."""
    with _lock:
        if _srv["servidor"] is None:
            for porta in range(PORTA_INICIAL, PORTA_INICIAL + 10):
                try:
                    s = ThreadingHTTPServer(("127.0.0.1", porta), _Handler)
                except OSError:
                    continue
                s.daemon_threads = True
                threading.Thread(target=s.serve_forever, daemon=True, name="quadro").start()
                _srv.update(servidor=s, porta=porta)
                break
            else:
                raise OSError("nenhuma porta livre entre 8770 e 8779")
        return f"http://127.0.0.1:{_srv['porta']}"


def parar_servidor() -> None:
    with _lock:
        s = _srv["servidor"]
        if s is not None:
            s.shutdown()
            s.server_close()
            _srv.update(servidor=None, porta=None)


PAGINA = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Quadro do JARVIS</title>
<style>
:root{--fundo:#16231f;--papel:#1e2f2a;--giz:#eef3ea;--fraco:#9fb3a8;--amarelo:#ffe27a;--azul:#8fd3ff;--verde:#9ff0b3;--rosa:#ff9fb2;--borda:#2f4740}
body.branco{--fundo:#eef1f5;--papel:#ffffff;--giz:#1d2433;--fraco:#677284;--amarelo:#b07d00;--azul:#1769c2;--verde:#178a4a;--rosa:#c2185b;--borda:#d5dbe4}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--giz);font:18px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px;background:var(--fundo);border-bottom:1px solid var(--borda)}
header h1{font-size:18px;margin:0 auto 0 0;letter-spacing:.04em;overflow-wrap:anywhere}
button{font:inherit;font-size:14px;color:var(--giz);background:transparent;border:1px solid var(--borda);border-radius:999px;padding:6px 12px;cursor:pointer}
button.on{background:var(--giz);color:var(--fundo)}.cor{width:26px;height:26px;padding:0;border-radius:50%}
#pomo{font-variant-numeric:tabular-nums;color:var(--amarelo);font-size:14px}
main{position:relative;max-width:920px;margin:16px auto 60px;padding:24px 22px;background:var(--papel);border:1px solid var(--borda);border-radius:14px;min-height:70vh}
#tinta{position:absolute;inset:0;width:100%;height:100%;touch-action:auto;pointer-events:none;border-radius:14px;z-index:2}#blocos{position:relative;z-index:1}@media (max-width:600px){header{gap:6px;padding:8px 12px}header h1{flex-basis:100%;font-size:16px}button{font-size:12px;padding:4px 9px}.cor{width:22px;height:22px}main{margin:10px 8px 40px;padding:16px 14px}.formula{font-size:21px}.titulo{font-size:23px}}
body.desenhando #tinta{pointer-events:auto;touch-action:none;cursor:crosshair}
.b{animation:entra .35s ease-out both;margin:0 0 18px}@keyframes entra{from{opacity:0;transform:translateY(6px)}}
.titulo{font-size:28px;font-weight:700;color:var(--amarelo);margin-top:6px}
.formula{font:26px/1.4 Georgia,"Times New Roman",serif;text-align:center;padding:10px 0;overflow-x:auto}
ol,ul{margin:0;padding-left:28px}li{margin:6px 0}
pre{font:15px/1.5 ui-monospace,Consolas,monospace;background:rgba(0,0,0,.18);padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap}
table{border-collapse:collapse;margin:0 auto}td{border:1px solid var(--borda);padding:6px 12px;text-align:center}tr:first-child td{font-weight:700;color:var(--azul)}
.destaque{border-left:4px solid var(--amarelo);padding:8px 14px;background:rgba(255,226,122,.08)}
.pergunta b{color:var(--azul)}.resposta{color:var(--verde)}.escondida{color:var(--fraco);font-style:italic}
.grafico svg{width:100%;height:auto;display:block}.vazio{color:var(--fraco);text-align:center;margin-top:20vh}
@media (prefers-reduced-motion:reduce){.b{animation:none}}
</style></head><body>
<header><h1 id="tit">Quadro</h1><span id="pomo"></span><span id="pag"></span>
<button id="caneta">✏️ Caneta</button><button class="cor" data-c="#ffe27a" style="background:#ffe27a" aria-label="amarelo"></button>
<button class="cor" data-c="#8fd3ff" style="background:#8fd3ff" aria-label="azul"></button><button class="cor" data-c="#ff9fb2" style="background:#ff9fb2" aria-label="rosa"></button>
<button class="cor" data-c="#ffffff" style="background:#ffffff" aria-label="branco"></button>
<button id="borracha">Borracha</button><button id="apagar">Limpar desenho</button><button id="fundo">Quadro branco</button><button id="salvar">Salvar</button></header>
<main id="quadro"><canvas id="tinta"></canvas><div id="blocos"><p class="vazio">O JARVIS escreve aqui enquanto explica.</p></div></main>
<script>
const $ = s => document.querySelector(s);
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const SUP = {"0":"⁰","1":"¹","2":"²","3":"³","4":"⁴","5":"⁵","6":"⁶","7":"⁷","8":"⁸","9":"⁹","-":"⁻","n":"ⁿ"};
function formula(t) {
  return esc(t).replace(/\^\(?(-?[0-9n]+)\)?/g, (m, g) => [...g].map(c => SUP[c] || c).join(""))
    .replace(/sqrt|raiz/g, "√").replace(/\*/g, "·").replace(/&gt;=/g, "≥").replace(/&lt;=/g, "≤").replace(/!=/g, "≠").replace(/\bpi\b/g, "π").replace(/\+-|\+\/-/g, "±");
}
function grafico(b) {
  const pts = (b.pontos || []).filter(p => p[1] !== null);
  if (!pts.length) return `<p>Não deu para desenhar y = ${esc(b.conteudo)}.</p>`;
  const W = 640, H = 360, P = 36;
  let ys = pts.map(p => p[1]).sort((a, c) => a - c);
  let y0 = ys[Math.floor(ys.length * .02)], y1 = ys[Math.ceil(ys.length * .98) - 1];
  if (y0 === y1) { y0 -= 1; y1 += 1; } const pad = (y1 - y0) * .08; y0 -= pad; y1 += pad;
  const X = x => P + (x - b.de) / (b.ate - b.de) * (W - 2 * P), Y = y => H - P - (y - y0) / (y1 - y0) * (H - 2 * P);
  let d = "", ant = false;
  for (const [x, y] of b.pontos) { if (y === null || y < y0 - (y1 - y0) || y > y1 + (y1 - y0)) { ant = false; continue; } d += (ant ? "L" : "M") + X(x).toFixed(1) + " " + Y(y).toFixed(1); ant = true; }
  const ex = b.de <= 0 && b.ate >= 0 ? X(0) : null, ey = y0 <= 0 && y1 >= 0 ? Y(0) : null;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="gráfico de y = ${esc(b.conteudo)}">
   <rect x="${P}" y="${P}" width="${W - 2 * P}" height="${H - 2 * P}" fill="none" stroke="var(--borda)"/>
   ${ex !== null ? `<line x1="${ex}" y1="${P}" x2="${ex}" y2="${H - P}" stroke="var(--fraco)"/>` : ""}
   ${ey !== null ? `<line x1="${P}" y1="${ey}" x2="${W - P}" y2="${ey}" stroke="var(--fraco)"/>` : ""}
   <path d="${d}" fill="none" stroke="var(--amarelo)" stroke-width="2.5"/>
   <text x="${P}" y="${H - 10}" fill="var(--fraco)" font-size="13">${b.de}</text><text x="${W - P}" y="${H - 10}" fill="var(--fraco)" font-size="13" text-anchor="end">${b.ate}</text>
   <text x="${P + 6}" y="${P + 16}" fill="var(--fraco)" font-size="13">${y1.toFixed(1)}</text><text x="${P + 6}" y="${H - P - 6}" fill="var(--fraco)" font-size="13">${y0.toFixed(1)}</text>
   <text x="${W / 2}" y="${P - 10}" fill="var(--giz)" font-size="16" text-anchor="middle">y = ${formula(b.conteudo)}</text></svg>`;
}
function bloco(b, i) {
  const c = b.conteudo;
  switch (b.tipo) {
    case "titulo": return `<div class="b titulo">${esc(c)}</div>`;
    case "formula": return `<div class="b formula">${formula(c)}</div>`;
    case "passos": return `<ol class="b">${(c || []).map(x => `<li>${esc(x)}</li>`).join("")}</ol>`;
    case "lista": return `<ul class="b">${(c || []).map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
    case "codigo": return `<pre class="b">${esc(c)}</pre>`;
    case "tabela": return `<table class="b">${(c || []).map(l => `<tr>${l.map(x => `<td>${esc(x)}</td>`).join("")}</tr>`).join("")}</table>`;
    case "destaque": return `<div class="b destaque">${esc(c)}</div>`;
    case "pergunta": return `<div class="b pergunta"><b>${i}.</b> ${esc(c)}<br>` + (b.revelada ? `<span class="resposta">✔ ${esc(b.resposta || "")}</span>` : `<span class="escondida">resposta escondida — peça ao JARVIS para revelar</span>`) + `</div>`;
    case "grafico": return `<div class="b grafico">${grafico(b)}</div>`;
    default: return `<p class="b">${esc(c)}</p>`;
  }
}
let versao = 0;
async function atualizar() {
  try {
    const e = await (await fetch("/estado")).json();
    const pm = e.pomodoro; $("#pomo").textContent = pm ? `${pm.fase === "foco" ? "🍅 foco" : "☕ pausa"} ${Math.floor(pm.restante_s / 60)}:${String(pm.restante_s % 60).padStart(2, "0")}` : "";
    if (e.versao === versao) return; versao = e.versao;
    $("#tit").textContent = e.pagina.titulo; document.title = e.pagina.titulo + " · Quadro";
    $("#pag").textContent = e.total > 1 ? `página ${e.atual + 1}/${e.total}` : "";
    let n = 0; const bl = e.pagina.blocos;
    $("#blocos").innerHTML = bl.length ? bl.map(b => bloco(b, b.tipo === "pergunta" ? ++n : 0)).join("") : `<p class="vazio">O JARVIS escreve aqui enquanto explica.</p>`;
    ajustarTinta(); window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  } catch (err) {}
}
const cv = $("#tinta"), cx = cv.getContext("2d"); let cor = "#ffe27a", borracha = false, riscando = false, guardado = null;
function ajustarTinta() {
  const r = $("#quadro").getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (cv.width === Math.round(r.width * dpr) && cv.height === Math.round(r.height * dpr)) return;
  const antes = cv.width ? cv.toDataURL() : null;
  cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr); cx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (antes) { const img = new Image(); img.onload = () => cx.drawImage(img, 0, 0, img.width / dpr, img.height / dpr); img.src = antes; }
}
function ponto(ev) { const r = cv.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; }
cv.addEventListener("pointerdown", ev => { riscando = true; cv.setPointerCapture(ev.pointerId); const [x, y] = ponto(ev); cx.beginPath(); cx.moveTo(x, y); });
cv.addEventListener("pointermove", ev => { if (!riscando) return; const [x, y] = ponto(ev);
  cx.globalCompositeOperation = borracha ? "destination-out" : "source-over"; cx.strokeStyle = cor; cx.lineWidth = borracha ? 22 : 3; cx.lineCap = cx.lineJoin = "round"; cx.lineTo(x, y); cx.stroke(); });
cv.addEventListener("pointerup", () => riscando = false);
$("#caneta").onclick = () => { document.body.classList.toggle("desenhando"); $("#caneta").classList.toggle("on"); borracha = false; $("#borracha").classList.remove("on"); };
$("#borracha").onclick = () => { borracha = !borracha; $("#borracha").classList.toggle("on", borracha); if (borracha && !document.body.classList.contains("desenhando")) $("#caneta").click(); };
document.querySelectorAll(".cor").forEach(b => b.onclick = () => { cor = b.dataset.c; borracha = false; $("#borracha").classList.remove("on"); if (!document.body.classList.contains("desenhando")) $("#caneta").click(); });
$("#apagar").onclick = () => cx.clearRect(0, 0, cv.width, cv.height);
$("#fundo").onclick = () => { document.body.classList.toggle("branco"); $("#fundo").textContent = document.body.classList.contains("branco") ? "Lousa" : "Quadro branco"; };
$("#salvar").onclick = async () => {
  const r = await (await fetch("/salvar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ desenho: cv.toDataURL("image/png") }) })).json();
  $("#salvar").textContent = r.arquivo ? "Salvo ✓" : "Erro"; setTimeout(() => $("#salvar").textContent = "Salvar", 2500);
};
window.addEventListener("resize", ajustarTinta);
atualizar(); setInterval(atualizar, 1200);
</script></body></html>"""
