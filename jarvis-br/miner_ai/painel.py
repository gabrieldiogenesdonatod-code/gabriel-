"""Dashboard do MINER AI: página local (só 127.0.0.1) que se atualiza sozinha a cada 2 s.

GET  /            a página
GET  /api/estado  o estado rotulado em JSON
POST /api/acao    {"acao": "pausar" | "retomar" | "parar"} — exige o cabeçalho X-Token (a página já tem)
"""
from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORTA = 18090
TOKEN = secrets.token_hex(16)
_srv: dict = {"s": None}

HTML = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MINER AI</title>
<style>
:root{--fundo:#f4f6fa;--cartao:#fff;--tinta:#152033;--suave:#5b6b82;--borda:#dde3ec;--real:#0e9f6e;--conf:#2563eb;--pend:#b7791f;--sim:#7c3aed;--custo:#dc2626}
@media (prefers-color-scheme:dark){:root{--fundo:#070c16;--cartao:#0f1726;--tinta:#e6edf7;--suave:#8fa1ba;--borda:#1f2b40;--real:#34d399;--conf:#60a5fa;--pend:#fbbf24;--sim:#a78bfa;--custo:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--tinta);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:18px 16px 40px}
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px}
h1{font-size:20px;margin:0;letter-spacing:.5px}h1 b{color:var(--real)}
.pilula{padding:4px 10px;border-radius:999px;font-size:13px;border:1px solid var(--borda);background:var(--cartao)}
.acoes{margin-left:auto;display:flex;gap:8px}
button{font:inherit;padding:7px 14px;border-radius:9px;border:1px solid var(--borda);background:var(--cartao);color:var(--tinta);cursor:pointer}
button.perigo{border-color:var(--custo);color:var(--custo)}
.grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.c{background:var(--cartao);border:1px solid var(--borda);border-radius:12px;padding:12px 14px}
.c small{display:block;color:var(--suave);font-size:12px;text-transform:uppercase;letter-spacing:.6px}
.c strong{display:block;font-size:22px;margin-top:2px;font-variant-numeric:tabular-nums}
.c span{color:var(--suave);font-size:12px}
h2{font-size:14px;margin:18px 0 8px;color:var(--suave);text-transform:uppercase;letter-spacing:.8px}
.c .rot,.rot{display:inline-block;color:#fff;font-size:11px;font-weight:700;padding:1px 7px;border-radius:5px;margin-right:6px;color:#fff;vertical-align:middle}
.real{background:var(--real)}.conf{background:var(--conf)}.c .pend,.pend{background:var(--pend);color:#1a1300}.sim{background:var(--sim)}.custo{background:var(--custo)}
#grafico{width:100%;height:90px}
ul{margin:6px 0 0;padding-left:20px}li{margin:4px 0}
.aviso{border-left:4px solid var(--pend);padding:8px 12px;background:var(--cartao);border-radius:8px;margin:10px 0}
table{width:100%;min-width:520px;border-collapse:collapse;font-size:13px}td,th{padding:6px;border-bottom:1px solid var(--borda);text-align:left}
</style></head><body><main>
<header><h1>MINER <b>AI</b></h1><span class="pilula" id="status">carregando…</span><span class="pilula" id="moeda"></span>
<div class="acoes"><button onclick="acao('pausar')">Pausar</button><button onclick="acao('retomar')">Retomar</button>
<button class="perigo" onclick="acao('parar')">Parar</button></div></header>
<div class="aviso" id="pausa" hidden></div>
<h2>Desempenho</h2>
<div class="grade">
 <div class="c"><small>Hashrate</small><strong id="hs">—</strong><span id="hs2"></span></div>
 <div class="c"><small>Temperatura</small><strong id="temp">—</strong><span id="temp2"></span></div>
 <div class="c"><small>Consumo</small><strong id="watts">—</strong><span id="watts2"></span></div>
 <div class="c"><small>Tempo</small><strong id="tempo">—</strong><span id="tempo2"></span></div>
</div>
<div class="c" style="margin-top:10px"><small>Hashrate (últimos minutos)</small><svg id="grafico" viewBox="0 0 300 90" preserveAspectRatio="none"></svg></div>
<h2>Dinheiro — cada número com o seu rótulo</h2>
<div class="grade">
 <div class="c"><small><span class="rot real">REAL</span>shares aceitos</small><strong id="shares">—</strong><span id="shares2"></span></div>
 <div class="c"><small><span class="rot conf">CONFIRMADO</span>saldo</small><strong id="conf">—</strong><span id="conf2"></span></div>
 <div class="c"><small><span class="rot pend">PENDENTE</span>a receber</small><strong id="pend">—</strong><span id="pend2"></span></div>
 <div class="c"><small><span class="rot custo">CUSTO</span>energia</small><strong id="custo">—</strong><span id="custo2"></span></div>
 <div class="c"><small><span class="rot sim">SIMULAÇÃO</span>lucro/prejuízo</small><strong id="lucro">—</strong><span id="lucro2"></span></div>
</div>
<h2>Cérebro</h2>
<div class="c"><div id="veredito"></div><ul id="dicas"></ul></div>
<h2>Últimas sessões</h2>
<div class="c" style="overflow-x:auto"><table><thead><tr><th>Moeda</th><th>Horas</th><th>Shares</th><th>kWh</th><th>Luz</th><th>Esperado (sim.)</th><th>Parou por</th></tr></thead><tbody id="sess"></tbody></table></div>
</main>
<script>
const TOKEN = "__TOKEN__", serie = [];
const brl = v => v == null ? "—" : (v < 0 ? "−" : "") + "R$ " + Math.abs(v).toLocaleString("pt-BR", {minimumFractionDigits: 2, maximumFractionDigits: Math.abs(v) < 0.01 ? 6 : 2});
const hs = v => v >= 1e6 ? (v / 1e6).toFixed(2) + " MH/s" : v >= 1e3 ? (v / 1e3).toFixed(1) + " kH/s" : (v || 0).toFixed(0) + " H/s";
const dur = s => { s = Math.floor(s || 0); return `${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}m`; };
const $ = id => document.getElementById(id);
async function acao(a) {
  if (a === "parar" && !confirm("Parar a mineração?")) return;
  await fetch("/api/acao", {method: "POST", headers: {"X-Token": TOKEN, "Content-Type": "application/json"}, body: JSON.stringify({acao: a})});
  atualizar();
}
function grafico() {
  const g = $("grafico"), max = Math.max(1, ...serie);
  const pts = serie.map((v, i) => `${(i / Math.max(1, serie.length - 1)) * 300},${88 - v / max * 80}`).join(" ");
  g.innerHTML = serie.length > 1 ? `<polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--real)"/>` : "";
}
async function atualizar() {
  let e;
  try { e = await (await fetch("/api/estado")).json(); } catch (x) { $("status").textContent = "sem conexão com o MINER AI"; return; }
  const d = e.desempenho, moeda = e.moeda ? e.moeda.toUpperCase() : "";
  $("status").textContent = !e.rodando ? "parado" : d.pausado ? "pausado" : d.conectado ? "minerando" : "conectando à pool…";
  $("moeda").textContent = e.rodando ? `${e.nome_moeda} · ${e.endereco}` : "nenhuma moeda";
  $("pausa").hidden = !d.motivo_pausa && !d.regulagem;
  $("pausa").textContent = d.motivo_pausa ? "Pausado: " + d.motivo_pausa : d.regulagem;
  $("hs").textContent = hs(d.hashrate); $("hs2").textContent = e.rodando ? `${d.threads} núcleo(s) · CPU ${Math.round(d.carga)}%` : "";
  $("temp").textContent = d.temperatura == null ? "—" : d.temperatura.toFixed(0) + " °C";
  $("temp2").textContent = d.temperatura == null ? "o sistema não informa" : `limite ${e.config.temperatura_max} °C`;
  $("watts").textContent = d.watts.toFixed(1) + " W"; $("watts2").textContent = e.custos.watts_fonte;
  $("tempo").textContent = dur(d.tempo_s); $("tempo2").textContent = "minerando " + dur(d.minerando_s);
  $("shares").textContent = e.real.shares_aceitos; $("shares2").textContent = `${e.real.shares_rejeitados} recusados · ${e.real.blocos} bloco(s) · ${e.real.explicacao}`;
  const un = moeda || "";
  $("conf").textContent = e.confirmado.valor == null ? "—" : `${e.confirmado.valor} ${un}`;
  $("conf2").textContent = e.confirmado.valor == null ? "ainda não consultado" : `${e.confirmado.o_que_e} · ${e.confirmado.fonte}`;
  $("pend").textContent = e.pendente.valor == null ? "—" : `${e.pendente.valor} ${un}`;
  $("pend2").textContent = e.pendente.valor == null ? "" : `${e.pendente.o_que_e} · ${e.pendente.fonte}`;
  $("custo").textContent = brl(e.custos.reais); $("custo2").textContent = `${e.custos.kwh.toFixed(4)} kWh a ${brl(e.custos.tarifa)}/kWh`;
  const r = e.resultado_estimado.reais;
  $("lucro").textContent = brl(r); $("lucro").style.color = r == null ? "" : r >= 0 ? "var(--real)" : "var(--custo)";
  $("lucro2").textContent = e.resultado_estimado.o_que_e;
  const sims = e.simulacao.moedas;
  $("veredito").innerHTML = Object.values(sims).map(s => `<p><span class="rot sim">SIMULAÇÃO</span>${s.veredito}</p>`).join("");
  $("dicas").innerHTML = e.recomendacoes.map(t => `<li>${t.replace(/</g, "&lt;")}</li>`).join("");
  $("sess").innerHTML = e.sessoes.slice().reverse().map(s => `<tr><td>${s.moeda.toUpperCase()}</td><td>${s.horas.toFixed(2)}</td><td>${s.shares}</td><td>${s.kwh.toFixed(3)}</td><td>${brl(s.custo)}</td><td>${brl(s.esperado_reais)}</td><td>${s.motivo}</td></tr>`).join("") || "<tr><td colspan=7>nenhuma ainda</td></tr>";
  if (e.rodando) { serie.push(d.hashrate); if (serie.length > 90) serie.shift(); grafico(); }
}
atualizar(); setInterval(atualizar, 2000);
</script></body></html>"""


def _json_seguro(o):
    def limpar(x):
        if isinstance(x, float) and (x != x or x in (float("inf"), float("-inf"))):
            return None
        if isinstance(x, dict):
            return {k: limpar(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [limpar(v) for v in x]
        return x
    return json.dumps(limpar(o), ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    ctl = None

    def log_message(self, *a):
        pass

    def _enviar(self, cod: int, corpo: bytes, tipo: str) -> None:
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._enviar(200, HTML.replace("__TOKEN__", TOKEN).encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/estado":
            self._enviar(200, _json_seguro(self.ctl.estado()), "application/json")
        else:
            self._enviar(404, b"{}", "application/json")

    def do_POST(self):
        if self.path != "/api/acao" or self.headers.get("X-Token") != TOKEN:
            self._enviar(403, b'{"erro": "sem permissao"}', "application/json")
            return
        try:
            a = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}").get("acao")
        except ValueError:
            a = None
        fn = {"pausar": self.ctl.pausar, "retomar": self.ctl.retomar, "parar": self.ctl.parar}.get(a)
        self._enviar(200 if fn else 400, _json_seguro({"resposta": fn() if fn else "ação desconhecida"}), "application/json")


def iniciar(ctl, porta: int = PORTA) -> str:
    """Sobe o painel (uma vez) e devolve o endereço."""
    if _srv["s"] is None:
        Handler.ctl = ctl
        s = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True, name="miner-ai-painel").start()
        _srv["s"] = s
    return f"http://127.0.0.1:{_srv['s'].server_address[1]}/"


def parar() -> None:
    if _srv["s"] is not None:
        _srv["s"].shutdown()
        _srv["s"].server_close()
        _srv["s"] = None
