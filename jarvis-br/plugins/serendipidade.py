"""
Serendipidade (3.0): o JARVIS pega duas ideias ou anotações antigas suas que nunca se encontraram e
junta numa ideia NOVA.

    "Jarvis, mistura duas ideias minhas."
    → "E se o capacete com ESP32 (ideia de agosto) virasse vitrine da loja (anotação de outubro)?
       Um manequim infantil com LEDs que acendem quando alguém passa…"

Usa a caixa de ideias e o segundo cérebro. Não repete o mesmo par. Sem a chave do Gemini, ele só
propõe o par e a pergunta "e se?".
"""

from __future__ import annotations

import random
import time

from plugins._lote2 import P, carregar, guardar, rodar

PLUGIN = P("serendipidade", "Serendipity: picks two old ideas/notes of yours that never met (idea box + second brain) and combines them into a "
           "new concrete idea; never repeats a pair; can save the result as a new idea.",
           "misturar | salvar | historico", "misturar: new combination. salvar: keep the last one in the idea box.", "")


def fontes() -> list[dict]:
    """[{'texto', 'origem', 'quando'}] das ideias e anotações (as mais antigas valem mais)."""
    itens = []
    try:
        from plugins import ideias
        for i in ideias.dados().get("ideias", []):
            itens.append({"texto": str(i.get("texto", ""))[:300], "origem": "ideia", "quando": float(i.get("criada") or 0)})
    except Exception:
        pass
    try:
        from plugins import segundo_cerebro
        for n in segundo_cerebro.dados().get("notas", []):
            itens.append({"texto": f"{n.get('titulo', '')}: {n.get('texto', '')}"[:300], "origem": "anotação",
                          "quando": float(n.get("criada") or 0)})
    except Exception:
        pass
    return [i for i in itens if len(i["texto"]) > 8]


def escolher_par(itens: list[dict], usados: set[str], rng=random) -> tuple[dict, dict] | None:
    """Dois itens diferentes, de preferência de origens ou épocas distantes, num par inédito. Pura (com rng)."""
    if len(itens) < 2:
        return None
    candidatos = []
    for _ in range(60):
        a, b = rng.sample(itens, 2)
        chave = "|".join(sorted([a["texto"][:60], b["texto"][:60]]))
        if chave in usados:
            continue
        dist = (a["origem"] != b["origem"]) * 2 + min(2.0, abs(a["quando"] - b["quando"]) / (30 * 86400))
        candidatos.append((dist + rng.random(), a, b))
    if not candidatos:
        return None
    _, a, b = max(candidatos, key=lambda x: x[0])
    return a, b


def _go(p, pl):
    a, est = p["action"], carregar("serendipidade", {"usados": [], "historico": []})
    if a == "historico":
        return "\n".join(f"{h['quando']}: {h['ideia'][:120]}" for h in est["historico"][-8:]) or "Ainda não misturei nada."
    if a == "salvar":
        if not est["historico"]:
            return "Ainda não tenho mistura para salvar."
        from core import registro_ferramentas
        return registro_ferramentas.executar("ideias", {"action": "anotar", "texto": est["historico"][-1]["ideia"]}, pl)
    par = escolher_par(fontes(), set(est["usados"]))
    if not par:
        return "Preciso de pelo menos duas ideias ou anotações guardadas (caixa de ideias ou segundo cérebro) que eu ainda não tenha juntado."
    x, y = par
    from core import gemini
    pedido = ("Junte as duas ideias do usuário abaixo numa ideia NOVA, concreta e possível para ele (programador em Goiânia, "
              "tem uma loja de roupa infantil, gosta de rap geek, constrói um J.A.R.V.I.S e uma IA do zero). Em português, até 4 "
              f"frases, terminando com o primeiro passo.\nIdeia A ({x['origem']}): {x['texto']}\nIdeia B ({y['origem']}): {y['texto']}")
    nova = gemini.text(pedido, tier=gemini.SMART, default="") or f"E se você juntasse \"{x['texto'][:80]}\" com \"{y['texto'][:80]}\"?"
    est["usados"].append("|".join(sorted([x["texto"][:60], y["texto"][:60]])))
    est["historico"].append({"quando": time.strftime("%Y-%m-%d"), "a": x["texto"], "b": y["texto"], "ideia": nova})
    guardar("serendipidade", {"usados": est["usados"][-500:], "historico": est["historico"][-100:]})
    return f"Juntei \"{x['texto'][:70]}\" com \"{y['texto'][:70]}\".\n{nova}\n(Diga 'salvar' para guardar na caixa de ideias.)"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("misturar salvar historico".split(), _go), player, "Serendipidade")
