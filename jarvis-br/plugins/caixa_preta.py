"""
Caixa-preta (3.3): os erros que o JARVIS já cometeu com você, para ele não repetir.

    "Jarvis, mostra a caixa-preta"                     "Jarvis, você já errou alguma coisa sobre a loja?"
    "Jarvis, anota na caixa-preta: quando eu disser 'a loja', é a Cristal Malhas"
    "Jarvis, esquece o erro 3"                         "Jarvis, apaga a caixa-preta"

Ele registra sozinho quando você o corrige ("não, não foi isso"). Como funciona: core/caixa_preta.py.
"""

from __future__ import annotations

from core import caixa_preta as CP
from plugins._lote2 import P, num1, rodar

PLUGIN = P("caixa_preta", "JARVIS's black box: mistakes it made with this user (what was asked, what it said, the correction) so it "
                          "does not repeat them.",
           "listar | consultar | anotar | esquecer | limpar",
           "listar: recorded mistakes. consultar: tema — mistakes about a subject. anotar: pergunta, correcao — record a rule the "
           "user dictates. esquecer: numero. limpar: erase all.", "tema pergunta correcao numero")


def _linha(e: dict) -> str:
    return (f"#{e['id']} ({e.get('vezes', 1)}×): você pediu \"{e['pergunta'][:90]}\""
            + (f", eu respondi \"{e['resposta'][:70]}\"" if e.get("resposta") else "") + f" e corrigiu: \"{e['correcao'][:110]}\"")


def _listar(p, pl):
    es = CP.erros()
    if not es:
        return "A caixa-preta está vazia: ainda não registrei nenhum erro meu com você."
    return f"{len(es)} erro(s) na caixa-preta (os primeiros entram nas minhas instruções):\n" + "\n".join(_linha(e) for e in es[:10])


def _consultar(p, pl):
    tema = str(p.get("tema") or p.get("pergunta") or "").strip()
    if not tema:
        return _listar(p, pl)
    es = CP.parecidos(tema)
    return ("Sobre isso eu já errei:\n" + "\n".join(_linha(e) for e in es)) if es else f"Não tenho erro registrado sobre '{tema}'."


def _anotar(p, pl):
    pergunta, correcao = str(p.get("pergunta") or "").strip(), str(p.get("correcao") or "").strip()
    if not pergunta or not correcao:
        return "Me diga as duas partes: quando você fala o quê, e o que é o certo."
    e = CP.registrar(pergunta, "", correcao, origem="ditado")
    if e is None:
        return "No modo anônimo eu não guardo nada."
    return f"Anotado na caixa-preta (#{e['id']}): quando você disser \"{pergunta[:80]}\", o certo é \"{correcao[:100]}\"."


def _esquecer(p, pl):
    n = int(num1(p, "numero", 0))
    return f"Esqueci o erro #{n}." if n and CP.esquecer(n) else "Não achei esse número na caixa-preta."


def _limpar(p, pl):
    return f"Caixa-preta apagada ({CP.limpar()} registro(s))."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"listar": _listar, "consultar": _consultar, "anotar": _anotar, "esquecer": _esquecer,
                              "limpar": _limpar}, player)
