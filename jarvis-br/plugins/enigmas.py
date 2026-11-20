"""Enigmas e charadas (2.18): o JARVIS pergunta, você responde; dica e resposta sob pedido."""
from __future__ import annotations

import random

from plugins import _lote2
from plugins._lote2 import P, gravar_json, ler_json, norm, rodar

PLUGIN = P("enigmas", "Riddles game in Portuguese: ask a riddle, check the answer, hint, reveal, score.",
           "novo | responder | dica | revelar",
           "novo: new riddle. responder: valor. dica. revelar.", "valor")

ENIGMAS = [("O que é que quanto mais se tira, maior fica?", "buraco", "Cava-se."),
           ("O que tem cidades mas não tem casas, rios mas não tem água?", "mapa", "Está na parede da escola."),
           ("O que sobe e desce mas não sai do lugar?", "escada", "Tem degraus."),
           ("Tem dentes mas não morde.", "pente", "Usado no cabelo."),
           ("Quanto mais seca, mais molhada fica.", "toalha", "Banheiro."),
           ("O que é que corre mas não tem pernas?", "rio", "Água."),
           ("Quem fala todas as línguas sem nunca ter estudado?", "eco", "Repete você."),
           ("O que é que tem pescoço mas não tem cabeça?", "garrafa", "Guarda líquidos."),
           ("O que é que anda com os pés na cabeça?", "piolho", "Mora no cabelo."),
           ("O que quebra quando você fala o nome?", "silencio", "Shhh."),
           ("O que tem teclas mas não abre portas?", "teclado", "Você usa para programar."),
           ("Sou leve como uma pena, mas ninguém me segura por muito tempo.", "respiracao", "Faça agora."),
           ("O que é que nasce grande e morre pequeno?", "lapis", "Escreve e é apontado."),
           ("O que é que tem olho mas não enxerga?", "agulha", "Usada para costurar."),
           ("O que passa diante do sol e não faz sombra?", "vento", "Não dá para ver."),
           ("Tenho chaves mas não abro portas, tenho espaço mas não tenho quarto. O que sou?", "teclado", "Está na sua mesa."),
           ("Quanto mais você tira de mim, mais eu deixo para trás. O que sou?", "passo", "Você dá ao caminhar."),
           ("O que é que está sempre na sua frente mas você não consegue ver?", "futuro", "Ainda vai chegar."),
           ("Se você me tem, quer me contar; se me conta, não me tem mais. O que sou?", "segredo", "Fica entre nós."),
           ("O que tem mãos mas não bate palmas?", "relogio", "Fica na parede ou no pulso."),
           ("O que enche uma casa mas não ocupa espaço?", "luz", "Acende no interruptor."),
           ("Qual é a coisa que, quanto maior, menos se vê?", "escuridao", "Chega de noite.")]


def _arq():
    return _lote2.PASTA / "enigmas.json"


def _go(p, pl):
    a, e = str(p.get("action")).lower(), ler_json(_arq(), {}) or {"pontos": 0}
    if a == "novo" or e.get("i") is None:
        e["i"] = random.randrange(len(ENIGMAS))
        gravar_json(_arq(), e)
        return ENIGMAS[e["i"]][0]
    q, r, d = ENIGMAS[e["i"]]
    if a == "dica":
        return d
    if a == "revelar" or norm(p.get("valor")).find(r) >= 0:
        acertou = a != "revelar"
        e["pontos"] += acertou
        e["i"] = None
        gravar_json(_arq(), e)
        return (f"Acertou! Pontos: {e['pontos']}." if acertou else f"Era: {r}.") + " Quer outro?"
    return "Não é isso. Quer uma dica?"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("novo responder dica revelar".split(), _go), player)
