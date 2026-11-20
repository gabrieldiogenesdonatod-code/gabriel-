"""
Gêmeo digital do computador — ideia 1 (fork PT-BR 1.4).

O JARVIS mantém um MODELO do seu PC e aprende com ele:
    * capacidade: núcleos, RAM, VRAM, discos;
    * perfil de cada programa: quanto de CPU e RAM ele costuma usar (média e
      pico), aprendido em segundo plano, uma amostra por minuto;
    * o que está rodando agora e o que está pesando.

Com isso ele PREVÊ antes de você fazer:
    "Jarvis, se eu abrir o Premiere agora, o PC vai travar?"
    "Jarvis, dá para gravar a tela e jogar ao mesmo tempo?"
→ estima a RAM e a CPU depois da tarefa e, se for passar do limite, diz o que
fechar (programas pesados que estão abertos mas não estão na frente).

O perfil fica em memory/gemeo.json. Programas que ele nunca viu usam uma
estimativa de tabela (jogos, editores de vídeo, navegadores…) até aprender.
"""

from __future__ import annotations

import threading
import time

from plugins._comum import MEMORIA, br, gravar_json, ler_json, mostrar, plugin_ligado, tamanho
from plugins._indice_apps import normalizar, pontuar
from plugins._protecao import eh_protegido

