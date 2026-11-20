"""
Cérebro de prioridades adaptativas — ideia 15 (fork PT-BR 1.4).

Uma fila de tarefas que se REORDENA sozinha conforme o momento:

    nota = importância·2 + urgência·1,5 + prazo (atrasada +6, < 24 h +4,
           < 3 dias +2, < 1 semana +1) + tempo esperando (até +2)
    fora da conta: bloqueada, esperando outra tarefa, precisa de internet e
    a internet caiu, ou não cabe no tempo que você tem
    ajuste: PC sobrecarregado → tarefas pesadas descem, leves sobem;
    a que você já começou ganha um empurrão (continuidade)

E APRENDE: compara quanto você estimou com quanto levou de verdade e passa
a corrigir as estimativas ("você costuma levar 1,4× o que estima").

    "Jarvis, adiciona tarefa: responder os clientes da loja, importante, até amanhã"
    "Jarvis, o que eu faço agora?"            "Jarvis, tenho 30 minutos, o que dá?"
    "Jarvis, estou bloqueado no deploy porque o servidor caiu"
    "Jarvis, comecei o relatório"   …   "Jarvis, terminei o relatório"
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, num

PLUGIN = {
    "name": "prioridades",
    "brief": "Adaptive to-do priorities: what to do now, blocked tasks, available time, learns estimates.",
    "description": (
        "Adaptive priority brain for the user's tasks. action='adicionar' (titulo, importancia 1-5, "
        "urgencia 1-5, prazo as said e.g. 'amanhã 18h', duracao in minutes, depende_de, recurso: "
        "internet|pc_pesado|leve), 'agora' ('what should I do now', optional minutos available), "
        "'bloquear' (titulo + motivo: 'I'm blocked on X because Y'), 'desbloquear', 'comecar', "
        "'concluir' (titulo), 'listar', 'remover'. Explain the reason for the pick."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "adicionar | agora | bloquear | desbloquear | comecar | concluir | listar | remover"},
            "titulo": {"type": "STRING"}, "importancia": {"type": "INTEGER"}, "urgencia": {"type": "INTEGER"},
            "prazo": {"type": "STRING"}, "duracao": {"type": "INTEGER"}, "depende_de": {"type": "STRING"},
            "recurso": {"type": "STRING"}, "motivo": {"type": "STRING"}, "minutos": {"type": "INTEGER"},
        },
        "required": ["action"],
    },
}

_ARQ = MEMORIA / "prioridades.json"


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def carregar() -> dict:
    d = ler_json(_ARQ, {}) or {}
    d.setdefault("tarefas", [])
    d.setdefault("fator", 1.0)
    d.setdefault("amostras_fator", 0)
    return d


def salvar(d: dict) -> None:
    gravar_json(_ARQ, d)


def achar(d: dict, termo: str, incluir_feitas: bool = False) -> dict | None:
    t = _dobrar(termo).strip()
    if not t:
        return None
    candidatas = [x for x in d["tarefas"] if incluir_feitas or x["status"] != "feita"]
    for x in candidatas:
        if x["id"] == t.lstrip("#"):
            return x
    palavras = [w for w in re.findall(r"\w{3,}", t)]
    melhor, nota = None, 0
    for x in candidatas:
        tit = _dobrar(x["titulo"])
        n = sum(1 for w in palavras if w in tit) + (3 if t in tit else 0)
        if n > nota:
            melhor, nota = x, n
    return melhor


_SEMANA = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def _prazo(texto: str, agora: datetime) -> str:
    """'amanhã 18h', 'sexta', 'dia 15', '20/11 às 9h', 'em 3 dias', 'hoje à noite' → ISO (ou '')."""
    t = _dobrar(texto).strip()
    if not t:
        return ""
    dia = None
    if "depois de amanha" in t:
        dia = agora.date() + timedelta(days=2)
    elif "amanha" in t:
        dia = agora.date() + timedelta(days=1)
    elif "hoje" in t:
        dia = agora.date()
    m = re.search(r"em (\d+) dias?", t)
    if m:
        dia = agora.date() + timedelta(days=int(m.group(1)))
    if "semana que vem" in t or "proxima semana" in t:
        dia = agora.date() + timedelta(days=7 - agora.weekday())
    for i, nome in enumerate(_SEMANA):
        if re.search(rf"\b{nome}", t):
            adiante = (i - agora.weekday()) % 7 or 7
            dia = agora.date() + timedelta(days=adiante)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if m:
        ano = int(m.group(3)) if m.group(3) else agora.year
        ano += 2000 if ano < 100 else 0
        try:
            dia = datetime(ano, int(m.group(2)), int(m.group(1))).date()
            if not m.group(3) and dia < agora.date():
                dia = dia.replace(year=ano + 1)
        except ValueError:
            pass
    else:
        m = re.search(r"\bdia (\d{1,2})\b", t)
        if m:
            try:
                dia = agora.date().replace(day=int(m.group(1)))
                if dia < agora.date():
                    dia = (dia.replace(day=1) + timedelta(days=32)).replace(day=int(m.group(1)))
            except ValueError:
                pass
    hora = None
    m = re.search(r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?|\bas (\d{1,2})\b", t)
    if m and not re.search(r"\d{1,2}/\d{1,2}\s*$", t[:m.end()]):
        hh = int(m.group(1) or m.group(3))
        hora = (hh % 24, int(m.group(2) or 0))
    elif "noite" in t:
        hora = (20, 0)
    elif "tarde" in t:
        hora = (15, 0)
    elif "manha" in t:
        hora = (9, 0)
    if dia is None and hora is None:
        return ""
    dia = dia or agora.date()
    h, mi = hora or (23, 59)
    alvo = datetime.combine(dia, datetime.min.time()).replace(hour=h, minute=mi)
    if alvo < agora and hora and dia == agora.date():
        alvo += timedelta(days=1)
    return alvo.isoformat(timespec="minutes")


# ── a nota (pura) ──────────────────────────────────────────────────────────────
def pontuar(t: dict, todas: list[dict], agora: datetime, contexto: dict) -> tuple[float | None, list[str]]:
    """(nota ou None se não dá para fazer agora, motivos)."""
    motivos = []
    if t["status"] == "feita":
        return None, ["já feita"]
    if t["status"] == "bloqueada":
        return None, [f"bloqueada: {t.get('motivo_bloqueio') or 'sem motivo'}"]
    pendentes = {x["id"] for x in todas if x["status"] != "feita"}
    espera = [x for x in t.get("depende_de", []) if x in pendentes]
    if espera:
        nomes = [x["titulo"] for x in todas if x["id"] in espera]
        return None, [f"espera: {', '.join(nomes)}"]
    if t.get("recurso") == "internet" and contexto.get("internet") is False:
        return None, ["precisa de internet, e a internet está fora"]
    nota = t.get("importancia", 3) * 2 + t.get("urgencia", 3) * 1.5
    if t.get("importancia", 3) >= 4:
        motivos.append("importante")
    if t.get("prazo"):
        horas = (datetime.fromisoformat(t["prazo"]) - agora).total_seconds() / 3600
        if horas < 0:
            nota += 6
            motivos.append("ATRASADA")
        elif horas < 24:
            nota += 4
            motivos.append(f"vence em {max(1, round(horas))} h")
        elif horas < 72:
            nota += 2
            motivos.append(f"vence em {round(horas / 24)} dia(s)")
        elif horas < 168:
            nota += 1
    dias = (agora - datetime.fromisoformat(t["criada"])).total_seconds() / 86400
    if dias >= 3:
        nota += min(2.0, dias * 0.15)
        motivos.append(f"esperando há {int(dias)} dias")
    estimada = (t.get("duracao_min") or 30) * contexto.get("fator", 1.0)
    disponivel = contexto.get("minutos")
    if disponivel:
        if estimada > disponivel * 1.15:
            return None, [f"não cabe em {disponivel} min (estimo {round(estimada)} min)"]
        motivos.append(f"cabe nos {disponivel} min")
    if contexto.get("pc_carregado"):
        if t.get("recurso") == "pc_pesado":
            nota -= 2
            motivos.append("o PC está carregado")
        elif t.get("recurso") == "leve":
            nota += 1
    if t["status"] == "fazendo":
        nota += 1.5
        motivos.append("já começou")
    return round(nota, 2), motivos


def ranking(d: dict, agora: datetime | None = None, contexto: dict | None = None) -> tuple[list, list]:
    agora = agora or datetime.now()
    contexto = dict(contexto or {})
    contexto.setdefault("fator", d.get("fator", 1.0))
    podem, nao = [], []
    for t in d["tarefas"]:
        if t["status"] == "feita":
            continue
        nota, motivos = pontuar(t, d["tarefas"], agora, contexto)
        (nao if nota is None else podem).append((nota, t, motivos))
    podem.sort(key=lambda x: -x[0])
    return podem, nao


def contexto_atual(minutos=None) -> dict:
    c = {"minutos": int(minutos) if minutos else None}
    try:
        from core import telemetria
        s = telemetria.get().snapshot()
        c["internet"] = s.get("internet")
        c["pc_carregado"] = (s.get("cpu") or 0) > 80 or ((s.get("ram") or {}).get("pct") or 0) > 88
    except Exception:
        pass
    return c


def aprender_fator(d: dict, estimada_min: float, real_min: float) -> None:
    if estimada_min <= 0 or real_min <= 0:
        return
    razao = max(0.3, min(4.0, real_min / estimada_min))
    d["fator"] = round(0.7 * d.get("fator", 1.0) + 0.3 * razao, 3)
    d["amostras_fator"] = d.get("amostras_fator", 0) + 1


def _proximo_id(d: dict) -> str:
    return str(max([int(t["id"]) for t in d["tarefas"] if str(t["id"]).isdigit()] + [0]) + 1)


def _texto_escolha(podem, nao, d) -> str:
    if not podem:
        if nao:
            return "Nada dá para fazer agora: " + "; ".join(f"{t['titulo']} ({m[0]})" for _n, t, m in nao[:3]) + "."
        return "Sua lista está vazia. Diga 'adiciona tarefa' para começar."
    nota, t, motivos = podem[0]
    estimada = round((t.get("duracao_min") or 30) * d.get("fator", 1.0))
    txt = f"Faça agora: {t['titulo']}"
    if motivos:
        txt += f" — porque {', '.join(motivos[:3])}"
    txt += f". Estimo {estimada} min."
    if len(podem) > 1:
        txt += " Depois: " + "; ".join(x[1]["titulo"] for x in podem[1:3]) + "."
    return txt


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "agora").lower()
    d = carregar()
    agora = datetime.now()
    try:
        if acao == "adicionar":
            titulo = str(p.get("titulo") or "").strip()
            if not titulo:
                return "Qual é a tarefa?"
            deps = []
            for nome in re.split(r",| e ", str(p.get("depende_de") or "")):
                alvo = achar(d, nome)
                if alvo:
                    deps.append(alvo["id"])
            recurso = _dobrar(str(p.get("recurso") or ""))
            recurso = ("internet" if "internet" in recurso or "online" in recurso else
                       "pc_pesado" if "pesad" in recurso or "render" in recurso else
                       "leve" if "leve" in recurso else "")
            t = {"id": _proximo_id(d), "titulo": titulo,
                 "importancia": int(max(1, min(5, num(p.get("importancia"), 3)))),
                 "urgencia": int(max(1, min(5, num(p.get("urgencia"), 3)))),
                 "prazo": _prazo(str(p.get("prazo") or ""), agora), "duracao_min": int(num(p.get("duracao"), 30)) or 30,
                 "depende_de": deps, "recurso": recurso, "status": "pendente", "motivo_bloqueio": "",
                 "criada": agora.isoformat(timespec="minutes")}
            d["tarefas"].append(t)
            salvar(d)
            prazo = f", prazo {datetime.fromisoformat(t['prazo']):%d/%m %H:%M}" if t["prazo"] else ""
            podem, _nao = ranking(d, agora, contexto_atual())
            pos = next((i for i, x in enumerate(podem, 1) if x[1]["id"] == t["id"]), None)
            return (f"Anotei a tarefa {t['id']}: {titulo}{prazo}."
                    + (f" Ela entra em {pos}º lugar na fila." if pos else ""))
        if acao in ("agora", "proxima"):
            ctx = contexto_atual(p.get("minutos"))
            podem, nao = ranking(d, agora, ctx)
            mostrar(player, "PRIORIDADES — AGORA",
                    "\n".join(f"{i}. [{n:>5}] {t['titulo']}  ({', '.join(m) or '—'})" for i, (n, t, m) in enumerate(podem, 1))
                    + ("\n\nFORA DA FILA AGORA\n" + "\n".join(f"  · {t['titulo']}: {m[0]}" for _n, t, m in nao) if nao else "")
                    + f"\n\nFator de estimativa aprendido: {d.get('fator', 1.0):.2f}× ({d.get('amostras_fator', 0)} tarefas medidas)")
            return _texto_escolha(podem, nao, d)
        if acao == "listar":
            abertas = [t for t in d["tarefas"] if t["status"] != "feita"]
            if not abertas:
                return "Nenhuma tarefa aberta."
            return f"{len(abertas)} tarefa(s): " + "; ".join(f"{t['id']}. {t['titulo']} ({t['status']})" for t in abertas[:8]) + "."
        t = achar(d, str(p.get("titulo") or ""), incluir_feitas=(acao == "remover"))
        if not t:
            return "Não achei essa tarefa na lista."
        if acao == "bloquear":
            t["status"] = "bloqueada"
            t["motivo_bloqueio"] = str(p.get("motivo") or "").strip()
            salvar(d)
            podem, nao = ranking(d, agora, contexto_atual(p.get("minutos")))
            return (f"Marquei '{t['titulo']}' como bloqueada" + (f" ({t['motivo_bloqueio']})" if t["motivo_bloqueio"] else "")
                    + ". Enquanto isso: " + _texto_escolha(podem, nao, d))
        if acao == "desbloquear":
            t["status"], t["motivo_bloqueio"] = "pendente", ""
            salvar(d)
            return f"'{t['titulo']}' voltou para a fila."
        if acao == "comecar":
            t["status"] = "fazendo"
            t["iniciada"] = agora.isoformat(timespec="minutes")
            salvar(d)
            return f"Bom trabalho em '{t['titulo']}'. Estimo {round(t['duracao_min'] * d.get('fator', 1.0))} min."
        if acao == "concluir":
            t["status"] = "feita"
            t["concluida"] = agora.isoformat(timespec="minutes")
            extra = ""
            if t.get("iniciada"):
                real = (agora - datetime.fromisoformat(t["iniciada"])).total_seconds() / 60
                if 2 <= real <= 16 * 60:
                    t["real_min"] = round(real)
                    aprender_fator(d, t["duracao_min"], real)
                    extra = f" Levou {round(real)} min (estimativa {t['duracao_min']})."
            liberadas = [x["titulo"] for x in d["tarefas"] if t["id"] in x.get("depende_de", []) and x["status"] != "feita"]
            salvar(d)
            if liberadas:
                extra += f" Isso libera: {', '.join(liberadas)}."
            podem, nao = ranking(d, agora, contexto_atual())
            return f"Concluída: {t['titulo']}.{extra} " + (_texto_escolha(podem, nao, d) if podem else "A fila está vazia.")
        if acao == "remover":
            d["tarefas"] = [x for x in d["tarefas"] if x["id"] != t["id"]]
            salvar(d)
            return f"Removi '{t['titulo']}'."
        return "Ações: adicionar, agora, bloquear, desbloquear, comecar, concluir, listar, remover."
    except Exception as e:
        return f"As prioridades falharam: {e}"
