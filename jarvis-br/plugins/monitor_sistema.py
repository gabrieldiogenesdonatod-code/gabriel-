"""
Monitoramento completo do PC — plugin do J.A.R.V.I.S BR.

Lê tudo do core/telemetria.py (a fonte única de métricas, a mesma do HUD) e
acrescenta:
    * respostas por voz: "como está o PC?", "o que está pesando?", "como está a
      internet?", "quem está usando minha rede?", "faz um teste de velocidade",
      "mostra o top de processos", "como foi o PC hoje?";
    * ações em processos: finalizar (com confirmação), suspender, retomar,
      mudar prioridade e abrir o local do arquivo;
    * alertas falados e configuráveis (CPU, RAM, disco, temperatura, internet,
      ping, bateria), registrados no histórico;
    * histórico em SQLite (memory/monitor.db), uma amostra por minuto.

O painel 📊 MONITOR (core/painel_monitor.py) mostra os mesmos dados ao vivo.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from plugins import _monitor_db as db
from plugins import _processos as proc_ops
from plugins._comum import (avisar, br, cfg, confirmar, duracao, mostrar, num,
                            plugin_ligado, registrar, sim, tamanho, velocidade)

PLUGIN = {
    "name": "monitor_sistema",
    "brief": "PC status, heavy processes, internet, network devices, speed test, disks, daily report, process actions.",
    "description": (
        "Full PC monitoring. action='status' for 'como está o PC', overall "
        "health, CPU/RAM/GPU/temperature/disk. action='pesando' for 'o que está "
        "pesando / deixando lento'. action='top' to show the process table "
        "(ordem: cpu | ram | disco | rede). action='internet' for internet/Wi-Fi/"
        "ping/IP questions. action='rede_local' for 'quem está na minha rede'. "
        "action='velocidade' to run a speed test. action='discos' for disk space "
        "and health. action='relatorio' for 'como foi o PC hoje / essa semana' "
        "(periodo: hoje | semana). action='eventos' for recent alerts. "
        "action='processo' to act on a program: operacao = finalizar | suspender "
        "| retomar | prioridade | abrir_local, alvo = name or PID, nivel for "
        "prioridade (baixa | abaixo | normal | acima | alta). "
        "action='painel' opens the 📊 MONITOR window. "
        "Prefer this over system_status for anything beyond a one-line check."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "status | pesando | top | internet | rede_local | "
                                      "velocidade | discos | relatorio | eventos | "
                                      "processo | painel"},
            "ordem": {"type": "STRING", "description": "top: cpu | ram | disco | rede"},
            "periodo": {"type": "STRING", "description": "relatorio: hoje | semana"},
            "operacao": {"type": "STRING",
                         "description": "processo: finalizar | suspender | retomar | "
                                        "prioridade | abrir_local"},
            "alvo": {"type": "STRING", "description": "processo: program name or PID"},
            "nivel": {"type": "STRING", "description": "prioridade level"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "monitor_sistema",
    "title": "Monitor do PC (alertas e histórico)",
    "fields": [
        {"key": "alertas", "label": "Alertas falados", "type": "toggle", "default": True},
        {"key": "cpu_limite", "label": "CPU acima de (%)", "type": "text", "default": "90"},
        {"key": "cpu_segundos", "label": "…por quantos segundos", "type": "text", "default": "30"},
        {"key": "ram_limite", "label": "RAM acima de (%)", "type": "text", "default": "85"},
        {"key": "disco_limite", "label": "Disco com menos de (% livre)", "type": "text", "default": "10"},
        {"key": "temp_limite", "label": "Temperatura acima de (°C)", "type": "text", "default": "85"},
        {"key": "ping_limite", "label": "Ping acima de (ms)", "type": "text", "default": "150"},
        {"key": "bateria_limite", "label": "Bateria abaixo de (%)", "type": "text", "default": "15"},
        {"key": "avisar_internet", "label": "Avisar quando a internet cair ou voltar",
         "type": "toggle", "default": True},
        {"key": "intervalo_min", "label": "Minutos entre avisos repetidos", "type": "text", "default": "10"},
        {"key": "historico", "label": "Gravar histórico (memory/monitor.db)", "type": "toggle", "default": True},
        {"key": "retencao_dias", "label": "Guardar histórico por (dias)", "type": "text", "default": "30"},
    ],
}


def _cfg() -> dict:
    return cfg("monitor_sistema", PLUGIN_SETTINGS)


def _tel():
    from core import telemetria
    return telemetria.get()


# ── textos ─────────────────────────────────────────────────────────────────────
def _pct(v) -> str:
    return "—" if v is None else f"{br(v, 0)}%"


def _graus(v) -> str:
    return "—" if v is None else f"{br(v, 0)} °C"


def texto_status(s: dict) -> tuple[str, str]:
    """(frase falada, painel detalhado)."""
    ram, gpu = s.get("ram") or {}, s.get("gpu")
    procs = s.get("processos") or []
    topo = procs[0] if procs else None
    partes = [f"CPU em {_pct(s.get('cpu'))}"]
    if s.get("cpu_temp") is not None:
        partes[-1] += f" a {_graus(s['cpu_temp'])}"
    partes.append(f"RAM em {_pct(ram.get('pct'))} ({tamanho(ram.get('usada', 0))} de "
                  f"{tamanho(ram.get('total', 0))})")
    if gpu:
        partes.append(f"GPU em {_pct(gpu.get('uso'))}" +
                      (f" a {_graus(gpu['temp'])}" if gpu.get("temp") is not None else ""))
    cheios = [p for p in s.get("particoes", []) if 100 - p["pct"] < 10]
    if cheios:
        partes.append("pouco espaço em " + ", ".join(p["ponto"] for p in cheios))
    if s.get("internet") is False:
        partes.append("sem internet")
    frase = "; ".join(partes) + "."
    if topo and topo["cpu"] >= 10:
        frase += f" Quem mais usa CPU agora: {topo['nome']} ({_pct(topo['cpu'])})."

    linhas = [
        f"CPU      {_pct(s.get('cpu'))}   {s.get('cpu_nucleos_fisicos')} núcleos / "
        f"{s.get('cpu_nucleos_logicos')} threads   {s.get('cpu_freq_mhz') or '—'} MHz   "
        f"temp {_graus(s.get('cpu_temp'))}",
        "núcleos  " + " ".join(f"{br(v, 0)}" for v in s.get("cpu_nucleos", [])),
        f"RAM      {_pct(ram.get('pct'))}   usada {tamanho(ram.get('usada', 0))}   "
        f"livre {tamanho(ram.get('livre', 0))}   cache {tamanho(ram.get('cache', 0))}",
        f"Swap     {_pct((s.get('swap') or {}).get('pct'))}   "
        f"{tamanho((s.get('swap') or {}).get('usada', 0))}",
    ]
    if gpu:
        linhas.append(f"GPU      {gpu.get('nome', '')}   uso {_pct(gpu.get('uso'))}   VRAM "
                      f"{tamanho(gpu.get('vram_usada', 0))}/{tamanho(gpu.get('vram_total', 0))}   "
                      f"{_graus(gpu.get('temp'))}   {gpu.get('clock_mhz') or '—'} MHz")
    else:
        linhas.append("GPU      sem GPU NVIDIA (ou driver sem NVML)")
    io = s.get("disco_io") or {}
    linhas.append(f"Disco    leitura {velocidade(io.get('leitura', 0))}   "
                  f"escrita {velocidade(io.get('escrita', 0))}")
    for p in s.get("particoes", []):
        linhas.append(f"  {p['ponto']:<12} {_pct(p['pct'])} usado   livre {tamanho(p['livre'])} "
                      f"de {tamanho(p['total'])}")
    rede = s.get("rede") or {}
    linhas.append(f"Rede     ↓ {velocidade(rede.get('down', 0))}   ↑ {velocidade(rede.get('up', 0))}   "
                  f"hoje ↓ {tamanho(s['rede_hoje']['down'])} ↑ {tamanho(s['rede_hoje']['up'])}")
    b = s.get("bateria")
    if b:
        linhas.append(f"Bateria  {_pct(b['pct'])} {'(na tomada)' if b['na_tomada'] else ''}"
                      + (f"   resta {duracao(b['restante_s'])}" if b.get("restante_s") else ""))
    for v in s.get("ventoinhas", []):
        linhas.append(f"Ventoinha {v['nome']}: {v['rpm']} RPM")
    linhas.append(f"Ligado há {duracao(s.get('uptime', 0))}   {s.get('total_processos')} processos")
    return frase, "\n".join(linhas)


def ordenar_processos(procs: list[dict], ordem: str) -> list[dict]:
    chave = {"ram": "ram", "memoria": "ram", "memória": "ram", "disco": "disco",
             "rede": "conexoes", "conexoes": "conexoes"}.get(str(ordem or "").lower(), "cpu")
    return sorted(procs, key=lambda p: p.get(chave) or 0, reverse=True)


def tabela_processos(procs: list[dict], n: int = 15) -> str:
    linhas = [f"{'PID':>7}  {'NOME':<26} {'CPU':>6} {'RAM':>10} {'DISCO':>11} {'CONEX':>5} "
              f"{'THR':>4}  {'USUÁRIO':<12} TEMPO"]
    agora = time.time()
    for p in procs[:n]:
        linhas.append(f"{p['pid']:>7}  {p['nome'][:26]:<26} {br(p['cpu'], 1):>5}% "
                      f"{tamanho(p['ram']):>10} {velocidade(p['disco']):>11} "
                      f"{p.get('conexoes', 0):>5} {p['threads']:>4}  {p['usuario'][:12]:<12} "
                      f"{duracao(agora - p['inicio']) if p['inicio'] else '—'}")
    return "\n".join(linhas)


def _pesando(s: dict) -> str:
    procs = s.get("processos") or []
    por_cpu = [p for p in ordenar_processos(procs, "cpu")[:3] if p["cpu"] >= 3]
    por_ram = ordenar_processos(procs, "ram")[:3]
    partes = []
    if por_cpu:
        partes.append("Na CPU: " + ", ".join(f"{p['nome']} {_pct(p['cpu'])}" for p in por_cpu))
    else:
        partes.append("Nenhum programa está forçando a CPU agora")
    partes.append("Na memória: " + ", ".join(f"{p['nome']} {tamanho(p['ram'])}" for p in por_ram))
    io = sorted(procs, key=lambda p: p["disco"], reverse=True)[:1]
    if io and io[0]["disco"] > 5 * 1024 * 1024:
        partes.append(f"No disco: {io[0]['nome']} {velocidade(io[0]['disco'])}")
    return ". ".join(partes) + "."


def _internet(s: dict) -> tuple[str, str]:
    ping = s.get("ping") or {}
    wifi = s.get("wifi") or {}
    rede = s.get("rede") or {}

    def pg(nome):
        p = ping.get(nome) or {}
        if p.get("ms") is None:
            return "sem resposta"
        return f"{br(p['ms'], 0)} ms" + (f" ({br(p['perda'], 0)}% perda)" if p.get("perda") else "")

    if s.get("internet") is False:
        frase = "Estou sem internet agora."
        if (ping.get("gateway") or {}).get("ms") is not None:
            frase += " O roteador responde, então o problema parece ser da operadora."
        elif s.get("gateway"):
            frase += " Nem o roteador responde: confira o cabo ou o Wi-Fi."
    else:
        frase = f"Internet funcionando. Ping {pg('8.8.8.8')} para o Google."
    if wifi.get("ssid"):
        frase += f" Wi-Fi {wifi['ssid']}" + (f" com sinal de {wifi['sinal']}%." if wifi.get("sinal") is not None else ".")
    frase += (f" Agora: ↓ {velocidade(rede.get('down', 0))} e ↑ {velocidade(rede.get('up', 0))}.")

    linhas = [
        f"IP local    {s.get('ip_local') or '—'}",
        f"IP público  {s.get('ip_publico') or '—'}",
        f"Gateway     {s.get('gateway') or '—'}   ping {pg('gateway')}",
        f"DNS         {', '.join(s.get('dns') or []) or '—'}",
        f"Google DNS  8.8.8.8   ping {pg('8.8.8.8')}",
        f"Cloudflare  1.1.1.1   ping {pg('1.1.1.1')}",
        f"Wi-Fi       {wifi.get('ssid') or '—'}   sinal {wifi.get('sinal') if wifi.get('sinal') is not None else '—'}%",
        f"Hoje        ↓ {tamanho(s['rede_hoje']['down'])}   ↑ {tamanho(s['rede_hoje']['up'])}",
        "",
        "INTERFACES",
    ]
    for nome, i in sorted(rede.get("interfaces", {}).items()):
        linhas.append(f"  {nome[:24]:<24} ↓ {velocidade(i['down']):>11}   ↑ {velocidade(i['up']):>11}")
    return frase, "\n".join(linhas)


def _rede_local(player) -> str:
    from core import telemetria
    registrar(player, "Procurando aparelhos na sua rede local…")
    lista = telemetria.dispositivos_rede(varrer=True)
    if not lista:
        return "Não consegui identificar sua rede local."
    outros = [d for d in lista if d["papel"] != "este PC"]
    linhas = [f"{'IP':<16} {'MAC':<18} {'NOME':<30} PAPEL"]
    for d in lista:
        linhas.append(f"{d['ip']:<16} {d['mac'] or '—':<18} {(d['nome'] or '—')[:30]:<30} {d['papel']}")
    mostrar(player, f"REDE LOCAL — {len(lista)} APARELHOS", "\n".join(linhas))
    nomes = [d["nome"].split(".")[0] for d in outros if d["nome"]][:5]
    return (f"Encontrei {len(outros)} aparelho(s) na sua rede além deste PC"
            + (f", entre eles: {', '.join(nomes)}" if nomes else "")
            + ". A lista está no painel. Aparelhos que bloqueiam tudo podem não aparecer.")


def _velocidade(player) -> str:
    from core import telemetria
    registrar(player, "Teste de velocidade em andamento (uns 15 segundos)…")
    r = telemetria.teste_velocidade()
    if r.get("erro") and r.get("down_mbps") is None:
        return f"O teste de velocidade falhou: {r['erro']}"
    texto = (f"Download {br(r['down_mbps'] or 0)} Mbps, upload "
             f"{br(r['up_mbps'] or 0)} Mbps" +
             (f", ping {br(r['ping_ms'], 0)} ms" if r.get("ping_ms") else "") + ".")
    db.gravar_evento("velocidade", texto)
    return texto + " Medido contra o servidor da Cloudflare."


def _discos(s: dict) -> tuple[str, str]:
    from core import telemetria
    saude = telemetria.saude_discos()
    partes = []
    linhas = []
    for p in s.get("particoes", []):
        livre_pct = 100 - p["pct"]
        partes.append(f"{p['ponto']} com {tamanho(p['livre'])} livres ({br(livre_pct, 0)}%)")
        linhas.append(f"{p['ponto']:<12} {p['tipo']:<6} {_pct(p['pct'])} usado   livre "
                      f"{tamanho(p['livre'])} de {tamanho(p['total'])}")
    if saude:
        linhas.append("")
        linhas.append("SAÚDE (SMART)")
        for d in saude:
            linhas.append(f"  {d['disco']}: {d['saude']}  {d['detalhe']}")
        ruins = [d for d in saude if d["saude"] != "saudável"]
        partes.append(("Atenção: " + ", ".join(f"{d['disco']} {d['saude']}" for d in ruins))
                      if ruins else "saúde dos discos ok")
    else:
        linhas.append("\nSaúde SMART não disponível neste sistema.")
    return "; ".join(partes) + ".", "\n".join(linhas)


def _relatorio(periodo: str, player) -> str:
    agora = datetime.now()
    if str(periodo or "").lower().startswith("semana"):
        desde, nome = agora - timedelta(days=7), "nos últimos 7 dias"
    else:
        desde, nome = agora.replace(hour=0, minute=0, second=0, microsecond=0), "hoje"
    r = db.resumo(desde.timestamp())
    if not r.get("amostras"):
        return (f"Ainda não tenho histórico {nome}. O histórico começa a ser gravado "
                "com o plugin ligado, uma amostra por minuto.")
    alertas = [e for e in r["eventos"] if e["tipo"].startswith("alerta")]
    quedas = [e for e in r["eventos"] if e["tipo"] == "internet_caiu"]
    frase = (f"{nome.capitalize()}: CPU média de {_pct(r['cpu_media'])} com pico de "
             f"{_pct(r['cpu_max'])}, RAM média de {_pct(r['ram_media'])}")
    if r.get("temp_max"):
        frase += f", temperatura máxima de {_graus(r['temp_max'])}"
    frase += f". Internet: ↓ {tamanho(r['total_down'])} e ↑ {tamanho(r['total_up'])}"
    frase += (f", {len(quedas)} queda(s)" if quedas else ", sem quedas")
    frase += f". {len(alertas)} alerta(s)." if alertas else ". Nenhum alerta."

    linhas = [f"Período: {nome}  ({r['minutos_ligado']} minutos registrados)",
              f"CPU        média {_pct(r['cpu_media'])}   pico {_pct(r['cpu_max'])}",
              f"RAM        média {_pct(r['ram_media'])}   pico {_pct(r['ram_max'])}",
              f"GPU        média {_pct(r['gpu_media'])}   pico {_pct(r['gpu_max'])}",
              f"Temp.      média {_graus(r['temp_media'])}   máx {_graus(r['temp_max'])}",
              f"Ping       médio {br(r['ping_medio'] or 0, 0)} ms   máx {br(r['ping_max'] or 0, 0)} ms",
              f"Disco      menor espaço livre {_pct(r['disco_livre_min'])}",
              f"Rede       ↓ {tamanho(r['total_down'])}   ↑ {tamanho(r['total_up'])}",
              f"Sem internet: {r['minutos_sem_internet']} min", "", "EVENTOS"]
    for e in r["eventos"][:25]:
        linhas.append(f"  {datetime.fromtimestamp(e['ts']).strftime('%d/%m %H:%M')}  {e['mensagem']}")
    mostrar(player, f"RELATÓRIO DO PC — {nome.upper()}", "\n".join(linhas))
    return frase


def _processo(p: dict, player) -> str:
    op = str(p.get("operacao") or "").strip().lower()
    alvo = str(p.get("alvo") or "").strip()
    if not alvo:
        return "Qual programa ou PID?"
    procs = proc_ops.achar(alvo)
    if not procs:
        return f"Não encontrei nenhum processo chamado {alvo}."
    if op in ("finalizar", "matar", "fechar", "encerrar", "kill"):
        ok, recusados = proc_ops.separar_protegidos(procs)
        if not ok:
            return "Não posso finalizar: " + "; ".join(recusados) + "."
        nomes = proc_ops.descrever(ok)
        pids = [x.pid for x in ok]
        return confirmar(
            f"finalizar-{alvo}", f"Finalizar {nomes}",
            f"{len(ok)} processo(s). O que não foi salvo nesses programas será perdido.",
            lambda: proc_ops.finalizar(proc_ops.achar_pids(pids)))
    if op in ("suspender", "pausar", "congelar"):
        return proc_ops.suspender(procs)
    if op in ("retomar", "continuar", "descongelar"):
        return proc_ops.retomar(procs)
    if op in ("prioridade", "prioridade_baixa", "prioridade_alta"):
        nivel = p.get("nivel") or op.replace("prioridade_", "").replace("prioridade", "")
        return proc_ops.prioridade(procs, nivel)
    if op in ("abrir_local", "local", "pasta"):
        return proc_ops.abrir_local(procs[0])
    return "Operação desconhecida. Use finalizar, suspender, retomar, prioridade ou abrir_local."


# ── alertas ────────────────────────────────────────────────────────────────────
class Vigia:
    """Regras de alerta. `avaliar` é pura (recebe o tempo), para dar para testar."""

    def __init__(self):
        self.cpu_desde: float | None = None
        self.ultimo: dict[str, float] = {}
        self.internet: bool | None = None
        self.internet_contagem = 0
        self.ping_alto = 0

    def _pode(self, chave: str, agora: float, intervalo: float) -> bool:
        if agora - self.ultimo.get(chave, -1e9) < intervalo:
            return False
        self.ultimo[chave] = agora
        return True

    def avaliar(self, s: dict, c: dict, agora: float) -> list[tuple[str, str]]:
        alertas: list[tuple[str, str]] = []
        intervalo = max(1.0, num(c.get("intervalo_min"), 10)) * 60

        cpu = float(s.get("cpu") or 0)
        if cpu >= num(c.get("cpu_limite"), 90):
            self.cpu_desde = self.cpu_desde if self.cpu_desde is not None else agora
            if agora - self.cpu_desde >= num(c.get("cpu_segundos"), 30) and \
                    self._pode("cpu", agora, intervalo):
                topo = (s.get("processos") or [{}])[0]
                quem = f" O maior consumo é do {topo.get('nome')}." if topo.get("nome") else ""
                alertas.append(("alerta_cpu", f"A CPU está em {br(cpu, 0)}% há mais de "
                                              f"{br(num(c.get('cpu_segundos'), 30), 0)} segundos.{quem}"))
        else:
            self.cpu_desde = None

        ram = float((s.get("ram") or {}).get("pct") or 0)
        if ram >= num(c.get("ram_limite"), 85) and self._pode("ram", agora, intervalo):
            alertas.append(("alerta_ram", f"A memória RAM está em {br(ram, 0)}%."))

        for p in s.get("particoes", []):
            livre = 100 - float(p.get("pct") or 0)
            if livre < num(c.get("disco_limite"), 10) and \
                    self._pode(f"disco{p['ponto']}", agora, max(intervalo, 3600)):
                alertas.append(("alerta_disco", f"O disco {p['ponto']} está com só "
                                                f"{br(livre, 0)}% livre ({tamanho(p['livre'])})."))

        limite_t = num(c.get("temp_limite"), 85)
        t = s.get("cpu_temp")
        if t is not None and t >= limite_t and self._pode("temp", agora, intervalo):
            alertas.append(("alerta_temp", f"A CPU está a {br(t, 0)} graus."))
        g = s.get("gpu") or {}
        if g.get("temp") is not None and g["temp"] >= limite_t and self._pode("gpu_temp", agora, intervalo):
            alertas.append(("alerta_temp", f"A placa de vídeo está a {br(g['temp'], 0)} graus."))

        net = s.get("internet")
        if net is not None and sim(c.get("avisar_internet", True)):
            if self.internet is None:
                self.internet = net
            elif net != self.internet:
                self.internet_contagem += 1
                # Duas leituras seguidas (~1 min) antes de anunciar: um ping
                # perdido não é queda.
                if self.internet_contagem >= 2:
                    self.internet, self.internet_contagem = net, 0
                    if net:
                        alertas.append(("internet_voltou", "A internet voltou."))
                    else:
                        alertas.append(("internet_caiu", "A internet caiu."))
            else:
                self.internet_contagem = 0

        ping = ((s.get("ping") or {}).get("8.8.8.8") or {}).get("ms")
        if ping is not None and ping > num(c.get("ping_limite"), 150):
            self.ping_alto += 1
            if self.ping_alto >= 3 and self._pode("ping", agora, intervalo):
                alertas.append(("alerta_ping", f"O ping está alto: {br(ping, 0)} ms."))
        else:
            self.ping_alto = 0

        b = s.get("bateria")
        if b and not b.get("na_tomada") and b["pct"] <= num(c.get("bateria_limite"), 15) \
                and self._pode("bateria", agora, intervalo):
            alertas.append(("alerta_bateria", f"A bateria está em {br(b['pct'], 0)}%. "
                                              "Melhor ligar na tomada."))
        return alertas


_vigia_thread: threading.Thread | None = None
_parar = threading.Event()


def _laco_vigia(player) -> None:
    vigia = Vigia()
    ultima_amostra = 0.0
    ultima_limpeza = 0.0
    tel = _tel()
    while not _parar.wait(5.0):
        if not plugin_ligado("monitor_sistema"):
            continue
        try:
            c = _cfg()
            s = tel.snapshot()
            agora = time.monotonic()
            if sim(c.get("alertas", True)):
                for tipo, msg in vigia.avaliar(s, c, agora):
                    db.gravar_evento(tipo, msg)
                    avisar(player, msg, "ALERTA DO SISTEMA")
            elif s.get("internet") is not None:
                vigia.avaliar(s, {**c, "avisar_internet": False}, agora)
            if sim(c.get("historico", True)) and time.time() - ultima_amostra >= 60:
                ultima_amostra = time.time()
                db.gravar_amostra(amostra_do_minuto(tel, s))
                if time.time() - ultima_limpeza > 86400:
                    ultima_limpeza = time.time()
                    db.limpar(num(c.get("retencao_dias"), 30))
        except Exception as e:
            print(f"[Monitor] vigia: {e}")


def amostra_do_minuto(tel, s: dict) -> dict:
    def media(chave):
        h = tel.historico(chave)[-30:]
        return sum(h) / len(h) if h else None

    parts = s.get("particoes") or []
    ping = ((s.get("ping") or {}).get("8.8.8.8") or {}).get("ms")
    return {"cpu": media("cpu"), "ram": media("ram"),
            "gpu": media("gpu") if s.get("gpu") else None,
            "temp": s.get("cpu_temp"), "down": media("down"), "up": media("up"),
            "leitura": media("leitura"), "escrita": media("escrita"),
            "disco_livre_pct": min((100 - p["pct"] for p in parts), default=None),
            "ping": ping, "internet": None if s.get("internet") is None else int(bool(s["internet"]))}


def on_session_start(player) -> None:
    global _vigia_thread
    if _vigia_thread and _vigia_thread.is_alive():
        return
    _parar.clear()
    _vigia_thread = threading.Thread(target=_laco_vigia, args=(player,), daemon=True,
                                     name="monitor-vigia")
    _vigia_thread.start()


# ── ponto de entrada ───────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    action = str(p.get("action") or "status").strip().lower()
    try:
        s = _tel().snapshot()
        if action == "status":
            frase, painel = texto_status(s)
            mostrar(player, "ESTADO DO PC", painel)
            return frase
        if action == "pesando":
            mostrar(player, "TOP DE PROCESSOS — CPU", tabela_processos(ordenar_processos(s["processos"], "cpu")))
            return _pesando(s)
        if action == "top":
            ordem = p.get("ordem") or "cpu"
            mostrar(player, f"TOP DE PROCESSOS — {str(ordem).upper()}",
                    tabela_processos(ordenar_processos(s["processos"], ordem), 25))
            return (f"Mostrei os 25 processos que mais usam {ordem} no painel. "
                    "Para a tabela ao vivo, abra o 📊 MONITOR.")
        if action == "internet":
            frase, painel = _internet(s)
            mostrar(player, "INTERNET", painel)
            return frase
        if action == "rede_local":
            return _rede_local(player)
        if action == "velocidade":
            return _velocidade(player)
        if action == "discos":
            frase, painel = _discos(s)
            mostrar(player, "DISCOS", painel)
            return frase
        if action == "relatorio":
            return _relatorio(p.get("periodo") or "hoje", player)
        if action == "eventos":
            evs = db.eventos(time.time() - 7 * 86400, 30)
            if not evs:
                return "Nenhum alerta nos últimos 7 dias."
            mostrar(player, "EVENTOS RECENTES", "\n".join(
                f"{datetime.fromtimestamp(e['ts']).strftime('%d/%m %H:%M')}  {e['mensagem']}" for e in evs))
            return f"{len(evs)} evento(s) nos últimos 7 dias; o mais recente: {evs[0]['mensagem']}"
        if action == "processo":
            return _processo(p, player)
        if action == "painel":
            from core import qt_bridge
            win = getattr(player, "_win", None)
            if win is not None and qt_bridge.na_interface(lambda: win._open_monitor_panel()):
                return "Abri o painel de monitoramento."
            return "Abra o painel pela gaveta CONTROLES → 📊 MONITOR."
        return "Ação desconhecida para o monitor."
    except Exception as e:
        return f"O monitor falhou: {e}"
