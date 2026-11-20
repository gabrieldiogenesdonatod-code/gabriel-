"""
Meta de vendas do mês (fork PT-BR 2.17).

    "Jarvis, minha meta de vendas é 6 mil por mês"
    "Jarvis, como está a meta?"   → vendido, % da meta, quanto falta por dia que resta, projeção

Lê as vendas da Cristal Malhas (memory/cristal_vendas.csv).
"""

from __future__ import annotations

import calendar
from datetime import date

from plugins._comum import cfg, salvar_cfg
from plugins._dados_br import ler, numero, reais

PLUGIN = {
    "name": "meta_vendas",
    "brief": "Monthly sales goal for the store: progress, needed per day, projection.",
    "description": "Sales goal. action='definir' with valor (monthly goal in reais). action='status' shows progress.",
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "valor": {"type": "NUMBER"}},
                   "required": []},
}

PLUGIN_SETTINGS = {"namespace": "meta_vendas", "title": "Meta de vendas",
                   "fields": [{"key": "meta", "label": "Meta mensal (R$)", "type": "number", "default": 0}]}


def progresso(vendido: float, meta: float, hoje: date) -> dict:
    dias_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    restam = dias_mes - hoje.day + 1
    projecao = vendido / hoje.day * dias_mes
    return {"pct": vendido / meta if meta else 0, "falta": max(0.0, meta - vendido),
            "por_dia": max(0.0, meta - vendido) / restam, "projecao": projecao, "restam": restam}


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    if str(p.get("action") or "status").lower() == "definir":
        salvar_cfg("meta_vendas", {"meta": float(p.get("valor") or 0)})
        return f"Meta mensal: {reais(float(p.get('valor') or 0))}."
    meta = float(cfg("meta_vendas", PLUGIN_SETTINGS).get("meta") or 0)
    if meta <= 0:
        return "Você ainda não definiu a meta. Diga 'minha meta é X reais por mês'."
    hoje = date.today()
    vendido = sum(numero(v.get("total")) for v in ler("cristal_vendas.csv")
                  if str(v.get("data", "")).startswith(hoje.strftime("%Y-%m")))
    r = progresso(vendido, meta, hoje)
    txt = f"Vendido no mês: {reais(vendido)}, {r['pct'] * 100:.0f}% da meta de {reais(meta)}. "
    if r["falta"] <= 0:
        return txt + "Meta batida! 🎉"
    return txt + (f"Faltam {reais(r['falta'])}: uns {reais(r['por_dia'])} por dia nos {r['restam']} dias que restam. "
                  f"No ritmo atual, o mês fecha em {reais(r['projecao'])}.")
