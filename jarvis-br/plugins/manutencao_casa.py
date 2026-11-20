"""
Manutenção da casa (fork PT-BR 2.17).

    "Jarvis, me lembra de trocar o filtro de água a cada 6 meses"
    "Jarvis, troquei o filtro hoje"                 → recomeça a contagem
    "Jarvis, o que está vencendo na casa?"
    "Jarvis, o gás dura uns 45 dias"                (botijão, óleo do carro, limpar o PC, ar-condicionado…)

Avisa uma vez por dia quando algo vence (voz + celular). Fica em memory/manutencao.json.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import date, timedelta

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "manutencao_casa",
    "brief": "Recurring home/car/PC maintenance reminders (filter, gas, oil, AC cleaning…): log done, what's due.",
    "description": (
        "Home maintenance. action='criar' with item and intervalo ('6 meses', '45 dias', '1 ano'). action='feito' with "
        "item resets the count. action='vencendo' lists due/soon. action='listar'. action='apagar' with item."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "item": {"type": "STRING"},
                                                    "intervalo": {"type": "STRING"}}, "required": ["action"]},
}

ARQ = MEMORIA / "manutencao.json"
_avisado = {"dia": ""}


def dias_de(texto: str) -> int:
    """'6 meses' → 182; '45 dias' → 45; '1 ano' → 365; '2 semanas' → 14 (pura)."""
    m = re.search(r"(\d+)\s*(dia|semana|mes|mês|ano)", str(texto or "").lower())
    if not m:
        return 0
    n = int(m.group(1))
    return n * {"dia": 1, "semana": 7, "mes": 30, "mês": 30, "ano": 365}[m.group(2)] + (n // 2 if m.group(2) in ("mes", "mês") else 0)


def proximo(item: dict) -> date:
    return date.fromisoformat(item["ultimo"]) + timedelta(days=item["dias"])


def _laco(player) -> None:
    while True:
        time.sleep(3600)
        hoje = date.today()
        if _avisado["dia"] == hoje.isoformat() or time.localtime().tm_hour < 9:
            continue
        vencidos = [i["item"] for i in (ler_json(ARQ, {}) or {}).values() if proximo(i) <= hoje]
        if vencidos:
            _avisado["dia"] = hoje.isoformat()
            from plugins._notificar import notificar
            notificar(player, "Manutenção vencida: " + ", ".join(vencidos) + ".", "Casa")


def on_session_start(player) -> None:
    threading.Thread(target=_laco, args=(player,), daemon=True, name="manutencao_casa").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "vencendo").lower()
    d = ler_json(ARQ, {}) or {}
    item = str(p.get("item") or "").strip()
    k = item.lower()
    hoje = date.today()
    try:
        if a == "criar":
            dias = dias_de(p.get("intervalo"))
            if not item or not dias:
                return "Diga o item e de quanto em quanto tempo (ex.: 6 meses)."
            d[k] = {"item": item, "dias": dias, "ultimo": d.get(k, {}).get("ultimo", hoje.isoformat())}
            gravar_json(ARQ, d)
            return f"Combinado: {item} a cada {dias} dias. Próxima: {proximo(d[k]):%d/%m/%Y}."
        if a == "feito":
            alvo = next((kk for kk in d if k in kk or kk in k), None)
            if not alvo:
                return f"Não tenho '{item}' na lista. Diga 'me lembra de {item} a cada…'."
            d[alvo]["ultimo"] = hoje.isoformat()
            gravar_json(ARQ, d)
            return f"Anotado. Próxima vez: {proximo(d[alvo]):%d/%m/%Y}."
        if a == "apagar":
            alvo = next((kk for kk in d if k in kk), None)
            if alvo:
                d.pop(alvo)
                gravar_json(ARQ, d)
                return "Apagado."
            return "Não achei."
        if not d:
            return "Nenhuma manutenção cadastrada."
        itens = sorted(d.values(), key=proximo)
        mostrar(player, "MANUTENÇÃO", "\n".join(f"{i['item']:<28} próxima {proximo(i):%d/%m/%Y}  (a cada {i['dias']} dias)"
                                                for i in itens))
        if a == "listar":
            return f"{len(itens)} itens; o próximo é {itens[0]['item']} em {proximo(itens[0]):%d/%m}."
        perto = [i for i in itens if (proximo(i) - hoje).days <= 7]
        if not perto:
            return f"Nada vencendo esta semana. O próximo é {itens[0]['item']} em {proximo(itens[0]):%d/%m}."
        return "Vencendo: " + "; ".join(f"{i['item']} ({'venceu' if proximo(i) <= hoje else f'em {(proximo(i) - hoje).days} dias'})"
                                         for i in perto) + "."
    except Exception as e:
        return f"A manutenção falhou: {e}"
