"""
Agendador de tarefas — plugin do J.A.R.V.I.S BR.

    "Jarvis, todo dia às 8 abre o WhatsApp"
    "Jarvis, toda sexta às 18h faz limpeza"
    "Jarvis, às 23h desliga o PC"
    "Jarvis, de segunda a sexta às 9h ativa o protocolo foco"
    "Jarvis, a cada 60 minutos me lembra de beber água"
    "Jarvis, quais tarefas eu agendei?" / "apaga a tarefa da limpeza"

As tarefas ficam em memory/agendador.json e sobrevivem ao reinício. Se o PC
estava desligado na hora, a tarefa roda ao ligar se o atraso for de até 15
minutos; senão, pula para a próxima vez (ninguém quer o PC desligando sozinho
uma hora depois de ligado).

Desligar, reiniciar e limpeza pedem confirmação NA HORA DE AGENDAR. Na hora de
rodar, desligar/reiniciar dão 2 minutos de aviso para você cancelar.
"""

from __future__ import annotations

import re
import threading
import unicodedata
from datetime import datetime, timedelta

from plugins._comum import (MEMORIA, WIN, confirmar, falar, gravar_json, ler_json,
                            mostrar, num, plugin_ligado, registrar)

PLUGIN = {
    "name": "agendador",
    "brief": "Create/list/delete/pause scheduled tasks (open app, protocol, cleanup, shutdown, reminder, command).",
    "description": (
        "Scheduled tasks. action='criar' with acao = abrir_app | protocolo | limpeza | "
        "desligar | reiniciar | lembrete | comando | modo_jogo | saude | organizar_downloads, "
        "alvo (app name, protocol name, reminder text, or for 'comando' the full request "
        "to run, e.g. 'manda o resumo do PC'), hora ('08:00', '23h', 'meio-dia'), dias "
        "('todo dia', 'sexta', 'segunda a sexta', 'fim de semana', 'seg,qua'), data "
        "('2026-11-05' or 'amanhã') for one-off, minutos for 'a cada N minutos'. "
        "action='listar', 'apagar' (alvo = id or words of the task), 'pausar' / 'retomar'. "
        "Use this for anything recurring or at a future time; use the reminder tool only "
        "for simple one-off OS reminders."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "criar | listar | apagar | pausar | retomar"},
            "acao": {"type": "STRING"}, "alvo": {"type": "STRING"},
            "hora": {"type": "STRING"}, "dias": {"type": "STRING"},
            "data": {"type": "STRING"}, "minutos": {"type": "NUMBER"},
        },
        "required": ["action"],
    },
}

ARQUIVO = MEMORIA / "agendador.json"
ACOES = ("abrir_app", "protocolo", "limpeza", "desligar", "reiniciar", "lembrete",
         "comando", "modo_jogo", "saude", "organizar_downloads")
PERIGOSAS = ("desligar", "reiniciar", "limpeza")
ATRASO_MAX = 15 * 60
_DIAS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
_NOMES_DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

_lock = threading.Lock()
_thread: threading.Thread | None = None
_parar = threading.Event()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()


# ── interpretação ──────────────────────────────────────────────────────────────
def parse_hora(texto) -> tuple[int, int] | None:
    t = _dobrar(texto).replace("as ", "").replace("às", "").strip()
    if not t:
        return None
    if "meio-dia" in t or "meio dia" in t:
        return 12, 0
    if "meia-noite" in t or "meia noite" in t:
        return 0, 0
    m = re.search(r"(\d{1,2})\s*(?:[:h]\s*(\d{2})?)?\s*(?:min)?", t)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if ("da noite" in t or "da tarde" in t or "pm" in t) and h < 12:
        h += 12
    if "da manha" in t and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def parse_dias(texto) -> list[int]:
    """Dias da semana (segunda=0). Lista vazia = todos os dias."""
    t = _dobrar(texto)
    if not t or any(x in t for x in ("todo dia", "todos os dias", "diario", "diariamente", "sempre")):
        return []
    if "util" in t or "uteis" in t:
        return [0, 1, 2, 3, 4]
    if "fim de semana" in t or "fins de semana" in t:
        return [5, 6]
    abrev = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6}
    m = re.search(r"(seg|ter|qua|qui|sex|sab|dom)\w*\s+a\s+(seg|ter|qua|qui|sex|sab|dom)", t)
    if m:
        a, b = abrev[m.group(1)], abrev[m.group(2)]
        return list(range(a, b + 1)) if a <= b else list(range(a, 7)) + list(range(0, b + 1))
    dias = sorted({v for k, v in abrev.items() if re.search(rf"\b{k}", t)})
    return dias