PLUGIN = {
    "name": "gemeo_digital",
    "brief": "Model of this PC: learned app resource profiles; predict slowdowns before a task.",
    "description": (
        "Digital twin of the computer. action='prever' with tarefa (one or more apps/tasks, comma "
        "separated, e.g. 'premiere, obs' or 'gravar a tela e jogar valorant') for 'se eu abrir X o "
        "PC vai travar?', 'dá para fazer X e Y juntos?'. action='estado' for an overview of the "
        "model (capacity, running tasks, what is heavy). action='perfil' (alvo) for what the twin "
        "learned about one program. action='aprendidos' lists learned programs."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "prever | estado | perfil | aprendidos"},
            "tarefa": {"type": "STRING"}, "alvo": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

ARQUIVO = MEMORIA / "gemeo.json"
GB = 1024 ** 3
LIMITE_RAM = 90.0
LIMITE_CPU = 90.0

# Estimativas de partida (RAM em GB, CPU em % do PC) para o que ainda não foi visto.
ESTIMATIVAS = {
    "premiere": (4.0, 45), "after effects": (5.0, 50), "davinci": (5.0, 55), "capcut": (2.0, 35),
    "photoshop": (3.0, 25), "blender": (4.0, 70), "obs": (0.6, 15), "gravar": (0.4, 12),
    "chrome": (1.5, 8), "edge": (1.2, 8), "firefox": (1.3, 8), "vs code": (0.8, 5), "code": (0.8, 5),
    "visual studio": (2.0, 15), "android studio": (4.0, 30), "pycharm": (2.0, 10), "docker": (2.0, 15),
    "valorant": (3.0, 45), "league of legends": (2.0, 35), "lol": (2.0, 35), "fortnite": (5.0, 60),
    "minecraft": (3.0, 40), "gta": (6.0, 60), "cs2": (4.0, 50), "counter strike": (4.0, 50),
    "steam": (0.5, 3), "discord": (0.5, 3), "spotify": (0.3, 2), "whatsapp": (0.4, 2),
    "teams": (0.8, 6), "zoom": (0.6, 15), "excel": (0.6, 5), "word": (0.5, 3),
    "compilar": (2.0, 80), "renderizar": (4.0, 90), "jogo": (4.0, 50), "jogar": (4.0, 50),
}

_lock = threading.Lock()
_thread: threading.Thread | None = None
_parar = threading.Event()


def carregar() -> dict:
    d = ler_json(ARQUIVO, None)
    return d if isinstance(d, dict) else {"programas": {}, "amostras": 0, "atualizado": 0}


def aprender(modelo: dict, processos: list[dict], ncpu: int, alfa: float = 0.2) -> dict:
    """Atualiza os perfis com uma fotografia da tabela de processos. Pura."""
    por_nome: dict[str, dict] = {}
    for p in processos:
        nome = normalizar(p["nome"].rsplit(".", 1)[0]) or p["nome"].lower()
        agg = por_nome.setdefault(nome, {"cpu": 0.0, "ram": 0, "rotulo": p["nome"]})
        agg["cpu"] += float(p.get("cpu") or 0)
        agg["ram"] += int(p.get("ram") or 0)
    progs = modelo.setdefault("programas", {})
    agora = time.time()
    for nome, a in por_nome.items():
        if a["ram"] < 50 * 1024 ** 2 and a["cpu"] < 1:
            continue                                  # só o que tem peso
        pf = progs.get(nome)
        if pf is None:
            progs[nome] = {"rotulo": a["rotulo"], "cpu": a["cpu"], "ram": a["ram"],
                           "cpu_pico": a["cpu"], "ram_pico": a["ram"], "vezes": 1, "visto": agora}
        else:
            pf["cpu"] = (1 - alfa) * pf["cpu"] + alfa * a["cpu"]
            pf["ram"] = int((1 - alfa) * pf["ram"] + alfa * a["ram"])
            pf["cpu_pico"] = max(pf["cpu_pico"] * 0.999, a["cpu"])
            pf["ram_pico"] = int(max(pf["ram_pico"] * 0.999, a["ram"]))
            pf["vezes"] += 1
            pf["visto"] = agora
    modelo["amostras"] = modelo.get("amostras", 0) + 1
    modelo["atualizado"] = agora
    return modelo


def _laco():
    from core import telemetria
    tel = telemetria.get()
    while not _parar.wait(60):
        if not plugin_ligado("gemeo_digital"):
            continue
        try:
            s = tel.snapshot()
            with _lock:
                m = aprender(carregar(), s.get("processos") or [], s.get("cpu_nucleos_logicos") or 1)
                m["capacidade"] = {"ram": (s.get("ram") or {}).get("total"),
                                   "nucleos": s.get("cpu_nucleos_logicos"),
                                   "vram": (s.get("gpu") or {}).get("vram_total")}
                gravar_json(ARQUIVO, m)          # arquivo pequeno: 1 gravação por minuto
        except Exception as e:
            print(f"[Gêmeo] {e}")


def on_session_start(player) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _parar.clear()
    _thread = threading.Thread(target=_laco, daemon=True, name="gemeo-digital")
    _thread.start()


# ── previsão ───────────────────────────────────────────────────────────────────
def perfil_de(alvo: str, modelo: dict) -> tuple[str, float, float, str]:
    """(nome, ram_bytes, cpu_pct, fonte) do que se aprendeu ou estimou para 'alvo'."""
    progs = modelo.get("programas", {})
    melhor, pontos = None, 0
    for nome, pf in progs.items():
        p = max(pontuar(alvo, nome), pontuar(alvo, pf.get("rotulo", "")))
        if p > pontos:
            melhor, pontos = nome, p
    if melhor and pontos >= 70:
        pf = progs[melhor]
        # entre a média e o pico: prever pelo uso típico, com folga
        ram = 0.6 * pf["ram"] + 0.4 * pf["ram_pico"]
        cpu = 0.6 * pf["cpu"] + 0.4 * pf["cpu_pico"]
        return pf.get("rotulo", melhor), ram, cpu, f"aprendido em {pf['vezes']} observações"
    q = normalizar(alvo)
    for chave, (ram_gb, cpu) in ESTIMATIVAS.items():
        if chave in q or pontuar(alvo, chave) >= 80:
            return alvo, ram_gb * GB, float(cpu), "estimativa de tabela (ainda não vi esse programa)"
    return alvo, 1.0 * GB, 10.0, "chute genérico (programa desconhecido)"


def prever(tarefas: list[str], s: dict, modelo: dict) -> dict:
    """Pura: dado o estado atual e o modelo, o que acontece se fizer as tarefas."""
    ram = s.get("ram") or {}
    total = float(ram.get("total") or 8 * GB)
    usada = float(ram.get("usada") or 0)
    cpu_agora = float(s.get("cpu") or 0)
    rodando = {normalizar(p["nome"].rsplit(".", 1)[0]) for p in s.get("processos") or []}
    itens, ram_extra, cpu_extra = [], 0.0, 0.0
    for t in tarefas:
        nome, r, c, fonte = perfil_de(t, modelo)
        ja = normalizar(nome.rsplit(".", 1)[0]) in rodando
        itens.append({"tarefa": t, "nome": nome, "ram": r, "cpu": c, "fonte": fonte, "ja_aberto": ja})
        if not ja:
            ram_extra += r
            cpu_extra += c
    ram_pct = 100 * (usada + ram_extra) / total
    cpu_pct = min(100.0, cpu_agora + cpu_extra)
    fechar = []
    if ram_pct > LIMITE_RAM or cpu_pct > LIMITE_CPU:
        alvos = {normalizar(i["nome"].rsplit(".", 1)[0]) for i in itens}
        pesados = sorted((p for p in s.get("processos") or []
                          if not eh_protegido(p["nome"], p["pid"])
                          and normalizar(p["nome"].rsplit(".", 1)[0]) not in alvos),
                         key=lambda p: p["ram"], reverse=True)
        precisa = (usada + ram_extra) - total * (LIMITE_RAM - 5) / 100
        liberado = 0
        vistos = set()
        for p in pesados:
            n = normalizar(p["nome"].rsplit(".", 1)[0])
            if n in vistos:
                continue
            vistos.add(n)
            fechar.append({"nome": p["nome"], "ram": sum(x["ram"] for x in pesados
                                                          if normalizar(x["nome"].rsplit(".", 1)[0]) == n)})
            liberado += fechar[-1]["ram"]
            if liberado >= precisa and ram_pct > LIMITE_RAM or len(fechar) >= 4:
                break
    risco = "alto" if ram_pct > 97 or cpu_pct >= 99 else "médio" if ram_pct > LIMITE_RAM or cpu_pct > LIMITE_CPU \
        else "baixo"
    return {"itens": itens, "ram_pct": ram_pct, "cpu_pct": cpu_pct, "risco": risco, "fechar": fechar,
            "ram_total": total, "ram_usada": usada}


def _texto_previsao(r: dict) -> str:
    nomes = ", ".join(i["nome"].rsplit(".exe", 1)[0] for i in r["itens"])
    base = (f"Com {nomes}, a RAM iria para cerca de {br(r['ram_pct'], 0)}% e a CPU para "
            f"{br(r['cpu_pct'], 0)}%.")
    if r["risco"] == "baixo":
        return base + " Dá tranquilo."
    sugestao = ""
    if r["fechar"]:
        sugestao = " Para ficar folgado, feche " + ", ".join(
            f"{f['nome'].rsplit('.', 1)[0]} ({tamanho(f['ram'])})" for f in r["fechar"]) + "."
    return base + (" Vai ficar pesado; pode travar." if r["risco"] == "alto" else " Vai ficar no limite.") + sugestao


def dividir(tarefa: str) -> list[str]:
    """'gravar a tela e jogar valorant' → ['gravar', 'valorant']."""
    import re
    partes = re.split(r",|\be\b|\+|\bjunto com\b|\bao mesmo tempo\b|\bcom\b", tarefa or "")
    limpas = []
    for p in partes:
        p = p.strip()
        if re.match(r"^(gravar|grava)\b", p):
            limpas.append("gravar")
            continue
        p = re.sub(r"^(abrir|abre|usar|usa|rodar|roda|jogar|joga)\s+", "", p).strip()
        if p:
            limpas.append(p)
    return limpas or ([tarefa] if tarefa else [])


def run(parameters: dict, player=None, session_memory=None) -> str:
    from core import telemetria
    p = parameters or {}
    a = str(p.get("action") or "estado").lower()
    try:
        s = telemetria.get().snapshot()
        with _lock:
            modelo = carregar()
        if not modelo.get("programas"):
            # primeira vez: aprende com o que está rodando agora, para já ter base
            modelo = aprender(modelo, s.get("processos") or [], s.get("cpu_nucleos_logicos") or 1)
        if a == "prever":
            tarefas = dividir(str(p.get("tarefa") or p.get("alvo") or ""))
            if not tarefas:
                return "O que você quer abrir ou fazer?"
            r = prever(tarefas, s, modelo)
            mostrar(player, "GÊMEO DIGITAL — PREVISÃO", "\n".join(
                [f"{i['nome']:<28} RAM {tamanho(i['ram']):>9}  CPU {br(i['cpu'], 0):>3}%  "
                 f"{'(já aberto) ' if i['ja_aberto'] else ''}{i['fonte']}" for i in r["itens"]]
                + ["", f"RAM: {tamanho(r['ram_usada'])} agora → {br(r['ram_pct'], 0)}% depois",
                   f"CPU: {br(s.get('cpu') or 0, 0)}% agora → {br(r['cpu_pct'], 0)}% depois",
                   f"Risco: {r['risco']}"]
                + ([""] + [f"Fechar: {f['nome']} ({tamanho(f['ram'])})" for f in r["fechar"]] if r["fechar"] else [])))
            return _texto_previsao(r)
        if a == "estado":
            ram = s.get("ram") or {}
            progs = modelo.get("programas", {})
            pesados = sorted(progs.values(), key=lambda x: x["ram"], reverse=True)[:5]
            g = s.get("gpu") or {}
            texto = (f"O modelo do seu PC: {s.get('cpu_nucleos_logicos')} núcleos, {tamanho(ram.get('total', 0))} de "
                     f"RAM" + (f", {tamanho(g.get('vram_total', 0))} de VRAM" if g else "") +
                     f". Agora: CPU {br(s.get('cpu') or 0, 0)}%, RAM {br(ram.get('pct') or 0, 0)}%. "
                     f"Já aprendi o perfil de {len(progs)} programas")
            if pesados:
                texto += "; os mais pesados costumam ser " + ", ".join(
                    f"{x['rotulo'].rsplit('.', 1)[0]} ({tamanho(x['ram'])})" for x in pesados[:3])
            return texto + "."
        if a == "perfil":
            alvo = str(p.get("alvo") or p.get("tarefa") or "")
            nome, ram, cpu, fonte = perfil_de(alvo, modelo)
            return f"{nome}: costuma usar uns {tamanho(ram)} de RAM e {br(cpu, 0)}% da CPU ({fonte})."
        if a == "aprendidos":
            progs = sorted(modelo.get("programas", {}).values(), key=lambda x: x["ram"], reverse=True)
            if not progs:
                return "Ainda não aprendi nenhum perfil; aprendo um pouco a cada minuto com o JARVIS aberto."
            mostrar(player, "GÊMEO DIGITAL — PERFIS", "\n".join(
                f"{x['rotulo'][:28]:<28} RAM média {tamanho(x['ram']):>9}  pico {tamanho(x['ram_pico']):>9}  "
                f"CPU {br(x['cpu'], 0):>3}% (pico {br(x['cpu_pico'], 0)}%)  {x['vezes']}×" for x in progs[:60]))
            return f"Tenho perfil de {len(progs)} programas; a lista está no painel."
        return "Use prever, estado, perfil ou aprendidos."
    except Exception as e:
        return f"O gêmeo digital falhou: {e}"
