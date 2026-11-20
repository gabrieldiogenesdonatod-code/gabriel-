"""
Detector de oportunidades — ideia 11 (fork PT-BR 1.4).

Uma vez por dia o JARVIS olha o seu uso e o estado do PC procurando o que
pode ser AUTOMATIZADO ou MELHORADO — e sugere, sem fazer nada sozinho:

    • rotina repetida (mesma sequência de ferramentas em vários dias)
      → "quer que eu transforme em uma ferramenta?" (criador de ferramentas)
    • o mesmo pedido, perto da mesma hora, em 4 dias ou mais
      → "quer que eu agende para as 8h40 de segunda a sexta?" (agendador)
    • mais de 30 arquivos soltos nos Downloads → organizar
    • mais de 10 programas abrindo com o Windows → revisar a inicialização
    • avisos de disco cheio se repetindo → limpeza agendada toda semana
    • uma ferramenta que falha muito → investigar com o motor de hipóteses
    • lições da memória contrafactual ainda não aplicadas

Cada sugestão tem um número. "Jarvis, quais oportunidades você viu?",
"aceita a 2", "recusa a 3" (recusada não volta). No máximo UMA sugestão
falada por dia, entre 9h e 21h, e nunca no meio de uma conversa.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from datetime import datetime

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "oportunidades",
    "brief": "Finds things worth automating or fixing from usage and PC state; suggests, never acts alone.",
    "description": (
        "Opportunity detector: finds what is worth automating or fixing (repeated routines → new tool, "
        "same request at the same time → schedule, messy Downloads, too many startup apps, recurring "
        "low-disk warnings, a tool that fails a lot, unapplied lessons). action='listar' ('what "
        "opportunities did you see?'), 'analisar' (look now), 'aceitar' with id, 'recusar' with id."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "listar | analisar | aceitar | recusar"},
            "id": {"type": "STRING"},
        },
        "required": [],
    },
}

_ARQ = MEMORIA / "oportunidades.json"
_iniciado = threading.Event()
_META = {"oportunidades", "radar_anomalias", "memoria_contrafactual", "reconstrucao", "guardiao_decisoes",
         "criador_ferramentas", "notificacoes"}


# ── detectores (puros, recebem os dados) ───────────────────────────────────────
def pedidos_no_mesmo_horario(chamadas: list[dict], min_dias: int = 4, tolerancia_min: int = 45) -> list[dict]:
    """Mesmo (ferramenta, ação, alvo) em ≥ min_dias dias diferentes, perto da mesma hora."""
    grupos = defaultdict(list)
    for c in chamadas:
        if c["ferramenta"] in _META or not c.get("ok", 1):
            continue
        try:
            params = json.loads(c.get("params") or "{}")
        except Exception:
            params = {}
        alvo = str(params.get("alvo") or params.get("app_name") or params.get("nome") or "").lower()
        grupos[(c["ferramenta"], c.get("acao") or "", alvo)].append((c["ts"], params))
    saida = []
    for (f, a, alvo), lista in grupos.items():
        por_dia = {}
        for ts, params in lista:
            dt = datetime.fromtimestamp(ts)
            por_dia.setdefault(dt.date(), (dt.hour * 60 + dt.minute, dt.weekday(), params))
        if len(por_dia) < min_dias:
            continue
        minutos = sorted(v[0] for v in por_dia.values())
        mediana = minutos[len(minutos) // 2]
        perto = [v for v in por_dia.values() if abs(v[0] - mediana) <= tolerancia_min]
        if len(perto) < min_dias:
            continue
        dias_semana = sorted({v[1] for v in perto})
        saida.append({"ferramenta": f, "acao": a, "alvo": alvo, "dias": len(perto),
                      "hora": f"{mediana // 60:02d}:{mediana % 60:02d}",
                      "dias_semana": [0, 1, 2, 3, 4] if set(dias_semana) <= {0, 1, 2, 3, 4} and len(dias_semana) >= 3
                      else ([] if len(dias_semana) >= 6 else dias_semana),
                      "params": perto[-1][2]})
    return saida


def ferramentas_falhando(chamadas: list[dict], minimo: int = 5, taxa: float = 0.4) -> list[tuple[str, int, int]]:
    por = defaultdict(lambda: [0, 0])
    for c in chamadas:
        por[c["ferramenta"]][0] += 1
        if not c.get("ok", 1):
            por[c["ferramenta"]][1] += 1
    return [(f, n, fal) for f, (n, fal) in por.items() if n >= minimo and fal / n >= taxa and f not in _META]


_DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _texto_dias(dias: list[int]) -> str:
    if not dias:
        return "todo dia"
    if dias == [0, 1, 2, 3, 4]:
        return "de segunda a sexta"
    return ", ".join(_DIAS[d] for d in dias)


# ── coleta das sugestões ───────────────────────────────────────────────────────
def detectar() -> list[dict]:
    from core import registro_uso
    agora = time.time()
    cham = registro_uso.chamadas(agora - 30 * 86400)
    sug = []
    try:
        from plugins import criador_ferramentas
        for s in criador_ferramentas.sequencias_repetidas(cham)[:3]:
            if s["dias"] >= 2:
                sug.append({"chave": f"seq:{s['id']}", "tipo": "ferramenta",
                            "texto": f"Você repete esta rotina ({s['vezes']} vezes): "
                                     + ", depois ".join(x["descricao"] for x in s["passos"])
                                     + ". Posso juntar tudo numa ferramenta só.",
                            "dados": {"id": s["id"]}})
    except Exception as e:
        print(f"[Oportunidades] sequências: {e}")
    for h in pedidos_no_mesmo_horario(cham):
        desc = f"{h['ferramenta']} {h['acao']} {h['alvo']}".strip()
        sug.append({"chave": f"agenda:{h['ferramenta']}:{h['acao']}:{h['alvo']}", "tipo": "agendar",
                    "texto": f"Você pede '{desc}' perto das {h['hora']} ({h['dias']} dias). Quer que eu "
                             f"agende para as {h['hora']}, {_texto_dias(h['dias_semana'])}?",
                    "dados": h})
    try:
        from plugins import downloads
        soltos = [a for a in downloads.pasta().iterdir() if a.is_file() and not downloads.eh_parcial(a.name)]
        if len(soltos) > 30:
            sug.append({"chave": "downloads", "tipo": "downloads",
                        "texto": f"Há {len(soltos)} arquivos soltos nos Downloads. Posso organizar por tipo.",
                        "dados": {}})
    except Exception:
        pass
    try:
        from plugins.controle_sistema import listar_inicializacao
        ativos = [i for i in listar_inicializacao() if i.get("ativo")]
        if len(ativos) > 10:
            sug.append({"chave": "inicializacao", "tipo": "inicializacao",
                        "texto": f"{len(ativos)} programas abrem junto com o Windows. Desligar alguns deixa o "
                                 "boot mais rápido. Quer ver a lista?", "dados": {}})
    except Exception:
        pass
    try:
        from plugins import _monitor_db
        disco = [e for e in _monitor_db.eventos(agora - 14 * 86400, 500) if "disco" in (e.get("mensagem") or "").lower()
                 and e.get("tipo") in ("alerta", "aviso")]
        if len(disco) >= 3:
            sug.append({"chave": "limpeza_semanal", "tipo": "limpeza",
                        "texto": f"O aviso de disco cheio apareceu {len(disco)} vezes em 2 semanas. Quer uma "
                                 "limpeza agendada todo domingo às 20h (com confirmação)?", "dados": {}})
    except Exception:
        pass
    for f, n, fal in ferramentas_falhando(cham):
        sug.append({"chave": f"falha:{f}", "tipo": "investigar",
                    "texto": f"A ferramenta {f} falhou {fal} de {n} vezes no último mês. Quer que eu investigue?",
                    "dados": {"ferramenta": f}})
    try:
        from plugins import memoria_contrafactual
        for l in memoria_contrafactual.carregar():
            if not l.get("aplicada") and (l.get("economia_s", 0) >= 3 or l.get("aplicavel")):
                sug.append({"chave": f"licao:{l['id']}", "tipo": "licao", "texto": l["texto"],
                            "dados": {"id": l["id"]}})
    except Exception:
        pass
    return sug


def _estado() -> dict:
    e = ler_json(_ARQ, {}) or {}
    e.setdefault("sugestoes", [])
    e.setdefault("recusadas", [])
    e.setdefault("ultima_fala", "")
    e.setdefault("proximo_id", 1)
    return e


def analisar() -> list[dict]:
    e = _estado()
    conhecidas = {s["chave"] for s in e["sugestoes"]} | set(e["recusadas"])
    novas = []
    for s in detectar():
        if s["chave"] in conhecidas:
            continue
        s.update(id=str(e["proximo_id"]), status="nova", criada=time.strftime("%Y-%m-%d %H:%M"))
        e["proximo_id"] += 1
        e["sugestoes"].append(s)
        novas.append(s)
    e["sugestoes"] = e["sugestoes"][-60:]
    e["analisado"] = time.time()
    gravar_json(_ARQ, e)
    return novas


def aceitar(ident: str, player=None) -> str:
    e = _estado()
    s = next((x for x in e["sugestoes"] if x["id"] == ident), None)
    if not s:
        return f"Não tenho a sugestão {ident}."
    d, tipo = s.get("dados", {}), s["tipo"]
    from core import registro_ferramentas as rf
    if tipo == "ferramenta":
        r = rf.executar("criador_ferramentas", {"action": "criar_sequencia", "id": d["id"]}, player)
    elif tipo == "agendar":
        from plugins import agendador
        quando = {"tipo": "semanal", "hora": d["hora"], "dias": d.get("dias_semana") or []}
        if d["ferramenta"] in ("open_app",) or (d["ferramenta"] == "controle_pc" and d["acao"] == "abrir"):
            t = agendador.adicionar("abrir_app", d["alvo"], quando)
        elif d["ferramenta"] == "protocolos":
            t = agendador.adicionar("protocolo", d["alvo"], quando)
        else:
            t = agendador.adicionar("comando", f"{d['ferramenta']} {d['acao']} {d['alvo']}".strip(), quando)
        r = f"Agendado: {t['descricao']}, {agendador.descrever_quando(quando)}."
    elif tipo == "downloads":
        r = rf.executar("downloads", {"action": "organizar"}, player)
    elif tipo == "inicializacao":
        r = rf.executar("controle_sistema", {"action": "inicializacao"}, player)
    elif tipo == "limpeza":
        from plugins import agendador
        t = agendador.adicionar("limpeza", "", {"tipo": "semanal", "hora": "20:00", "dias": [6]})
        r = f"Agendei a limpeza (com confirmação na hora): {agendador.descrever_quando(t['quando'])}."
    elif tipo == "investigar":
        r = rf.executar("hipoteses", {"problema": f"a ferramenta {d['ferramenta']} está falhando"}, player)
    elif tipo == "licao":
        from plugins import memoria_contrafactual
        r = memoria_contrafactual.aplicar(d["id"])
    else:
        r = "Não sei aplicar esse tipo de sugestão."
    s["status"] = "aceita"
    gravar_json(_ARQ, e)
    return r


def recusar(ident: str) -> str:
    e = _estado()
    s = next((x for x in e["sugestoes"] if x["id"] == ident), None)
    if not s:
        return f"Não tenho a sugestão {ident}."
    s["status"] = "recusada"
    e["recusadas"].append(s["chave"])
    gravar_json(_ARQ, e)
    return "Tudo bem, não sugiro mais isso."


def _pode_falar(e: dict) -> bool:
    agora = datetime.now()
    if e.get("ultima_fala") == agora.date().isoformat() or not (9 <= agora.hour < 21):
        return False
    try:
        from core import registro_uso
        if registro_uso.chamadas(time.time() - 300):       # conversa acontecendo: não interrompe
            return False
    except Exception:
        pass
    return True


def _laco(player) -> None:
    time.sleep(600)
    while True:
        try:
            e = _estado()
            if time.time() - float(e.get("analisado") or 0) > 20 * 3600:
                analisar()
                e = _estado()
            novas = [s for s in e["sugestoes"] if s["status"] == "nova" and not s.get("falada")]
            if novas and _pode_falar(e):
                s = novas[0]
                s["falada"] = True
                e["ultima_fala"] = datetime.now().date().isoformat()
                gravar_json(_ARQ, e)
                from plugins._notificar import notificar
                notificar(player, f"Uma sugestão (número {s['id']}): {s['texto']}", titulo="Oportunidade",
                          etiqueta="OPORTUNIDADE")
        except Exception as ex:
            print(f"[Oportunidades] {ex}")
        time.sleep(1800)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="oportunidades").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    ident = str(p.get("id") or "").strip().lstrip("#")
    try:
        if acao == "aceitar":
            return aceitar(ident, player)
        if acao == "recusar":
            return recusar(ident)
        if acao == "analisar":
            analisar()
        e = _estado()
        abertas = [s for s in e["sugestoes"] if s["status"] == "nova"]
        if not abertas:
            return "Não vi nenhuma oportunidade nova. Eu olho de novo uma vez por dia."
        mostrar(player, "OPORTUNIDADES", "\n\n".join(f"[{s['id']}] {s['texto']}" for s in abertas))
        return (f"{len(abertas)} sugestão(ões). A primeira (número {abertas[0]['id']}): {abertas[0]['texto']} "
                "Diga 'aceita' ou 'recusa' com o número.")
    except Exception as ex:
        return f"O detector de oportunidades falhou: {ex}"
