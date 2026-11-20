"""Curiosidades (2.19): fatos rápidos e verdadeiros sobre espaço, animais, corpo humano, tecnologia, Brasil e ciência, sem repetir os últimos."""
from __future__ import annotations

import random

from plugins._lote2 import P, carregar, guardar, norm, rodar

PLUGIN = P("curiosidades", "Quick true fun facts (space, animals, human body, technology, Brazil, science), avoiding recent repeats.",
           "contar | temas", "contar: tema (espaco|animais|corpo|tecnologia|brasil|ciencia|qualquer).", "tema")

FATOS = {
    "espaco": ["A luz do Sol leva cerca de 8 minutos e 20 segundos para chegar à Terra.",
               "Um dia em Vênus dura mais que um ano em Vênus: ele gira mais devagar do que dá a volta no Sol.",
               "A Lua se afasta da Terra cerca de 3,8 centímetros por ano.", "Saturno é menos denso que a água.",
               "Júpiter tem mais de 90 luas conhecidas.", "No espaço não há som, porque não existe ar para carregar as ondas sonoras."],
    "animais": ["Polvos têm três corações e sangue azulado.", "Golfinhos dormem com metade do cérebro de cada vez.",
                "A capivara é o maior roedor do mundo.", "O coração de um beija-flor pode passar de mil batidas por minuto.",
                "Tubarões existem há mais tempo que as árvores.", "As abelhas avisam onde estão as flores com uma dança."],
    "corpo": ["O corpo de um adulto tem 206 ossos.", "O coração bate cerca de 100 mil vezes por dia.",
              "As impressões digitais se formam antes do nascimento e são únicas.",
              "O cérebro usa cerca de 20% da energia do corpo em repouso."],
    "tecnologia": ["O primeiro 'bug' de computador registrado foi uma mariposa presa num relé do Harvard Mark II, em 1947.",
                   "O primeiro site do mundo foi ao ar em 1991, criado por Tim Berners-Lee no CERN.",
                   "A linguagem Python tem esse nome por causa do grupo de humor Monty Python, não da cobra.",
                   "O teclado QWERTY foi desenhado para máquinas de escrever na década de 1870.",
                   "O primeiro disco rígido, da IBM em 1956, guardava uns 5 milhões de caracteres e pesava perto de uma tonelada.",
                   "O computador de bordo da Apollo tinha cerca de 4 kilobytes de memória RAM."],
    "brasil": ["O Brasil faz fronteira com quase todos os países da América do Sul, menos Chile e Equador.",
               "Goiânia foi planejada e fundada em 1933.", "O pequi, símbolo do Cerrado, tem espinhos dentro do caroço.",
               "O nome Brasil vem do pau-brasil, árvore de madeira avermelhada.",
               "A Amazônia forma 'rios voadores': massas de vapor que levam chuva para outras regiões do país."],
    "ciencia": ["O mel praticamente não estraga: já encontraram mel conservado em tumbas egípcias.",
                "Bananas são levemente radioativas por causa do potássio.", "Um raio é várias vezes mais quente que a superfície do Sol.",
                "O diamante e o grafite do lápis são feitos do mesmo elemento: carbono.", "O vidro é feito principalmente de areia."],
}


def escolher(tema: str, recentes: list[str], rng=random) -> str:
    pool = FATOS.get(norm(tema)) or [f for v in FATOS.values() for f in v]
    return rng.choice([f for f in pool if f not in recentes] or pool)


def _go(p, pl):
    if p["action"] == "temas":
        return "Temas: " + ", ".join(FATOS) + "."
    rec = carregar("curiosidades", [])
    f = escolher(p.get("tema"), rec)
    guardar("curiosidades", (rec + [f])[-20:])
    return f


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"contar": _go, "temas": _go}, player)
