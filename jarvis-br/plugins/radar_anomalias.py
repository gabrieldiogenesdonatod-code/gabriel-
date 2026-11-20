"""
Radar de anomalias pessoais do sistema — ideia 8 (fork PT-BR 1.4).

Não usa limites fixos ("CPU acima de 90%"): aprende o NORMAL do SEU PC e do
próprio JARVIS e avisa quando algo foge do padrão — e já investiga o porquê.

O QUE ELE VIGIA (a cada 5 minutos, em segundo plano, quase sem custo)
    • ferramentas que ficaram LENTAS: a mediana de 14 dias vira a linha de
      base; um aviso exige 3 chamadas acima de mediana + 4·MAD e acima do
      dobro da mediana (MAD = desvio absoluto mediano, robusto a picos);
    • ferramentas que passaram a FALHAR (falhava < 20%, agora ≥ 50%);
    • VAZAMENTO de memória do JARVIS: RAM do processo subindo > 50% em 2 h e
      passando de 500 MB;
    • ENXURRADA de erros no registro (5 ou mais em 10 minutos);
    • CPU/RAM fora do normal PARA AQUELA HORA do dia (perfil por hora de 14
      dias do monitor: 85% às 15h assusta se o seu normal às 15h é 20%).

Ao achar, investiga: cruza com os eventos do monitor (queda de internet,
disco cheio…), as amostras daquele período e os processos mais pesados no
momento. Cada assunto avisa no máximo uma vez a cada 6 horas.

    "Jarvis, tem alguma anomalia?"     "Jarvis, o que é normal no meu PC às 15h?"
"""

from __future__ import annotations

import re
import statistics
import threading
import time
from collections import defaultdict

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "radar_anomalias",
    "brief": "Learns what is normal for this PC and JARVIS and reports deviations with likely causes.",
    "description": (
        "Personal anomaly radar: learns normal behaviour (tool durations and failure rates, JARVIS "
        "memory, error bursts, CPU/RAM by hour of day) and flags deviations with an investigation. "
        "action='verificar' ('any anomaly?', 'is something weird?'), 'historico' (recent anomalies), "
        "'normal' with hora (0-23) to describe the usual CPU/RAM at that hour."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "verificar | historico | normal"},
            "hora": {"type": "INTEGER"},
        },
        "required": [],
    },
}

_ARQ = MEMORIA / "radar.json"
_INTERVALO = 300
_SILENCIO_S = 6 * 3600
_iniciado = threading.Event()


# ── estatística robusta (pura) ─────────────────────────────────────────────────
def mediana_mad(valores: list[float]) -> tuple[float, float]:
    if not valores:
        return 0.0, 0.0
    med = statistics.median(valores)
    mad = statistics.median([abs(v - med) for v in valores])
    return med, mad


def linha_base_ferramentas(chamadas: list[dict], antes_de: float) -> dict:
    """{ferramenta: {med, mad, n, falha}} com as chamadas anteriores a `antes_de`."""
    por = defaultdict(list)
    for c in chamadas:
        if c["ts"] < antes_de:
            por[c["ferramenta"]].append(c)
    base = {}
    for f, cs in por.items():
        med, mad = mediana_mad([float(c["ms"]) for c in cs if c.get("ok")])
        base[f] = {"med": med, "mad": mad, "n": len(cs),
                   "falha": sum(1 for c in cs if not c.get("ok")) / len(cs)}
    return base


def anomalias_ferramentas(base: dict, recentes: list[dict]) -> list[dict]:
    por = defaultdict(list)
    for c in recentes:
        por[c["ferramenta"]].append(c)
    saida = []
    for f, cs in por.items():
        b = base.get(f)
        if not b or b["n"] < 8:
            continue                                   # pouco histórico: ainda aprendendo
        limite = max(b["med"] + 4 * max(b["mad"], b["med"] * 0.05), 2 * b["med"], b["med"] + 300)
        lentas = [c for c in cs if c.get("ok") and float(c["ms"]) > limite]
        if len(lentas) >= 3:
            media = statistics.mean(float(c["ms"]) for c in lentas)
            saida.append({"chave": f"lenta:{f}", "tipo": "ferramenta lenta",
                          "texto": f"{f} está lenta: {media / 1000:.1f} s em {len(lentas)} chamadas; "
                                   f"o normal é {b['med'] / 1000:.1f} s",
                          "inicio": lentas[0]["ts"], "fim": lentas[-1]["ts"]})
        falhas = [c for c in cs if not c.get("ok")]
        if len(cs) >= 3 and len(falhas) / len(cs) >= 0.5 and b["falha"] < 0.2:
            ultimo = (falhas[-1].get("resumo") or "")[:120]
            saida.append({"chave": f"falha:{f}", "tipo": "ferramenta falhando",
                          "texto": f"{f} falhou {len(falhas)} de {len(cs)} vezes; normalmente falha "
                                   f"{b['falha'] * 100:.0f}%" + (f". Última resposta: {ultimo}" if ultimo else ""),
                          "inicio": falhas[0]["ts"], "fim": falhas[-1]["ts"]})
    return saida


