"""
Segurança que aprende o SEU PC (fork PT-BR 2.4).

Não tem lista fixa de regras: a cada 5 minutos ele anota o que é normal no
seu PC — quanto sobe pela internet em cada hora do dia, que programas rodam
(e de qual pasta, e em que horário), quem fica escutando conexões e quem
conecta de fora — e avisa quando algo foge do padrão:

    "Senhor, um programa enviou 2,1 GB pela internet às 3h. Isso nunca aconteceu antes. (provável: x.exe)"
    "Um programa que eu nunca vi (atualizador.exe, na pasta Temp) está conectado à internet."
    "Alguém de fora (189.x.x.x) conectou no seu PC pela porta 3389 (Área de Trabalho Remota)."
    "O OBS abriu às 4h; você nunca usa ele nesse horário."

Os primeiros 7 dias são de aprendizado: só avisa o que é grave. Diga "isso é
normal" (ou 'normal' com o número do aviso) e ele aprende. Os avisos passam
pela central (urgente fala na hora; o resto espera você não estar jogando).
Tudo fica em memory/seguranca_padrao.json — nada sai do PC.

    "Jarvis, como está a segurança?"   "Jarvis, o que é normal no meu PC às 3h?"
    "Jarvis, isso é normal"            "Jarvis, mostra os avisos de segurança"
"""

from __future__ import annotations

import ipaddress
import re
import statistics
import threading
import time
from datetime import datetime

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "seguranca_adaptativa",
    "brief": "Adaptive security: learns this PC's normal pattern (upload per hour, programs, ports, inbound) and "
             "warns when something is unusual.",
    "description": (
        "Adaptive security that learns the PC's normal behaviour (upload per hour of day, which programs run from "
        "where and when, listening ports, inbound connections) and alerts on deviations. action='status' (learning "
        "progress, last alerts); 'avisos' lists recent alerts with numbers; 'normal' with id (or the last one) marks "
        "an alert as normal so it learns; 'perfil' with hora (0-23) tells what is normal at that hour; 'pausar' / "
        "'retomar' the watcher."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "status | avisos | normal | perfil | pausar | retomar"},
                       "id": {"type": "INTEGER"}, "hora": {"type": "INTEGER"}},
        "required": [],
    },
}

ARQ = MEMORIA / "seguranca_padrao.json"
INTERVALO_S = 300
APRENDIZADO_DIAS = 7
PASTAS_SUSPEITAS = re.compile(r"(?i)\\(appdata\\local\\temp|temp|downloads|users\\public|programdata)\\")
PORTAS = {3389: "Área de Trabalho Remota", 22: "SSH", 445: "compartilhamento de arquivos", 5900: "VNC",
          21: "FTP", 23: "Telnet", 3306: "MySQL", 5432: "PostgreSQL", 8000: "painel do JARVIS",
          8001: "painel do JARVIS", 47777: "agente do JARVIS"}
PORTAS_GRAVES = {3389, 22, 5900, 23, 445}

_lock = threading.Lock()
_estado = {"thread": None, "pausado": False, "ultima": None}
_parar = threading.Event()


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def mediana_mad(valores: list[float]) -> tuple[float, float]:
    if not valores:
        return 0.0, 0.0
    m = statistics.median(valores)
    return m, statistics.median([abs(v - m) for v in valores])


def publico(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
        return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved)
    except ValueError:
        return False


def novo_modelo(agora: float) -> dict:
    return {"inicio": agora, "amostras": 0, "upload": {str(h): [] for h in range(24)}, "programas": {},
            "portas": {}, "entradas": {}, "ignorar": [], "avisos": [], "ultimo_aviso": {}}


def _gb(mb: float) -> str:
    return f"{mb / 1024:.1f} GB".replace(".", ",") if mb >= 1024 else f"{mb:.0f} MB"