def parse_data(texto, agora: datetime) -> datetime | None:
    t = _dobrar(texto)
    if not t:
        return None
    if t in ("hoje",):
        return agora.replace(hour=0, minute=0, second=0, microsecond=0)
    if t in ("amanha",):
        return (agora + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    # "05/11" sem ano: este ano, ou o próximo se a data já passou
    try:
        d = datetime.strptime(f"{t}/{agora.year}", "%d/%m/%Y")
        if d.date() < agora.date():
            d = d.replace(year=agora.year + 1)
        return d
    except ValueError:
        return None


def montar_quando(hora, dias, data, minutos, agora: datetime | None = None) -> dict | None:
    agora = agora or datetime.now()
    if num(minutos, 0) > 0 and not hora:
        return {"tipo": "intervalo", "minutos": int(num(minutos))}
    hm = parse_hora(hora)
    if hm is None:
        return None
    d = parse_data(data, agora)
    if d is not None:
        return {"tipo": "unico", "quando": d.replace(hour=hm[0], minute=hm[1]).isoformat(timespec="minutes")}
    if not dias:
        # "às 23h desliga o PC" sem dia = só uma vez, a próxima 23h.
        alvo = agora.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        if alvo <= agora:
            alvo += timedelta(days=1)
        return {"tipo": "unico", "quando": alvo.isoformat(timespec="minutes")}
    return {"tipo": "semanal", "hora": f"{hm[0]:02d}:{hm[1]:02d}", "dias": parse_dias(dias)}


def proxima_execucao(quando: dict, depois_de: datetime) -> datetime | None:
    tipo = quando.get("tipo")
    if tipo == "intervalo":
        return depois_de + timedelta(minutes=max(1, int(quando.get("minutos", 60))))
    if tipo == "unico":
        alvo = datetime.fromisoformat(quando["quando"])
        return alvo if alvo > depois_de else None
    h, m = map(int, quando["hora"].split(":"))
    dias = quando.get("dias") or list(range(7))
    for adiante in range(0, 8):
        dia = depois_de + timedelta(days=adiante)
        alvo = dia.replace(hour=h, minute=m, second=0, microsecond=0)
        if alvo > depois_de and alvo.weekday() in dias:
            return alvo
    return None


def descrever_quando(q: dict) -> str:
    if q["tipo"] == "intervalo":
        return f"a cada {q['minutos']} min"
    if q["tipo"] == "unico":
        return datetime.fromisoformat(q["quando"]).strftime("em %d/%m às %H:%M")
    dias = q.get("dias") or []
    if not dias or len(dias) == 7:
        quando = "todo dia"
    elif dias == [0, 1, 2, 3, 4]:
        quando = "de segunda a sexta"
    elif dias == [5, 6]:
        quando = "no fim de semana"
    else:
        quando = "às " + ", ".join(_NOMES_DIAS[d] for d in dias)
    return f"{quando} às {q['hora']}"


# ── armazenamento ──────────────────────────────────────────────────────────────
def carregar() -> list[dict]:
    d = ler_json(ARQUIVO, [])
    return d if isinstance(d, list) else []


def salvar(tarefas: list[dict]) -> None:
    gravar_json(ARQUIVO, tarefas)


def _descricao(acao: str, alvo: str) -> str:
    return {"abrir_app": f"abrir {alvo}", "protocolo": f"protocolo {alvo}", "limpeza": "limpeza do PC",
            "desligar": "desligar o PC", "reiniciar": "reiniciar o PC", "lembrete": f"lembrete: {alvo}",
            "comando": alvo, "modo_jogo": f"modo jogo {alvo or 'ligar'}", "saude": "relatório de saúde do PC",
            "organizar_downloads": "organizar a pasta Downloads"}.get(acao, acao)


def adicionar(acao: str, alvo: str, quando: dict, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now()
    with _lock:
        tarefas = carregar()
        novo_id = max([int(t["id"]) for t in tarefas if str(t.get("id", "")).isdigit()] + [0]) + 1
        prox = proxima_execucao(quando, agora)
        t = {"id": str(novo_id), "acao": acao, "alvo": alvo, "quando": quando,
             "descricao": _descricao(acao, alvo), "ativo": True,
             "proxima": prox.isoformat(timespec="seconds") if prox else None, "ultima": None}
        tarefas.append(t)
        salvar(tarefas)
    return t


def vencidas(tarefas: list[dict], agora: datetime) -> list[dict]:
    """As que devem rodar agora (pura: dá para testar)."""
    saida = []
    for t in tarefas:
        if not t.get("ativo") or not t.get("proxima"):
            continue
        prox = datetime.fromisoformat(t["proxima"])
        if prox <= agora:
            saida.append(t)
    return saida


# ── execução ───────────────────────────────────────────────────────────────────
def executar(t: dict, player) -> str:
    acao, alvo = t["acao"], t.get("alvo") or ""
    if acao == "abrir_app":
        from actions.open_app import open_app
        open_app({"app_name": alvo}, player=player)
        return f"abrindo {alvo}"
    if acao == "protocolo":
        from plugins.protocolos import run as protocolo
        return protocolo({"action": "executar", "nome": alvo}, player)
    if acao == "limpeza":
        from plugins.limpeza import CATEGORIAS, executar as limpar
        return limpar(list(CATEGORIAS))
    if acao in ("desligar", "reiniciar"):
        if WIN:
            from plugins._comum import rodar
            rodar(["shutdown", "/s" if acao == "desligar" else "/r", "/t", "120"])
        else:
            from plugins.controle_pc import _cmd_energia
            fn = _cmd_energia(acao)
            if fn:
                tm = threading.Timer(120, fn)
                tm.daemon = True
                tm.start()
                from plugins import controle_pc
                controle_pc._agendamento.update({"operacao": acao, "timer": tm})
        falar(player, f"[TAREFA AGENDADA] Avise que o PC vai {acao} em 2 minutos, como foi "
                      "agendado, e que dá para cancelar dizendo 'cancela o desligamento'. Uma frase.")
        return f"{acao} em 2 minutos"
    if acao == "lembrete":
        falar(player, f"[LEMBRETE AGENDADO] Lembre o usuário, em uma frase natural: {alvo}")
        return "lembrete dado"
    if acao == "comando":
        falar(player, f"[TAREFA AGENDADA PELO USUÁRIO] Na hora marcada, faça agora o que o usuário "
                      f"pediu quando agendou: \"{alvo}\". Use as ferramentas necessárias.")
        return "comando enviado"
    if acao == "modo_jogo":
        from plugins.modo_jogo import desligar, ligar
        return desligar(player) if "deslig" in alvo or "normal" in alvo else ligar(player)
    if acao == "saude":
        from plugins.saude_pc import run as saude
        r = saude({"action": "relatorio"}, player)
        falar(player, f"[TAREFA AGENDADA] Conte em uma ou duas frases: {r}")
        return "relatório gerado"
    if acao == "organizar_downloads":
        from plugins.downloads import organizar
        return organizar(player)
    return "ação desconhecida"


def _laco(player):
    while not _parar.wait(20):
        if not plugin_ligado("agendador"):
            continue
        agora = datetime.now()
        with _lock:
            tarefas = carregar()
            para_rodar = []
            for t in vencidas(tarefas, agora):
                atraso = (agora - datetime.fromisoformat(t["proxima"])).total_seconds()
                if atraso <= ATRASO_MAX:
                    para_rodar.append(dict(t))
                t["ultima"] = agora.isoformat(timespec="seconds") if atraso <= ATRASO_MAX else t.get("ultima")
                prox = proxima_execucao(t["quando"], agora)
                t["proxima"] = prox.isoformat(timespec="seconds") if prox else None
                if prox is None:
                    t["ativo"] = False
            salvar(tarefas)
        for t in para_rodar:
            try:
                r = executar(t, player)
                registrar(player, f"Tarefa agendada #{t['id']} ({t['descricao']}): {r}")
            except Exception as e:
                registrar(player, f"Tarefa agendada #{t['id']} falhou: {e}")


def on_session_start(player) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _parar.clear()
    _thread = threading.Thread(target=_laco, args=(player,), daemon=True, name="agendador")
    _thread.start()


def _achar(tarefas: list[dict], alvo: str) -> dict | None:
    alvo_d = _dobrar(alvo)
    for t in tarefas:
        if alvo_d == str(t["id"]) or alvo_d.lstrip("#") == str(t["id"]):
            return t
    palavras = [p for p in alvo_d.split() if len(p) > 2]
    melhores = [t for t in tarefas if palavras and all(p in _dobrar(t["descricao"]) for p in palavras)]
    return melhores[0] if len(melhores) == 1 else None


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "").strip().lower()
    try:
        if a == "criar":
            acao = _dobrar(p.get("acao")).replace(" ", "_")
            if acao not in ACOES:
                return "Que tipo de tarefa? " + ", ".join(ACOES) + "."
            alvo = str(p.get("alvo") or "").strip()
            if acao in ("abrir_app", "protocolo", "lembrete", "comando") and not alvo:
                return "Falta dizer o quê (o app, o protocolo ou o texto)."
            quando = montar_quando(p.get("hora"), p.get("dias"), p.get("data"), p.get("minutos"))
            if quando is None:
                return "Não entendi o horário. Diga, por exemplo, 'às 8h' ou 'a cada 30 minutos'."
            texto = f"{_descricao(acao, alvo)}, {descrever_quando(quando)}"
            if acao in PERIGOSAS:
                return confirmar(f"agendar-{acao}", f"Agendar: {texto}",
                                 "Na hora, desligar e reiniciar ainda dão 2 minutos de aviso.",
                                 lambda: f"Agendado (#{adicionar(acao, alvo, quando)['id']}): {texto}.")
            t = adicionar(acao, alvo, quando)
            return f"Agendado (#{t['id']}): {texto}."
        tarefas = carregar()
        if a == "listar":
            ativas = [t for t in tarefas if t.get("ativo")]
            if not tarefas:
                return "Nenhuma tarefa agendada."
            mostrar(player, "TAREFAS AGENDADAS", "\n".join(
                f"#{t['id']:<3} {'●' if t.get('ativo') else '○'} {t['descricao'][:40]:<40} "
                f"{descrever_quando(t['quando'])}"
                + (f"   próxima {datetime.fromisoformat(t['proxima']).strftime('%d/%m %H:%M')}"
                   if t.get("proxima") else "") for t in tarefas))
            return f"{len(ativas)} tarefa(s) ativa(s): " + "; ".join(
                f"{t['descricao']} {descrever_quando(t['quando'])}" for t in ativas[:5]) + "."
        if a in ("apagar", "pausar", "retomar"):
            t = _achar(tarefas, str(p.get("alvo") or ""))
            if not t:
                return "Não achei essa tarefa. Diga o número dela (veja a lista)."
            with _lock:
                tarefas = carregar()
                t = next(x for x in tarefas if x["id"] == t["id"])
                if a == "apagar":
                    tarefas.remove(t)
                else:
                    t["ativo"] = a == "retomar"
                    if t["ativo"]:
                        prox = proxima_execucao(t["quando"], datetime.now())
                        t["proxima"] = prox.isoformat(timespec="seconds") if prox else None
                salvar(tarefas)
            verbo = {"apagar": "apagada", "pausar": "pausada", "retomar": "retomada"}[a]
            return f"Tarefa #{t['id']} ({t['descricao']}) {verbo}."
        return "Use criar, listar, apagar, pausar ou retomar."
    except Exception as e:
        return f"O agendador falhou: {e}"
