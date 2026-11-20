"""Revisão espaçada (2.19): você diz o que estudou e o JARVIS marca as revisões em 1, 3, 7, 15, 30 e 60 dias para não esquecer."""
from __future__ import annotations

from datetime import date, timedelta

from plugins._lote2 import Colecao, P, norm, rodar

PLUGIN = P("revisao_espacada", "Spaced repetition scheduler: log a studied topic, reviews due today (1-3-7-15-30-60 days), mark reviewed (easy/hard), list.",
           "estudei | hoje | feito | listar | apagar",
           "estudei: tema, materia. feito: tema, como (facil|dificil; 'dificil' restarts the intervals).",
           "tema materia como")

INTERVALOS = [1, 3, 7, 15, 30, 60]
R = Colecao("revisoes")


def proxima(etapa: int, ref: date) -> str | None:
    return (ref + timedelta(INTERVALOS[etapa])).isoformat() if etapa < len(INTERVALOS) else None


def _go(p, pl):
    a, tema, hoje_ = p["action"], p.get("tema"), date.today()
    tudo = list(R.tudo().values())
    if a == "estudei":
        R.por(tema, {"materia": str(p.get("materia") or ""), "etapa": 0, "proxima": proxima(0, hoje_)})
        return f"Anotado. Primeira revisão de '{tema}' amanhã."
    if a == "hoje":
        dev = [r["nome"] for r in tudo if r["proxima"] and r["proxima"] <= hoje_.isoformat()]
        return f"Revisar hoje ({len(dev)}): " + ", ".join(dev) + "." if dev else "Nada para revisar hoje."
    if a == "listar":
        return "\n".join(f"{r['nome']}: " + (f"próxima em {r['proxima'][8:]}/{r['proxima'][5:7]}" if r["proxima"] else "dominado")
                         for r in sorted(tudo, key=lambda r: r["proxima"] or "9")) or "Nenhum tema anotado."
    r = R.pegar(tema)
    if not r:
        return "Não achei esse tema."
    if a == "apagar":
        R.tirar(tema)
        return "Tema apagado."
    r["etapa"] = 0 if norm(p.get("como")).startswith(("dif", "esq", "err")) else r["etapa"] + 1
    r["proxima"] = proxima(r["etapa"], hoje_)
    R.por(r["nome"], r)
    return f"'{r['nome']}': próxima revisão em {INTERVALOS[r['etapa']]} dia(s)." if r["proxima"] else f"'{r['nome']}' dominado! 🎓"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("estudei hoje feito listar apagar".split(), _go), player, "Revisões")