def avaliar(modelo: dict, a: dict, agora: float) -> list[dict]:
    """Compara uma amostra com o que é normal. Devolve avisos {chave, texto, prioridade} (pura)."""
    avisos = []
    aprendendo = agora - modelo["inicio"] < APRENDIZADO_DIAS * 86400
    ign = set(modelo.get("ignorar", []))
    h = str(a["hora"])
    hist = modelo["upload"].get(h, [])
    med, mad = mediana_mad(hist)
    up = a["up_mb"]
    limite = max(200.0 if aprendendo else 50.0, med + 8 * mad, 4 * med)
    if up >= limite and (not aprendendo or up >= 1024) and f"upload:{h}" not in ign:
        nunca = not hist or up > 3 * max(hist)
        quem = f" (provável: {a['maior_rede']})" if a.get("maior_rede") else ""
        madrugada = int(h) < 6
        avisos.append({"chave": f"upload:{h}", "prioridade": "urgente" if (madrugada and up >= 500) or up >= 2048 else "normal",
                       "texto": f"Senhor, um programa enviou {_gb(up)} pela internet às {int(h)}h"
                                + (" da manhã" if madrugada else "") + "."
                                + (" Isso nunca aconteceu antes." if nunca else " Bem acima do normal nesse horário.")
                                + quem})
    for exe, p in a["procs"].items():
        conhecido = modelo["programas"].get(exe)
        if conhecido is None:
            if p.get("rede") and PASTAS_SUSPEITAS.search(exe) and f"novo:{exe}" not in ign:
                avisos.append({"chave": f"novo:{exe}", "prioridade": "normal",
                               "texto": f"Um programa que eu nunca vi ({p['nome']}, em {exe.rsplit(chr(92), 2)[-2]}) "
                                        "está conectado à internet."})
            continue
        if not aprendendo and conhecido.get("vezes", 0) >= 20 and conhecido["horas"].get(h, 0) == 0 and \
                f"hora:{exe}:{h}" not in ign and p.get("na_frente"):
            avisos.append({"chave": f"hora:{exe}:{h}", "prioridade": "baixa",
                           "texto": f"{p['nome']} abriu às {int(h)}h; você nunca usa ele nesse horário."})
    for porta, info in a["escutando"].items():
        k = f"porta:{porta}:{info['exe']}"
        if str(porta) not in modelo["portas"] and info.get("publica") and k not in ign and \
                (not aprendendo or int(porta) in PORTAS_GRAVES):
            nome = PORTAS.get(int(porta), "")
            avisos.append({"chave": k, "prioridade": "normal",
                           "texto": f"{info['proc']} abriu a porta {porta}{' (' + nome + ')' if nome else ''} para a rede. "
                                    "Isso é novo."})
    for e in a["entrada"]:
        prefixo = ".".join(e["ip"].split(".")[:3])
        k = f"entrada:{e['porta']}:{prefixo}"
        if prefixo in modelo["entradas"].get(str(e["porta"]), []) or k in ign:
            continue
        grave = int(e["porta"]) in PORTAS_GRAVES
        if grave or not aprendendo:
            nome = PORTAS.get(int(e["porta"]), "")
            avisos.append({"chave": k, "prioridade": "urgente" if grave else "normal",
                           "texto": f"Alguém de fora ({e['ip']}) conectou no seu PC pela porta {e['porta']}"
                                    + (f" ({nome})" if nome else "") + f", no {e['proc']}."})
    return avisos


def aprender(modelo: dict, a: dict) -> None:
    """Junta a amostra ao normal (pura: mexe só no dict)."""
    h = str(a["hora"])
    modelo["amostras"] = modelo.get("amostras", 0) + 1
    modelo["upload"][h] = (modelo["upload"].get(h, []) + [round(a["up_mb"], 2)])[-300:]
    for exe, p in a["procs"].items():
        c = modelo["programas"].setdefault(exe, {"nome": p["nome"], "primeiro": a["ts"], "vezes": 0, "horas": {}})
        c["vezes"] += 1
        c["horas"][h] = c["horas"].get(h, 0) + 1
    for porta, info in a["escutando"].items():
        modelo["portas"].setdefault(str(porta), {"proc": info["proc"], "primeiro": a["ts"]})
    for e in a["entrada"]:
        lista = modelo["entradas"].setdefault(str(e["porta"]), [])
        prefixo = ".".join(e["ip"].split(".")[:3])
        if prefixo not in lista:
            lista.append(prefixo)
            del lista[:-200]


