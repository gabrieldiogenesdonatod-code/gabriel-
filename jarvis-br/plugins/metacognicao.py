"""
Metacognição (3.6): o JARVIS mede o quanto pode confiar em si mesmo — e só evolui com prova e com o seu sim.

    "Jarvis, o quanto eu posso confiar em você?"         → o placar medido de cada sistema que faz previsão
    "Jarvis, como está o placar do seu cérebro?"         → quanto o cérebro local acertaria sozinho
    "Jarvis, tem alguma evolução esperando?"             "Jarvis, aprova a evolução do cérebro"
    "Jarvis, recusa a evolução"                          "Jarvis, desliga a evolução do cérebro"

O cérebro local é medido em sombra: a cada pedido que o Gemini resolveu, ele responde por dentro o que
teria feito, e a comparação vira placar. Quando a prova é forte, ele PROPÕE fazer sozinho frases parecidas
com as suas; só você aprova; se depois errar 3 das últimas 12, ele mesmo volta atrás. O placar junta também
o erro medido do oráculo, do eu do futuro, do gêmeo da loja e do motor de probabilidades.
Como funciona: core/metacognicao.py.
"""

from __future__ import annotations

from core import metacognicao as M
from plugins._lote2 import P, rodar

PLUGIN = P("metacognicao", "JARVIS measures how much it can trust itself: accuracy of its own predictions and local brain; "
                           "evidence-gated evolution you approve.",
           "placar | cerebro | evolucao | aprovar | recusar | rebaixar",
           "placar: measured accuracy/error per predicting system. cerebro: shadow-evaluation of the local brain (what it would "
           "have done vs what was done) and calibration. evolucao: pending proposal and history. aprovar / recusar: answer the "
           "pending evolution proposal. rebaixar: turn the approved similarity reflex off.", "")


def _placar(p, pl):
    linhas = M.placar()
    if not linhas:
        return ("Ainda não tenho nada medido. O placar aparece quando houver previsões conferidas (oráculo, eu do futuro, "
                "promoções) e alguns pedidos para comparar com o cérebro local.")
    fracos = [x["sistema"] for x in linhas if x["confianca"] == "baixa"]
    return ("O quanto você pode confiar em mim, pelo que foi medido:\n" + "\n".join("- " + M.frase_de(x) for x in linhas)
            + (f"\nOnde eu erro mais: {', '.join(fracos)}. Aí, confira antes de decidir." if fracos else ""))


def _cerebro(p, pl):
    pc = M.placar_cerebro()
    if not pc["n"] and not pc["sozinho"]["n"]:
        return "Ainda não medi o cérebro local: preciso de pedidos resolvidos pelo Gemini para comparar."
    partes = [f"Cérebro local, medido em {pc['n']} pedido(s): em {pc['sabia']} ele tinha um palpite"
              + (f" e acertou a ferramenta em {pc['top1']:.0%}." if pc["top1"] is not None else ".")]
    for nome, chave in (("Os reflexos de hoje", "reflexo"), ("Frases parecidas (evolução)", "parecida")):
        b = pc[chave]
        if b["n"]:
            partes.append(f"{nome}: acertaria {b['acertos']} de {b['n']} (piso de confiança {b['piso']:.0%}).")
    if pc["sozinho"]["n"]:
        partes.append(f"Depois da evolução aprovada, fiz {pc['sozinho']['n']} frase(s) parecida(s) sozinho e você corrigiu "
                      f"{pc['sozinho']['corrigidos']}.")
    for c in pc["calibracao"]:
        dif = c["certeza"] - c["acerto"]
        nota = "confiante demais" if dif > 0.15 else "modesto demais" if dif < -0.15 else "bem calibrado"
        partes.append(f"Quando ele diz {c['faixa'][0]:.0%} a {c['faixa'][1]:.0%} de certeza, acerta {c['acerto']:.0%} "
                      f"({c['n']} caso(s)): {nota}.")
    return " ".join(partes)


def _evolucao(p, pl):
    from core import cerebro
    d, prop = M._ler(), M.proposta()
    partes = ["Reflexo por semelhança: " + ("LIGADO (você aprovou)." if cerebro.semelhanca_ligada() else "desligado.")]
    if prop:
        partes.append(f"Proposta esperando o seu sim: em {prop['n']} casos parecidos eu teria acertado {prop['acertos']} "
                      f"(piso {prop['piso']:.0%}). Diga 'aprova a evolução do cérebro' ou 'recusa a evolução'.")
    else:
        par = M.placar_cerebro()["parecida"]
        partes.append(f"Sem proposta agora: tenho {par['n']} caso(s) parecidos medidos (preciso de {M.MIN_CASOS} com piso de "
                      f"{M.PISO_PROMOVER:.0%}).")
    hist = d.get("historico", [])[-4:]
    if hist:
        partes.append("Histórico: " + "; ".join(h["acao"] for h in hist) + ".")
    return " ".join(partes)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"placar": _placar, "cerebro": _cerebro, "evolucao": _evolucao, "aprovar": lambda p, pl: M.aprovar(),
                              "recusar": lambda p, pl: M.recusar(), "rebaixar": lambda p, pl: M.rebaixar()}, player, "Metacognição")