def vazamento(amostras: list[dict], janela_s: float = 7200, minimo_mb: float = 500) -> dict | None:
    """amostras: [{ts, rss_mb}] em ordem. Crescimento > 50% em 2 h e acima do mínimo."""
    if len(amostras) < 4:
        return None
    fim = amostras[-1]
    inicio = next((a for a in amostras if fim["ts"] - a["ts"] <= janela_s), None)
    if not inicio or fim["ts"] - inicio["ts"] < janela_s * 0.6:
        return None
    if fim["rss_mb"] > minimo_mb and fim["rss_mb"] > inicio["rss_mb"] * 1.5:
        # só conta se for subida sustentada (não um pico)
        meio = [a["rss_mb"] for a in amostras if inicio["ts"] <= a["ts"] <= fim["ts"]]
        subidas = sum(1 for x, y in zip(meio, meio[1:]) if y >= x)
        if subidas >= 0.6 * (len(meio) - 1):
            return {"chave": "vazamento", "tipo": "memória do JARVIS subindo",
                    "texto": f"a memória do JARVIS foi de {inicio['rss_mb']:.0f} MB para {fim['rss_mb']:.0f} MB "
                             f"em {(fim['ts'] - inicio['ts']) / 3600:.1f} h, sem descer",
                    "inicio": inicio["ts"], "fim": fim["ts"]}
    return None


_RE_ERRO = re.compile(r"\b(erro|error|falhou|failed|exception|traceback|n[aã]o consegui)\b", re.I)


def enxurrada_erros(linhas: list[dict], minimo: int = 5) -> dict | None:
    erros = [l for l in linhas if _RE_ERRO.search(l.get("linha") or "")]
    if len(erros) < minimo:
        return None
    exemplos = "; ".join((e["linha"] or "")[:80] for e in erros[-2:])
    return {"chave": "erros", "tipo": "muitos erros", "texto": f"{len(erros)} erros no registro em 10 minutos ({exemplos})",
            "inicio": erros[0]["ts"], "fim": erros[-1]["ts"]}


def perfil_por_hora(amostras: list[dict]) -> dict:
    """{hora: {"cpu": (med, mad), "ram": (med, mad), "n": dias}} (pura)."""
    por = defaultdict(lambda: {"cpu": [], "ram": [], "dias": set()})
    for a in amostras:
        lt = time.localtime(a["ts"])
        h = por[lt.tm_hour]
        if a.get("cpu") is not None:
            h["cpu"].append(float(a["cpu"]))
        if a.get("ram") is not None:
            h["ram"].append(float(a["ram"]))
        h["dias"].add(lt.tm_yday)
    return {hora: {"cpu": mediana_mad(v["cpu"]), "ram": mediana_mad(v["ram"]), "n": len(v["dias"])}
            for hora, v in por.items()}


def anomalia_hora(perfil: dict, recentes: list[dict]) -> list[dict]:
    if len(recentes) < 5:
        return []
    hora = time.localtime(recentes[-1]["ts"]).tm_hour
    p = perfil.get(hora)
    if not p or p["n"] < 4:
        return []
    saida = []
    for campo, nome, folga in (("cpu", "CPU", 25), ("ram", "RAM", 20)):
        vals = [float(a[campo]) for a in recentes if a.get(campo) is not None]
        if not vals:
            continue
        atual = statistics.mean(vals)
        med, mad = p[campo]
        if atual > med + max(4 * mad, folga):
            saida.append({"chave": f"hora:{campo}", "tipo": f"{nome} fora do normal",
                          "texto": f"{nome} em {atual:.0f}% nos últimos 30 min; às {hora}h o normal é {med:.0f}%",
                          "inicio": recentes[0]["ts"], "fim": recentes[-1]["ts"]})
    return saida


# ── investigação ───────────────────────────────────────────────────────────────
def investigar(an: dict) -> list[str]:
    pistas = []
    ini, fim = an.get("inicio", time.time() - 1800) - 900, an.get("fim", time.time()) + 300
    try:
        from plugins import _monitor_db
        for e in _monitor_db.eventos(ini, 50):
            if e["ts"] <= fim and e.get("tipo") != "aviso":
                pistas.append(f"{time.strftime('%H:%M', time.localtime(e['ts']))} {e['tipo']}: {e['mensagem'][:90]}")
        am = _monitor_db.amostras(ini, fim)
        if am:
            sem_net = sum(1 for a in am if a.get("internet") == 0)
            if sem_net:
                pistas.append(f"internet fora em {sem_net} de {len(am)} amostras do período")
            cpu = [a["cpu"] for a in am if a.get("cpu") is not None]
            if cpu and max(cpu) > 90:
                pistas.append(f"CPU chegou a {max(cpu):.0f}% no período")
            disco = [a["disco_livre_pct"] for a in am if a.get("disco_livre_pct") is not None]
            if disco and min(disco) < 10:
                pistas.append(f"disco com só {min(disco):.0f}% livre")
    except Exception:
        pass
    if an.get("fim", 0) > time.time() - 900:              # está acontecendo agora
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["name", "memory_info"]):
                try:
                    procs.append((p.info["memory_info"].rss, p.info["name"] or "?"))
                except Exception:
                    continue
            pesados = sorted(procs, reverse=True)[:3]
            pistas.append("mais pesados agora: " + ", ".join(f"{n} ({r / 1048576:.0f} MB)" for r, n in pesados))
        except Exception:
            pass
    return pistas[:8]


