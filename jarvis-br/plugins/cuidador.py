"""
Modo cuidador (fork PT-BR 1.6).

Rotina de cuidados com alguém da família: horários (remédios, refeições,
água, curativo, exercício), consultas marcadas e o checklist do dia. Na hora,
o JARVIS avisa por voz e no celular; se ninguém marcar como feito em 30 min,
ele avisa de novo. De noite, dá o resumo do dia.

    "Jarvis, cuidados da vó: remédio da pressão às 8h e às 20h"
    "Jarvis, consulta da vó com o cardiologista dia 15/11 às 14h no Hospital X"
    "Jarvis, já dei o remédio da vó"          "Jarvis, o que falta hoje para a vó?"
    "Jarvis, checklist da vó: banho, caminhada de 10 minutos"

Os dados ficam só neste PC (memory/cuidador.json).
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
import uuid
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, falar, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "cuidador",
    "brief": "Caregiver mode: family member's daily care schedule, appointments, checklist; reminders and daily report.",
    "description": (
        "Caregiver routine for a family member: action='adicionar' with pessoa + item (e.g. 'remédio da pressão') + "
        "horarios ('8h e 20h', '08:00, 14:00') + optional dias ('seg a sex'); 'consulta' with pessoa + item + data "
        "(dd/mm) + hora + local; 'checklist' with pessoa + itens (comma separated, once a day); 'feito' with pessoa + "
        "item (marks done now); 'hoje' with pessoa (what is pending today); 'remover' with pessoa + item; 'listar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}, "pessoa": {"type": "STRING"}, "item": {"type": "STRING"},
                       "horarios": {"type": "STRING"}, "dias": {"type": "STRING"}, "data": {"type": "STRING"},
                       "hora": {"type": "STRING"}, "local": {"type": "STRING"}, "itens": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "cuidador.json"
DIAS = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6}
_iniciado = threading.Event()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode().strip()


def ler_horarios(texto: str) -> list[str]:
    """'8h e 20h', '08:00, 14:30', '7h30' → ['08:00', '20:00'] (pura)."""
    saida = []
    for h, m in re.findall(r"\b(\d{1,2})\s*(?:h|:|horas?)\s*(\d{2})?", texto or ""):
        if int(h) < 24 and int(m or 0) < 60:
            saida.append(f"{int(h):02d}:{int(m or 0):02d}")
    return sorted(set(saida))


def ler_dias(texto: str) -> list[int]:
    """'seg a sex' → [0..4]; 'ter, qui' → [1, 3]; vazio → todos (pura)."""
    t = _dobrar(texto)
    if not t or "todo" in t:
        return list(range(7))
    m = re.search(r"(seg|ter|qua|qui|sex|sab|dom)\w*\s*a\s*(seg|ter|qua|qui|sex|sab|dom)", t)
    if m:
        a, b = DIAS[m.group(1)], DIAS[m.group(2)]
        return list(range(a, b + 1)) if a <= b else list(range(a, 7)) + list(range(0, b + 1))
    return sorted({DIAS[x] for x in re.findall(r"(seg|ter|qua|qui|sex|sab|dom)", t)}) or list(range(7))


def pendentes(d: dict, agora: datetime, pessoa: str = "") -> list[dict]:
    """Horários de hoje que já passaram e não foram marcados (pura)."""
    hoje = agora.date().isoformat()
    saida = []
    for it in d.get("itens", []):
        if pessoa and _dobrar(pessoa) not in _dobrar(it["pessoa"]):
            continue
        if agora.weekday() not in it.get("dias", list(range(7))):
            continue
        for h in it.get("horarios", []):
            if f"{hoje} {h}" in it.get("feitos", []):
                continue
            hh, mm = map(int, h.split(":"))
            if agora >= agora.replace(hour=hh, minute=mm, second=0, microsecond=0):
                saida.append({"id": it["id"], "pessoa": it["pessoa"], "item": it["item"], "hora": h})
    for c in d.get("checklist", []):
        if (not pessoa or _dobrar(pessoa) in _dobrar(c["pessoa"])) and c.get("feito") != hoje:
            saida.append({"id": c["id"], "pessoa": c["pessoa"], "item": c["item"], "hora": "hoje"})
    return saida


def pendentes_hoje() -> list[dict]:
    """Usado pelo boot: o que já devia ter sido feito hoje e não foi."""
    return pendentes(ler_json(_ARQ, {}) or {}, datetime.now())


def _achar_item(d: dict, pessoa: str, item: str) -> list[dict]:
    p, i = _dobrar(pessoa), _dobrar(item)
    cands = [x for x in d.get("itens", []) + d.get("checklist", [])
             if (not p or p in _dobrar(x["pessoa"])) and (not i or i in _dobrar(x["item"]) or _dobrar(x["item"]) in i)]
    return cands


def _laco(player) -> None:
    time.sleep(45)
    while True:
        try:
            d = ler_json(_ARQ, {}) or {}
            agora = datetime.now()
            avisos = d.setdefault("avisos", {})
            mudou = False
            for pnd in pendentes(d, agora):
                if pnd["hora"] == "hoje":
                    continue
                chave = f"{agora.date().isoformat()} {pnd['hora']} {pnd['id']}"
                n, ultimo = avisos.get(chave, [0, 0])
                hh, mm = map(int, pnd["hora"].split(":"))
                atraso = (agora - agora.replace(hour=hh, minute=mm, second=0, microsecond=0)).total_seconds() / 60
                if atraso > 180 or n >= 3 or time.time() - ultimo < 30 * 60:
                    continue
                avisos[chave] = [n + 1, time.time()]
                mudou = True
                from plugins._notificar import notificar
                texto = f"{pnd['item']} de {pnd['pessoa']} ({pnd['hora']})" + (" — ainda não marcado" if n else "")
                notificar(player, f"Hora do cuidado: {texto}.", titulo="CUIDADOR", etiqueta="CUIDADO", falar_agora=False,
                          prioridade="high")
                falar(player, f"[CUIDADOR] Lembre com carinho, em UMA frase: {texto}. Peça para avisar quando estiver "
                              "feito. Não chame nenhuma ferramenta.")
            for c in d.get("consultas", []):
                quando = datetime.fromisoformat(c["quando"])
                for antes, rotulo in ((timedelta(days=1), "amanhã"), (timedelta(hours=2), "daqui a 2 horas")):
                    chave = f"consulta {c['id']} {rotulo}"
                    if quando - antes <= agora < quando and chave not in avisos:
                        avisos[chave] = [1, time.time()]
                        mudou = True
                        falar(player, f"[CUIDADOR] Lembre: consulta de {c['pessoa']} — {c['item']} {rotulo}, às "
                                      f"{quando:%H:%M}" + (f", em {c['local']}" if c.get("local") else "") + ". UMA frase.")
            if mudou:
                d["avisos"] = {k: v for k, v in avisos.items() if k[:10] >= (agora.date() - timedelta(days=3)).isoformat()
                               or k.startswith("consulta")}
                gravar_json(_ARQ, d)
        except Exception as e:
            print(f"[Cuidador] {e}")
        time.sleep(60)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="cuidador").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = _dobrar(str(p.get("action") or "hoje"))
    pessoa = str(p.get("pessoa") or "").strip()
    try:
        d = ler_json(_ARQ, {}) or {}
        for k in ("itens", "consultas", "checklist"):
            d.setdefault(k, [])
        if acao == "adicionar":
            horarios = ler_horarios(str(p.get("horarios") or ""))
            item = str(p.get("item") or "").strip()
            if not pessoa or not item or not horarios:
                return "Diga para quem, o quê e os horários (ex.: vó, remédio da pressão, 8h e 20h)."
            d["itens"].append({"id": uuid.uuid4().hex[:6], "pessoa": pessoa, "item": item, "horarios": horarios,
                               "dias": ler_dias(str(p.get("dias") or "")), "feitos": []})
            gravar_json(_ARQ, d)
            return f"Anotado: {item} de {pessoa} às {', '.join(horarios)}. Eu aviso na hora (e de novo se ninguém marcar)."
        if acao == "consulta":
            from plugins.aniversarios import ler_data
            data, horas = ler_data(str(p.get("data") or "")), ler_horarios(str(p.get("hora") or ""))
            if not pessoa or not data or not horas:
                return "Diga para quem, a data (dd/mm) e a hora da consulta."
            dia, mes, ano = data
            quando = datetime(ano or date.today().year, mes, dia, *map(int, horas[0].split(":")))
            if quando < datetime.now() and not ano:
                quando = quando.replace(year=quando.year + 1)
            d["consultas"].append({"id": uuid.uuid4().hex[:6], "pessoa": pessoa, "item": str(p.get("item") or "consulta"),
                                   "quando": quando.isoformat(), "local": str(p.get("local") or "")})
            gravar_json(_ARQ, d)
            return f"Consulta de {pessoa} em {quando:%d/%m às %H:%M}. Aviso na véspera e 2 horas antes."
        if acao == "checklist":
            itens = [x.strip() for x in re.split(r"[,;]| e ", str(p.get("itens") or "")) if x.strip()]
            for it in itens:
                d["checklist"].append({"id": uuid.uuid4().hex[:6], "pessoa": pessoa or "família", "item": it, "feito": ""})
            gravar_json(_ARQ, d)
            return f"Checklist diário de {pessoa or 'família'}: {', '.join(itens)}."
        if acao == "feito":
            alvos = _achar_item(d, pessoa, str(p.get("item") or ""))
            if not alvos:
                return "Não achei esse cuidado. Diga 'o que falta hoje' para ver a lista."
            agora = datetime.now()
            hoje = agora.date().isoformat()
            marcados = []
            for it in alvos:
                if "horarios" in it:
                    passou = [h for h in it["horarios"] if f"{hoje} {h}" not in it["feitos"]
                              and agora >= agora.replace(hour=int(h[:2]), minute=int(h[3:]), second=0) - timedelta(hours=1)]
                    if passou:
                        it["feitos"] = (it["feitos"] + [f"{hoje} {passou[0]}"])[-200:]
                        marcados.append(f"{it['item']} das {passou[0]}")
                elif it.get("feito") != hoje:
                    it["feito"] = hoje
                    marcados.append(it["item"])
            gravar_json(_ARQ, d)
            return ("Marquei: " + ", ".join(marcados) + ".") if marcados else "Isso já estava marcado como feito hoje."
        if acao == "remover":
            alvos = _achar_item(d, pessoa, str(p.get("item") or ""))
            d["itens"] = [x for x in d["itens"] if x not in alvos]
            d["checklist"] = [x for x in d["checklist"] if x not in alvos]
            gravar_json(_ARQ, d)
            return f"Removi {len(alvos)} item(ns)."
        agora = datetime.now()
        if acao == "listar":
            linhas = [f"{it['pessoa']}: {it['item']} às {', '.join(it['horarios'])}" for it in d["itens"]] + \
                [f"{c['pessoa']}: {c['item']} (diário)" for c in d["checklist"]] + \
                [f"{c['pessoa']}: {c['item']} em {datetime.fromisoformat(c['quando']):%d/%m %H:%M}" for c in d["consultas"]
                 if datetime.fromisoformat(c["quando"]) >= agora]
            mostrar(player, "CUIDADOS", "\n".join(linhas) or "Nada cadastrado.")
            return f"{len(linhas)} cuidado(s) cadastrados; a lista está no painel." if linhas else \
                "Nada cadastrado. Ex.: cuidados da vó: remédio da pressão às 8h e às 20h."
        falta = pendentes(d, agora, pessoa)
        proximos = sorted({(h, it["item"]) for it in d["itens"] if (not pessoa or _dobrar(pessoa) in _dobrar(it["pessoa"]))
                           and agora.weekday() in it.get("dias", list(range(7))) for h in it["horarios"]
                           if h > agora.strftime("%H:%M")})
        return (("Falta: " + ", ".join(f"{x['item']} ({x['hora']})" for x in falta) + ". ") if falta else "Tudo em dia até agora. ") + \
            (("Próximos: " + ", ".join(f"{i} às {h}" for h, i in proximos[:4]) + ".") if proximos else "")
    except Exception as e:
        return f"O cuidador falhou: {e}"