def filtrar_repetidos(modelo: dict, avisos: list[dict], agora: float, intervalo_s: float = 6 * 3600) -> list[dict]:
    saida = []
    for av in avisos:
        if agora - modelo["ultimo_aviso"].get(av["chave"], 0) >= intervalo_s:
            modelo["ultimo_aviso"][av["chave"]] = agora
            saida.append(av)
    return saida


# ── leitura de verdade ───────────────────────────────────────────────────────
_anterior: dict = {"up": None, "io": {}}


def amostrar() -> dict:
    import psutil
    agora = time.time()
    net = psutil.net_io_counters()
    up_mb = 0.0 if _anterior["up"] is None else max(0.0, (net.bytes_sent - _anterior["up"]) / 2**20)
    _anterior["up"] = net.bytes_sent
    conexoes: dict[int, list] = {}
    escutando: dict[int, dict] = {}
    entrada: list[dict] = []
    try:
        cons = psutil.net_connections(kind="inet")
    except Exception:
        cons = []
    portas_escuta = set()
    for c in cons:
        if c.status == "LISTEN" and c.laddr:
            portas_escuta.add(c.laddr.port)
    nomes: dict[int, tuple[str, str]] = {}

    def info(pid):
        if pid not in nomes:
            try:
                pr = psutil.Process(pid)
                nomes[pid] = (pr.name(), (pr.exe() or pr.name()).lower())
            except Exception:
                nomes[pid] = ("?", "?")
        return nomes[pid]
    for c in cons:
        if not c.pid:
            continue
        if c.status == "LISTEN" and c.laddr and c.laddr.ip in ("0.0.0.0", "::"):
            nome, exe = info(c.pid)
            escutando[c.laddr.port] = {"proc": nome, "exe": exe, "publica": True}
        elif c.raddr and c.status == "ESTABLISHED":
            conexoes.setdefault(c.pid, []).append(c.raddr.ip)
            if c.laddr and c.laddr.port in portas_escuta and publico(c.raddr.ip):
                nome, _exe = info(c.pid)
                entrada.append({"ip": c.raddr.ip, "porta": c.laddr.port, "proc": nome})
    try:
        from plugins.linha_do_tempo import foco_atual
        frente = (foco_atual()[0] or "").lower()
    except Exception:
        frente = ""
    procs: dict[str, dict] = {}
    maior, maior_io = "", 0.0
    io_novo = {}
    for pr in psutil.process_iter(["pid", "name", "exe"]):
        try:
            exe = (pr.info.get("exe") or "").lower()
            if not exe:
                continue
            rede = any(publico(ip) for ip in conexoes.get(pr.info["pid"], []))
            io = 0.0
            try:
                cont = pr.io_counters()
                io = float(getattr(cont, "other_bytes", 0) or 0) + float(cont.write_bytes)
            except Exception:
                pass
            io_novo[pr.info["pid"]] = io
            delta = (io - _anterior["io"].get(pr.info["pid"], io)) / 2**20
            if rede and delta > maior_io:
                maior, maior_io = pr.info["name"], delta
            procs[exe] = {"nome": pr.info["name"], "rede": rede, "na_frente": pr.info["name"].lower() == frente}
        except Exception:
            continue
    _anterior["io"] = io_novo
    return {"ts": agora, "hora": datetime.fromtimestamp(agora).hour, "up_mb": up_mb, "procs": procs,
            "escutando": escutando, "entrada": entrada, "maior_rede": maior if maior_io > 20 else ""}


def modelo() -> dict:
    m = ler_json(ARQ, None)
    return m if isinstance(m, dict) and "upload" in m else novo_modelo(time.time())


