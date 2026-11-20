"""
Duelo JARVIS × FRIDAY (3.0): as duas IAs respondem à MESMA pergunta, cada uma do seu jeito. Você
vê as duas respostas às cegas (A e B, em ordem sorteada), escolhe a melhor e o placar evolui. Com
o tempo o JARVIS descobre quem manda melhor em cada assunto (programação, loja, vida…).

    "Jarvis, duelo: como eu aumento as vendas no fim do mês?"     "Voto na B."     "Placar do duelo."
"""

from __future__ import annotations

import random
import time

from plugins._lote2 import P, carregar, guardar, norm, rodar

PLUGIN = P("duelo_ia", "JARVIS vs FRIDAY: both answer the same question blind (A/B); you vote; scoreboard per topic shows who is better at what.",
           "duelar | votar | placar",
           "duelar: pergunta, categoria (optional: programacao|loja|vida|outro). votar: voto (a|b|empate).", "pergunta categoria voto")

ESTILOS = {"JARVIS": "Você é o J.A.R.V.I.S: mordomo britânico, preciso, formal, com ironia sutil; vai ao ponto com cuidado técnico.",
           "FRIDAY": "Você é a F.R.I.D.A.Y: jovem, direta, animada e prática, fala como uma amiga que resolve; frases curtas."}
TEMAS = {"programacao": "codigo programa python bug erro api banco site app ia modelo git deploy servidor",
         "loja": "loja venda vender cliente estoque preco promocao post instagram roupa malha cristal fornecedor caixa",
         "vida": "vida familia saude dinheiro casa tempo estudar habito treino sono vo"}


def categoria(pergunta: str) -> str:
    ws = set(norm(pergunta).split())
    notas = {c: len(ws & set(p.split())) for c, p in TEMAS.items()}
    melhor = max(notas, key=notas.get)
    return melhor if notas[melhor] else "outro"


def elo(ra: float, rb: float, resultado: float, k: float = 24) -> tuple[float, float]:
    """resultado = 1 (A ganhou), 0 (B ganhou), 0.5 (empate). Pura."""
    esperado = 1 / (1 + 10 ** ((rb - ra) / 400))
    return ra + k * (resultado - esperado), rb - k * (resultado - esperado)


def _go(p, pl):
    a, est = p["action"], carregar("duelo", {"placar": {}, "atual": None, "historico": []})
    if a == "placar":
        if not est["placar"]:
            return "Nenhum duelo votado ainda."
        linhas = []
        for cat, r in est["placar"].items():
            lider = max(r, key=lambda k: r[k])
            linhas.append(f"{cat}: JARVIS {r['JARVIS']:.0f} × FRIDAY {r['FRIDAY']:.0f} — melhor em {cat}: {lider}")
        return "\n".join(linhas)
    if a == "votar":
        at = est.get("atual")
        if not at:
            return "Não há duelo esperando voto."
        v = norm(p.get("voto"))
        if v not in ("a", "b") and not v.startswith("emp"):
            return "Vote 'A', 'B' ou 'empate'."
        r = est["placar"].setdefault(at["categoria"], {"JARVIS": 1000.0, "FRIDAY": 1000.0})
        ganhador = at["ordem"][0] if v == "a" else at["ordem"][1] if v == "b" else None
        res_j = 0.5 if ganhador is None else 1.0 if ganhador == "JARVIS" else 0.0
        r["JARVIS"], r["FRIDAY"] = elo(r["JARVIS"], r["FRIDAY"], res_j)
        est["historico"].append({"quando": time.strftime("%Y-%m-%d"), "categoria": at["categoria"], "venceu": ganhador or "empate"})
        est["atual"] = None
        guardar("duelo", est)
        return (f"A era {at['ordem'][0]}, B era {at['ordem'][1]}. " + (f"Ponto para {ganhador}!" if ganhador else "Empate.") +
                f" Placar em {at['categoria']}: JARVIS {r['JARVIS']:.0f} × FRIDAY {r['FRIDAY']:.0f}.")
    perg = str(p.get("pergunta") or "").strip()
    if len(perg) < 5:
        return "Qual a pergunta do duelo?"
    from core import gemini
    respostas = {}
    for nome, estilo in ESTILOS.items():
        r = gemini.text(f"{estilo}\nResponda em português do Brasil, em até 5 frases, à pergunta: {perg}", tier=gemini.FAST, default="")
        if not r:
            return "As IAs não responderam agora (preciso da chave do Gemini e de internet)."
        respostas[nome] = r.strip()
    ordem = random.sample(list(ESTILOS), 2)
    cat = norm(p.get("categoria")) or categoria(perg)
    est["atual"] = {"pergunta": perg, "ordem": ordem, "categoria": cat if cat in TEMAS or cat == "outro" else "outro"}
    guardar("duelo", est)
    from plugins._comum import mostrar
    mostrar(pl, "DUELO — VOTE NA MELHOR", f"Pergunta: {perg}\n\nA)\n{respostas[ordem[0]]}\n\nB)\n{respostas[ordem[1]]}")
    return "As duas responderam. As respostas A e B estão no painel, às cegas. Qual foi melhor: A, B ou empate?"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("duelar votar placar".split(), _go), player, "Duelo")