# ── ciclo ──────────────────────────────────────────────────────────────────────
def _estado() -> dict:
    e = ler_json(_ARQ, {}) or {}
    e.setdefault("rss", [])
    e.setdefault("historico", [])
    e.setdefault("avisados", {})
    return e


def _amostrar_proprio(e: dict) -> None:
    try:
        import psutil
        p = psutil.Process()
        e["rss"].append({"ts": time.time(), "rss_mb": p.memory_info().rss / 1048576})
        e["rss"] = [a for a in e["rss"] if a["ts"] > time.time() - 48 * 3600][-600:]
    except Exception:
        pass


def verificar(avisar_player=None, notificar_agora: bool = True) -> list[dict]:
    from core import registro_uso
    agora = time.time()
    e = _estado()
    _amostrar_proprio(e)
    achados = []
    cham = registro_uso.chamadas(agora - 14 * 86400)
    base = linha_base_ferramentas(cham, agora - 3600)
    achados += anomalias_ferramentas(base, [c for c in cham if c["ts"] >= agora - 3600])
    v = vazamento(e["rss"])
    if v:
        achados.append(v)
    erros = enxurrada_erros(registro_uso.linhas_registro(agora - 600))
    if erros:
        achados.append(erros)
    try:
        from plugins import _monitor_db
        perfil = perfil_por_hora(_monitor_db.amostras(agora - 14 * 86400, agora - 3600))
        achados += anomalia_hora(perfil, _monitor_db.amostras(agora - 1800))
    except Exception:
        pass
    novos = []
    for a in achados:
        a["pistas"] = investigar(a)
        a["quando"] = agora
        if agora - float(e["avisados"].get(a["chave"], 0)) >= _SILENCIO_S:
            e["avisados"][a["chave"]] = agora
            e["historico"].append({k: a[k] for k in ("chave", "tipo", "texto", "pistas", "quando")})
            novos.append(a)
    e["historico"] = e["historico"][-100:]
    gravar_json(_ARQ, e)
    if notificar_agora and novos:
        from plugins._notificar import notificar
        a = novos[0]
        pista = f" Pista: {a['pistas'][0]}." if a["pistas"] else ""
        notificar(avisar_player, f"Anomalia: {a['texto']}.{pista}", titulo="Radar de anomalias",
                  etiqueta="RADAR")
    return achados


def _laco(player) -> None:
    time.sleep(180)
    while True:
        try:
            verificar(player)
        except Exception as ex:
            print(f"[Radar] {ex}")
        time.sleep(_INTERVALO)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="radar_anomalias").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "verificar").lower()
    try:
        if acao == "historico":
            h = _estado()["historico"][-10:]
            if not h:
                return "Nenhuma anomalia registrada até agora."
            mostrar(player, "RADAR — HISTÓRICO", "\n\n".join(
                f"{time.strftime('%d/%m %H:%M', time.localtime(a['quando']))} — {a['tipo']}\n  {a['texto']}"
                + "".join(f"\n  • {x}" for x in a.get("pistas", [])) for a in reversed(h)))
            return f"{len(h)} anomalia(s) recentes; a última: {h[-1]['texto']}."
        if acao == "normal":
            from plugins import _monitor_db
            hora = int(p.get("hora") if p.get("hora") is not None else time.localtime().tm_hour) % 24
            perfil = perfil_por_hora(_monitor_db.amostras(time.time() - 14 * 86400))
            if hora not in perfil:
                return "Ainda não tenho dados suficientes desse horário."
            x = perfil[hora]
            return (f"Às {hora}h, o normal do seu PC é CPU em torno de {x['cpu'][0]:.0f}% e RAM em "
                    f"{x['ram'][0]:.0f}% (base de {x['n']} dia(s)).")
        achados = verificar(player, notificar_agora=False)
        if not achados:
            return "Nada fora do normal agora. Ferramentas, memória do JARVIS e uso do PC estão no padrão."
        mostrar(player, "RADAR DE ANOMALIAS", "\n\n".join(
            f"■ {a['tipo'].upper()}\n  {a['texto']}" + "".join(f"\n  • {x}" for x in a["pistas"]) for a in achados))
        a = achados[0]
        return (f"{len(achados)} coisa(s) fora do normal. Principal: {a['texto']}."
                + (f" Pista: {a['pistas'][0]}." if a["pistas"] else ""))
    except Exception as e:
        return f"O radar falhou: {e}"
