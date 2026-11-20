"""Piadas (2.18): trocadilhos de programador, geek e de tiozão, sem repetir as últimas contadas."""
from __future__ import annotations

import random

from plugins import _lote2
from plugins._lote2 import P, gravar_json, ler_json, rodar

PLUGIN = P("piadas", "Jokes in Portuguese: programmer, geek, dad jokes and riddles-style puns; avoids repeating recent ones.",
           "contar | tipos",
           "contar: tipo (dev|geek|tiozao|qualquer).", "tipo")

PIADAS = {
    "dev": ["Por que o programador foi ao médico? Porque estava com um bug no sistema.",
            "Quantos programadores são precisos para trocar uma lâmpada? Nenhum, é problema de hardware.",
            "O Python foi à festa sozinho porque não queria se indentar com ninguém.",
            "Meu código funciona e eu não sei por quê. Meu código não funciona e eu também não sei por quê.",
            "Por que o Java usa óculos? Porque ele não C#.",
            "Eu ia contar uma piada de UDP, mas talvez você não receba.",
            "Existem 10 tipos de pessoas: as que entendem binário e as que não entendem.",
            "O commit dizia 'pequeno ajuste'. Mudou 47 arquivos.",
            "O Git e eu temos algo em comum: a gente vive fazendo merge de sentimentos em conflito.",
            "Programador otimista: 'só falta um detalhe'. Programador realista: o detalhe é o projeto inteiro.",
            "Na minha máquina funciona. Então vamos mandar a sua máquina para o cliente.",
            "O estagiário apagou o banco de produção. Agora ele é o DBA: Deletou Banco Agora.",
            "Deus fez o mundo em seis dias porque não tinha sistema legado.",
            "Tem dois problemas difíceis na programação: dar nome às coisas, invalidar cache e errar a conta por um.",
            "Fui debugar com um patinho de borracha. Ele achou o bug e pediu aumento.",
            "A senha tem que ter oito caracteres: escolhi Branca de Neve e os sete anões."],
    "geek": ["Por que o Homem de Ferro nunca se perde? Porque ele tem um JARVIS no GPS.",
             "O Thanos estalou os dedos e metade dos meus bugs sumiu. A outra metade virou feature.",
             "Qual o jogo favorito do eletricista? League of Legends… quer dizer, Liga das Lâmpadas.",
             "O Wi-Fi do vizinho se chama 'Vírus Detectado'. Eu também não confio em mim mesmo.",
             "O Pikachu foi ao mercado e voltou com uma conta muito alta. Choque de preços.",
             "Por que o Jedi não usa elevador? Porque ele prefere a Força."],
    "tiozao": ["O que o pagodeiro foi fazer na igreja? Cantar pá God.",
               "Por que a plantinha não foi atendida no hospital? Porque só tinha médico de plantão.",
               "Qual é o contrário de volátil? Vem cá, sobrinho.",
               "O que o zero disse para o oito? Que cinto bonito!",
               "Por que o livro de matemática ficou triste? Porque tinha muitos problemas.",
               "Sabe por que o pão não entende a batata? Porque ele é francês e ela é inglesa.",
               "O que é um pontinho amarelo na janela? Um fandango olhando a vista.",
               "Por que o jacaré tirou o filho da escola? Porque ele réptil de ano.",
               "O que a impressora falou para a outra? Essa folha é sua ou é impressão minha?",
               "Qual é o café mais perigoso do mundo? O ex-presso.",
               "O que o tomate foi fazer no banco? Tirar extrato.",
               "Por que a aranha é o animal mais carente? Porque ela é um ar-carente... digo, aracnídeo."],
}


def escolher(tipo: str, recentes: list[str], rng=random) -> str:
    pool = PIADAS.get(tipo) or [x for v in PIADAS.values() for x in v]
    novas = [x for x in pool if x not in recentes] or pool
    return rng.choice(novas)


def _go(p, pl):
    if str(p.get("action")).lower() == "tipos":
        return "Tipos: dev, geek, tiozao."
    arq = _lote2.PASTA / "piadas.json"
    rec = ler_json(arq, []) or []
    pj = escolher(str(p.get("tipo") or "").lower(), rec)
    gravar_json(arq, (rec + [pj])[-15:])
    return pj


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"contar": _go, "tipos": _go}, player)
