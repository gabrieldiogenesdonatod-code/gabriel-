"""
Reconstrução de acontecimentos — ideia 14 (fork PT-BR 1.4).

"Jarvis, o que aconteceu ontem à tarde?"   "Por que o PC travou às 15h?"
"O que deu errado no protocolo trabalho hoje de manhã?"

Junta, numa linha do tempo única e em ordem, tudo que ficou registrado:

    ferramentas chamadas (e se deram certo)      core/registro_uso.py
    linhas do registro do JARVIS                  core/registro_uso.py
    protocolos e cadeias, passo a passo           core/registro_uso.py
    eventos do monitor (alertas, internet, segurança, avisos)  monitor.db
    amostras do monitor (CPU, RAM, internet)      monitor.db
    janela em foco / ausência                     monitor.db (linha do tempo)
    arquivos criados ou mudados nas suas pastas   disco

E SEPARA o que é FATO (está registrado, com horário) do que é HIPÓTESE
(deduzido por regras: falha logo depois de a internet cair, lentidão com CPU
no máximo, "não encontrei" por falta de apelido…). Quando a pergunta é sobre
um problema, o motor de hipóteses concorrentes também opina.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from plugins._comum import mostrar, pasta_usuario

PLUGIN = {
    "name": "reconstrucao",
    "brief": "Rebuild what happened in a period (or to something), separating facts from hypotheses.",
    "description": (
        "Event reconstruction: builds an ordered timeline from JARVIS tool calls, log lines, protocol "
        "steps, monitor events and samples, focused windows and changed files, then separates recorded "
        "FACTS from HYPOTHESES. Use for 'what happened yesterday afternoon', 'why did the PC freeze at "
        "3pm', 'what went wrong with X'. periodo = natural phrase (ontem à tarde, hoje às 15h, das 14h "
        "às 16h, última hora); alvo = optional subject to focus on; pergunta = the user's question."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "periodo": {"type": "STRING"}, "alvo": {"type": "STRING"}, "pergunta": {"type": "STRING"},
        },
        "required": [],
    },
}


# ── período ────────────────────────────────────────────────────────────────────
def _hora(txt: str) -> tuple[int, int] | None:
    m = re.search(r"(\d{1,2})\s*(?:h|:|horas?)\s*(\d{2})?", txt)
    if not m:
        return None
    return int(m.group(1)) % 24, int(m.group(2) or 0)


def periodo(texto: str, agora: datetime | None = None) -> tuple[datetime, datetime, str]:
    agora = agora or datetime.now()
    t = (texto or "").lower()
    base = agora.date()
    rotulo = ""
    if "anteontem" in t:
        base, rotulo = base - timedelta(days=2), "anteontem"
    elif "ontem" in t:
        base, rotulo = base - timedelta(days=1), "ontem"
    elif "hoje" in t:
        rotulo = "hoje"
    dia0 = datetime.combine(base, datetime.min.time())
    m = re.search(r"[uú]ltim[oa]s?\s+(\d+)?\s*(minutos?|horas?|hora)", t)
    if m:
        n = int(m.group(1) or 1)
        delta = timedelta(minutes=n) if m.group(2).startswith("min") else timedelta(hours=n)
        rot = f"últimos {n} {m.group(2)}" if n > 1 else ("último minuto" if m.group(2).startswith("min") else "última hora")
        return agora - delta, agora, rot
    m = re.search(r"das?\s+(\d{1,2})\s*(?:h|:)?\s*(\d{2})?\s*(?:h)?\s*(?:às|as|a|até)\s+(\d{1,2})\s*(?:h|:)?\s*(\d{2})?", t)
    if m:
        ini = dia0.replace(hour=int(m.group(1)) % 24, minute=int(m.group(2) or 0))
        fim = dia0.replace(hour=int(m.group(3)) % 24, minute=int(m.group(4) or 0))
        return ini, max(fim, ini + timedelta(minutes=10)), f"{rotulo + ' ' if rotulo else ''}das {ini:%H:%M} às {fim:%H:%M}"
    if re.search(r"\b(?:às|as|por volta d[ae]s?)\s+\d", t) or re.search(r"\b\d{1,2}\s*h\b", t):
        hm = _hora(t)
        if hm:
            centro = dia0.replace(hour=hm[0], minute=hm[1])
            if not rotulo and centro > agora:
                centro -= timedelta(days=1)
            return centro - timedelta(minutes=40), centro + timedelta(minutes=20), \
                f"{rotulo + ' ' if rotulo else ''}por volta das {centro:%H:%M}"
    for nome, (h1, h2) in (("madrugada", (0, 6)), ("manhã", (6, 12)), ("manha", (6, 12)),
                           ("tarde", (12, 18)), ("noite", (18, 24))):
        if nome in t:
            ini = dia0.replace(hour=h1)
            fim = dia0.replace(hour=23, minute=59) if h2 == 24 else dia0.replace(hour=h2)
            return ini, min(fim, agora) if base == agora.date() else fim, f"{rotulo or 'hoje'} de {nome.replace('manha', 'manhã')}"
    if rotulo:
        return dia0, min(dia0 + timedelta(days=1), agora), rotulo
    return agora - timedelta(hours=3), agora, "últimas 3 horas"


# ── coleta ─────────────────────────────────────────────────────────────────────
def _arquivos_mudados(ini: float, fim: float, limite: int = 40) -> list[tuple[float, str]]:
    saida = []
    for nome in ("Desktop", "Documents", "Downloads", "Pictures", "Videos"):
        try:
            raiz = pasta_usuario(nome)
        except Exception:
            continue
        if not raiz.exists():
            continue
        pilha, vistos = [(raiz, 0)], 0
        while pilha and vistos < 4000:
            d, nivel = pilha.pop()
            try:
                for it in d.iterdir():
                    vistos += 1
                    if it.name.startswith(".") or it.name.lower() in ("desktop.ini", "thumbs.db"):
                        continue
                    if it.is_dir():
                        if nivel < 2 and it.name.lower() not in ("node_modules", ".git", "__pycache__", "venv"):
                            pilha.append((it, nivel + 1))
                        continue
                    mt = it.stat().st_mtime
                    if ini <= mt <= fim:
                        saida.append((mt, f"arquivo mudado: {it.name} ({nome})"))
            except OSError:
                continue
    return sorted(saida)[-limite:]


def linha_do_tempo(ini: float, fim: float, incluir_arquivos: bool = True) -> list[dict]:
    """[{ts, fonte, texto, ok}] em ordem (só fatos registrados)."""
    itens = []
    try:
        from core import registro_uso
        for c in registro_uso.chamadas(ini, fim):
            itens.append({"ts": c["ts"], "fonte": "ferramenta", "ok": bool(c.get("ok")),
                          "texto": f"{c['ferramenta']} {c.get('acao') or ''}".strip()
                                   + f" → {'ok' if c.get('ok') else 'FALHOU'} ({c['ms'] / 1000:.1f} s)"
                                   + (f": {c['resumo'][:90]}" if c.get("resumo") else "")})
        for l in registro_uso.linhas_registro(ini, fim):
            txt = l.get("linha") or ""
            if txt.startswith(("Você:", "JARVIS:")) or re.search(r"erro|falh|n[aã]o consegui|aviso|alerta", txt, re.I):
                itens.append({"ts": l["ts"], "fonte": "registro", "texto": txt[:160],
                              "ok": not re.search(r"erro|falh|n[aã]o consegui", txt, re.I)})
        for t in registro_uso.tarefas(ini):
            if t["ts"] > fim:
                continue
            ruins = [p["descricao"] for p in t.get("passos", []) if not p.get("ok")]
            itens.append({"ts": t["ts"], "fonte": t["tipo"], "ok": bool(t.get("ok")),
                          "texto": f"{t['tipo']} '{t['nome']}' em {t['ms'] / 1000:.1f} s"
                                   + (f"; falharam: {', '.join(ruins[:3])}" if ruins else "; todos os passos ok")})
    except Exception as e:
        print(f"[Reconstrução] diário: {e}")
    try:
        from plugins import _monitor_db
        for e in _monitor_db.eventos(ini, 500):
            if e["ts"] <= fim:
                itens.append({"ts": e["ts"], "fonte": f"monitor/{e['tipo']}", "texto": e["mensagem"][:160],
                              "ok": e["tipo"] not in ("alerta", "seguranca")})
        am = _monitor_db.amostras(ini, fim)
        sem_net = None
        for a in am:
            if a.get("internet") == 0 and sem_net is None:
                sem_net = a["ts"]
            elif a.get("internet") != 0 and sem_net is not None:
                itens.append({"ts": sem_net, "fonte": "monitor/amostra", "ok": False,
                              "texto": f"internet fora por {max(1, round((a['ts'] - sem_net) / 60))} min"})
                sem_net = None
        if sem_net is not None:
            itens.append({"ts": sem_net, "fonte": "monitor/amostra", "ok": False, "texto": "internet fora (até o fim do período)"})
        picos = [a for a in am if (a.get("cpu") or 0) >= 90]
        if picos:
            itens.append({"ts": picos[0]["ts"], "fonte": "monitor/amostra", "ok": False,
                          "texto": f"CPU acima de 90% em {len(picos)} minuto(s), pico {max(a['cpu'] for a in picos):.0f}%"})
        ram = [a for a in am if (a.get("ram") or 0) >= 90]
        if ram:
            itens.append({"ts": ram[0]["ts"], "fonte": "monitor/amostra", "ok": False,
                          "texto": f"RAM acima de 90% em {len(ram)} minuto(s)"})
        from plugins.linha_do_tempo import juntar
        for f in juntar(_monitor_db.focos(ini, fim)):
            if f["fim"] - f["inicio"] >= 120:
                itens.append({"ts": f["inicio"], "fonte": "foco", "ok": True,
                              "texto": (f"longe do PC por {round((f['fim'] - f['inicio']) / 60)} min"
                                        if f["atividade"] == "ausente" else
                                        f"{f['atividade']}{(' · ' + f['projeto']) if f.get('projeto') else ''} por "
                                        f"{round((f['fim'] - f['inicio']) / 60)} min")})
    except Exception as e:
        print(f"[Reconstrução] monitor: {e}")
    if incluir_arquivos:
        for ts, txt in _arquivos_mudados(ini, fim):
            itens.append({"ts": ts, "fonte": "arquivos", "texto": txt, "ok": True})
    return sorted(itens, key=lambda x: x["ts"])


# ── hipóteses (regras sobre os fatos) ──────────────────────────────────────────
def hipoteses(itens: list[dict]) -> list[str]:
    saida = []
    quedas = [i for i in itens if "internet fora" in i["texto"] or re.search(r"internet (caiu|fora)", i["texto"], re.I)]
    falhas = [i for i in itens if not i["ok"] and i["fonte"] in ("ferramenta", "protocolo", "habilidades", "registro")]
    for f in falhas:
        perto = [q for q in quedas if -120 <= f["ts"] - q["ts"] <= 600]
        if perto:
            saida.append(f"'{f['texto'][:60]}' pode ter falhado por causa da internet, que estava fora às "
                         f"{datetime.fromtimestamp(perto[0]['ts']):%H:%M}.")
            break
    cpu = [i for i in itens if "CPU acima de 90%" in i["texto"] or "RAM acima de 90%" in i["texto"]]
    lentas = [i for i in itens if i["fonte"] == "ferramenta" and re.search(r"\((\d{2,}\.\d) s\)", i["texto"])]
    if cpu:
        saida.append("O PC esteve sobrecarregado no período (" + "; ".join(c["texto"] for c in cpu[:2])
                     + "); travamentos e lentidão nessa hora provavelmente vêm daí.")
    elif lentas:
        saida.append("Algumas ferramentas demoraram mais de 10 s sem sobrecarga registrada; pode ter sido a rede "
                     "ou o próprio programa que estava sendo controlado.")
    nao_achou = [i for i in itens if re.search(r"n[aã]o (encontrei|achei)", i["texto"], re.I)]
    if nao_achou:
        saida.append(f"'{nao_achou[0]['texto'][:70]}': provavelmente o nome falado não bate com o do programa; "
                     "um apelido resolveria.")
    excecoes = [i for i in itens if re.search(r"exception|traceback|erro interno", i["texto"], re.I)]
    if excecoes:
        saida.append(f"Houve erro de programa ({excecoes[0]['texto'][:70]}); vale olhar o console do JARVIS.")
    ausente = [i for i in itens if i["texto"].startswith("longe do PC")]
    if ausente and any(not i["ok"] for i in itens):
        saida.append("Parte disso aconteceu enquanto você estava longe do PC, então ninguém viu os avisos na hora.")
    return saida


def reconstruir(texto_periodo: str = "", alvo: str = "", pergunta: str = "") -> dict:
    ini, fim, rotulo = periodo(texto_periodo or pergunta)
    itens = linha_do_tempo(ini.timestamp(), fim.timestamp())
    if alvo:
        a = alvo.lower()
        relacionados = [i for i in itens if a in i["texto"].lower()]
        if relacionados:          # mantém o contexto de 10 min em volta do que fala do alvo
            janelas = [(r["ts"] - 600, r["ts"] + 600) for r in relacionados]
            itens = [i for i in itens if any(x <= i["ts"] <= y for x, y in janelas)]
    hips = hipoteses(itens)
    extra = None
    try:
        from plugins import hipoteses as motor
        problema = pergunta or alvo
        if problema and motor.dominio_de(problema) not in (None, "app"):
            dom = motor.dominio_de(problema)
            ranking = motor.avaliar(dom, motor.coletar())
            if ranking:
                extra = f"Motor de hipóteses ({dom}): {ranking[0]['nome']} ({ranking[0]['confianca']:.0%})"
    except Exception:
        pass
    if extra:
        hips.append(extra)
    return {"rotulo": rotulo, "inicio": ini, "fim": fim, "fatos": itens, "hipoteses": hips}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    try:
        r = reconstruir(str(p.get("periodo") or ""), str(p.get("alvo") or ""), str(p.get("pergunta") or ""))
        fatos = r["fatos"]
        if not fatos:
            return f"Não há nada registrado {r['rotulo']}. O JARVIS só lembra do que aconteceu com ele aberto."
        linhas = [f"PERÍODO: {r['inicio']:%d/%m %H:%M} → {r['fim']:%d/%m %H:%M} ({r['rotulo']})", "",
                  "FATOS (registrados)"]
        linhas += [f"  {datetime.fromtimestamp(i['ts']):%H:%M:%S}  {'✖' if not i['ok'] else '·'} [{i['fonte']}] {i['texto']}"
                   for i in fatos[-250:]]
        linhas += ["", "HIPÓTESES (deduzidas — não comprovadas)"] + [f"  ? {h}" for h in r["hipoteses"] or ["nenhuma"]]
        mostrar(player, "RECONSTRUÇÃO", "\n".join(linhas))
        ruins = [i for i in fatos if not i["ok"]]
        fala = (f"{r['rotulo'].capitalize()}: {len(fatos)} registros. "
                + (f"Os pontos de atenção foram: {'; '.join(i['texto'][:70] for i in ruins[:3])}. " if ruins
                   else "Nada deu errado no que ficou registrado. ")
                + (f"Hipótese principal: {r['hipoteses'][0]}" if r["hipoteses"] else ""))
        return fala
    except Exception as e:
        return f"Não consegui reconstruir: {e}"
