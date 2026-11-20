"""Telefones úteis (2.19): números de emergência do Brasil e os seus contatos importantes (encanador, médico, síndico)."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, norm, rodar

PLUGIN = P("telefones_uteis", "Brazilian emergency/useful numbers (police, ambulance, firefighters, CVV…) and the user's own important contacts.",
           "emergencia | buscar | salvar | meus | apagar",
           "buscar: texto (e.g. 'bombeiros', 'encanador'). salvar: nome, numero.", "texto nome numero")

BR = {"polícia militar": "190", "samu ambulância": "192", "bombeiros": "193", "polícia rodoviária federal": "191",
      "polícia civil": "197", "defesa civil": "199", "central de atendimento à mulher": "180", "disque denúncia": "181",
      "cvv apoio emocional": "188", "direitos humanos": "100", "inss previdência": "135", "disque saúde sus": "136",
      "guarda municipal": "153", "polícia federal": "194", "procon": "151"}
T = Colecao("telefones")


def procurar(q: str) -> list[str]:
    q = norm(q)
    todos = {**{k: v for k, v in BR.items()}, **{x["nome"]: x["numero"] for x in T.tudo().values()}}
    return [f"{k}: {v}" for k, v in todos.items() if any(w in norm(k) for w in q.split() if len(w) > 2)]


def _go(p, pl):
    a = p["action"]
    if a == "emergencia":
        return "Polícia 190, SAMU 192, Bombeiros 193, Defesa Civil 199, CVV 188, Central da Mulher 180."
    if a == "salvar":
        T.por(p.get("nome"), {"numero": str(p.get("numero") or "").strip()})
        return f"Salvei {p.get('nome')}: {p.get('numero')}."
    if a == "meus":
        return "\n".join(f"{x['nome']}: {x['numero']}" for x in T.tudo().values()) or "Nenhum contato salvo."
    if a == "apagar":
        return "Apagado." if T.tirar(p.get("nome")) else "Não achei esse contato."
    r = procurar(p.get("texto") or p.get("nome") or "")
    return "; ".join(r) or "Não achei. Diga 'emergência' para os principais."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("emergencia buscar salvar meus apagar".split(), _go), player, "Telefones")
