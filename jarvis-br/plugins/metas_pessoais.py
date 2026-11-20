"""Metas pessoais (2.19): metas do ano com resultados mensuráveis; você atualiza os números e vê o progresso de cada uma."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, dias_ate, norm, num1, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("metas_pessoais", "Personal goals with measurable key results (OKR style): create, add key results with targets, update progress, see % done and days left.",
           "criar | resultado | progresso | ver | listar | apagar",
           "criar: nome, prazo (dd/mm/aaaa). resultado: nome, texto (key result), alvo (number). progresso: nome, texto (which result), valor.",
           "nome prazo texto alvo valor")

M = Colecao("metas")


def percentual(m: dict) -> int:
    rs = m.get("resultados") or []
    return round(sum(min(1, r["atual"] / r["alvo"]) for r in rs if r["alvo"]) / len(rs) * 100) if rs else 0


def linha(m: dict) -> str:
    prazo = f", {dias_ate(m['prazo'])} dia(s) restantes" if m.get("prazo") else ""
    return f"{m['nome']}: {percentual(m)}%{prazo}"


def _go(p, pl):
    a, nome = p["action"], p.get("nome")
    if a == "criar":
        M.por(nome, {"prazo": ler_data(p.get("prazo")).isoformat() if p.get("prazo") else None, "resultados": []})
        return f"Meta '{nome}' criada. Agora diga os resultados que provam que ela foi cumprida."
    if a == "listar":
        return "\n".join(linha(m) for m in M.tudo().values()) or "Nenhuma meta criada."
    m = M.pegar(nome)
    if not m:
        return "Não achei essa meta."
    if a == "apagar":
        M.tirar(nome)
        return "Meta apagada."
    if a == "resultado":
        m["resultados"].append({"t": str(p.get("texto") or "resultado"), "alvo": num1(p, "alvo", 1), "atual": 0.0})
    elif a == "progresso":
        q = norm(p.get("texto"))
        r = next((x for x in m["resultados"] if q and q in norm(x["t"])), m["resultados"][0] if len(m["resultados"]) == 1 else None)
        if not r:
            return "Qual resultado? " + ", ".join(x["t"] for x in m["resultados"])
        r["atual"] = num1(p, "valor", r["atual"])
    M.por(m["nome"], m)
    return linha(m) + ".\n" + "\n".join(f"• {r['t']}: {r['atual']:g} de {r['alvo']:g}" for r in m["resultados"])


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("criar resultado progresso ver listar apagar".split(), _go), player, "Metas")