def passo(enviar=None) -> list[dict]:
    a = amostrar()
    if _anterior.get("primeira", True):                       # a 1ª amostra não tem diferença de upload
        _anterior["primeira"] = False
        a["up_mb"] = 0.0
    with _lock:
        m = modelo()
        avisos = filtrar_repetidos(m, avaliar(m, a, a["ts"]), a["ts"])
        for av in avisos:
            av["id"] = (max([x.get("id", 0) for x in m["avisos"]], default=0) % 999) + 1
            av["ts"] = a["ts"]
            m["avisos"] = (m["avisos"] + [av])[-50:]
        aprender(m, a)
        gravar_json(ARQ, m)
    for av in avisos:
        (enviar or _enviar)(av)
    return avisos


def _enviar(av: dict) -> None:
    try:
        from plugins._notificar import notificar
        prioridade = {"urgente": "urgent", "baixa": "low"}.get(av["prioridade"], "high")
        notificar(None, av["texto"] + f" (aviso {av['id']}; se for normal, diga 'isso é normal')",
                  titulo="Segurança", etiqueta="SEGURANÇA", prioridade=prioridade,
                  falar_agora=True)
    except Exception as e:
        print(f"[Segurança] {e}")


def _laco() -> None:
    time.sleep(30)
    while not _parar.is_set():
        if not _estado["pausado"]:
            try:
                passo()
            except Exception as e:
                print(f"[Segurança] {e}")
        _parar.wait(INTERVALO_S)


def on_session_start(player) -> None:
    t = _estado["thread"]
    if t is None or not t.is_alive():
        _estado["thread"] = threading.Thread(target=_laco, daemon=True, name="seguranca_adaptativa")
        _estado["thread"].start()


def marcar_normal(aid: int | None = None) -> str:
    with _lock:
        m = modelo()
        if not m["avisos"]:
            return "Não tenho aviso de segurança para marcar."
        av = next((x for x in m["avisos"] if x.get("id") == aid), None) if aid else m["avisos"][-1]
        if av is None:
            return f"Não achei o aviso {aid}."
        if av["chave"] not in m["ignorar"]:
            m["ignorar"].append(av["chave"])
        gravar_json(ARQ, m)
    return f"Entendido: '{av['texto'][:80]}…' passa a ser normal."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "normal":
            return marcar_normal(int(p["id"]) if p.get("id") else None)
        if acao == "pausar":
            _estado["pausado"] = True
            return "Vigia de segurança pausado."
        if acao == "retomar":
            _estado["pausado"] = False
            return "Vigia de segurança ligado de novo."
        m = modelo()
        if acao == "avisos":
            if not m["avisos"]:
                return "Nenhum aviso de segurança até agora."
            texto = "\n".join(f"#{a['id']} {datetime.fromtimestamp(a['ts']):%d/%m %H:%M} — {a['texto']}"
                              for a in m["avisos"][-12:])
            mostrar(player, "SEGURANÇA", texto)
            return texto
        if acao == "perfil":
            h = int(p.get("hora") if p.get("hora") is not None else datetime.now().hour) % 24
            med, _mad = mediana_mad(m["upload"].get(str(h), []))
            progs = sorted(((c["horas"].get(str(h), 0), c["nome"]) for c in m["programas"].values()), reverse=True)
            comuns = ", ".join(n for v, n in progs[:8] if v > 0) or "nada registrado ainda"
            return (f"Às {h}h, o normal é subir uns {med * 12:.0f} MB por hora pela internet; programas de costume: "
                    f"{comuns}.")
        dias = (time.time() - m["inicio"]) / 86400
        fase = (f"aprendendo o seu padrão ({dias:.0f} de {APRENDIZADO_DIAS} dias; por enquanto só aviso o que é grave)"
                if dias < APRENDIZADO_DIAS else "já conhece o seu padrão")
        ult = m["avisos"][-1]["texto"] if m["avisos"] else "nenhum aviso"
        return (f"Vigia de segurança {'pausado' if _estado['pausado'] else 'ligado'}, {fase}: {len(m['programas'])} "
                f"programas e {len(m['portas'])} portas conhecidos, {m.get('amostras', 0)} amostras. Último aviso: {ult}.")
    except Exception as e:
        return f"A segurança adaptativa falhou: {e}"
