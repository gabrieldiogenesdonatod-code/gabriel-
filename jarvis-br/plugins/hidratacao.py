"""Hidratação (2.18): anota copos de água, meta pelo peso, lembrete a cada X minutos enquanto o JARVIS está aberto."""
from __future__ import annotations

import threading

from plugins import _lote2
from plugins._lote2 import P, avisar, gravar_json, hoje, ler_json, numeros, rodar

PLUGIN = P("hidratacao", "Water tracker: log glasses/ml, daily goal (35 ml/kg), progress, reminder every N minutes.",
           "bebi | hoje | semana | meta | lembrete | parar_lembrete",
           "bebi: valor (ml, default 250 = one glass). meta: valor = weight kg or goal in ml. lembrete: valor minutes.",
           "valor")

_lemb: dict = {}


def _arq():
    return _lote2.PASTA / "agua.json"


def meta_ml(valor: float) -> int:
    return int(valor * 35) if valor < 300 else int(valor)     # < 300 = peso em kg


def _go(p, pl):
    a, d = str(p.get("action")).lower(), ler_json(_arq(), {}) or {}
    v = (numeros(p.get("valor")) or [0])[0]
    meta = d.get("meta", 2000)
    if a == "meta":
        d["meta"] = meta_ml(v or 2000)
        gravar_json(_arq(), d)
        return f"Meta: {d['meta']} ml por dia."
    if a == "bebi":
        d[hoje()] = d.get(hoje(), 0) + int(v or 250)
        gravar_json(_arq(), d)
    if a in ("bebi", "hoje"):
        x = d.get(hoje(), 0)
        return f"Hoje: {x} ml de {meta} ml ({min(100, x * 100 // meta)}%)."
    if a == "semana":
        import time
        dias = [time.strftime("%Y-%m-%d", time.localtime(time.time() - k * 86400)) for k in range(7)]
        vals = [d.get(x, 0) for x in dias]
        return f"Últimos 7 dias: média de {sum(vals) // 7} ml por dia; bateu a meta em {sum(v >= meta for v in vals)} dia(s)."
    if a == "parar_lembrete":
        _lemb["parar"] = True
        return "Lembrete desligado."
    mins = max(10, int(v or 60))
    _lemb["parar"] = False

    def laco():
        ev = threading.Event()
        while not ev.wait(mins * 60) and not _lemb.get("parar"):
            avisar(pl, "Hora de beber um copo de água.", "AGUA")
    threading.Thread(target=laco, daemon=True).start()
    return f"Vou lembrar de beber água a cada {mins} minutos."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("bebi hoje semana meta lembrete parar_lembrete".split(), _go), player)
