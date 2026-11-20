"""Jogos de festa (2.19): mímica, stop (adedonha), eu nunca, quem é mais provável e desafios leves — para a família toda.

Exemplos: "brincadeira de stop", "sorteia uma palavra de mímica", "um desafio para a roda", "brincadeira para a
festa das crianças", "jogo para a família".
"""
from __future__ import annotations

import random

from plugins._lote2 import P, norm, rodar

PLUGIN = P("jogos_de_festa", "Family party games: charades word, stop/adedonha (letter + categories), never-have-I-ever, who's most likely, light dares; optional timer.",
           "mimica | stop | eu_nunca | quem_e_mais | desafio",
           "mimica: categoria (animais|profissoes|acoes|objetos|esportes). All content is family-friendly.", "categoria")

MIMICA = {"animais": "galinha canguru macaco cobra pinguim girafa sapo caranguejo".split(),
          "profissoes": "dentista bombeiro cozinheiro professor fotografo pedreiro cabeleireiro motorista".split(),
          "acoes": ["escovar os dentes", "trocar uma lâmpada", "andar de bicicleta", "pescar", "fritar um ovo", "tirar uma selfie"],
          "objetos": "guarda-chuva liquidificador escada violao ventilador tesoura".split(),
          "esportes": "natacao volei boxe surfe basquete capoeira".split()}
CATEGORIAS = ["nome", "animal", "cor", "fruta ou comida", "cidade ou país", "objeto", "profissão", "marca", "parte do corpo", "filme ou série"]
EU_NUNCA = ["Eu nunca comi pizza no café da manhã.", "Eu nunca dormi no cinema.", "Eu nunca mandei mensagem para a pessoa errada.",
            "Eu nunca esqueci o nome de alguém logo depois de conhecer.", "Eu nunca fingi que entendi uma piada.",
            "Eu nunca procurei o celular com ele na mão.", "Eu nunca cantei no chuveiro como se fosse show.",
            "Eu nunca caí de bicicleta.", "Eu nunca comi a sobremesa antes do almoço.", "Eu nunca ri numa hora séria."]
QUEM = ["esquecer onde deixou o celular", "virar famoso na internet", "chorar em filme de animação", "ganhar um reality de culinária",
        "se perder usando GPS", "dormir primeiro na festa", "adotar dez cachorros", "rir da própria piada", "chegar atrasado no próprio aniversário"]
DESAFIOS = ["Imite um robô por 10 segundos.", "Fale uma frase inteira sem abrir os dentes.", "Dance 15 segundos sem música.",
            "Conte até 10 com voz de locutor de rádio.", "Faça o seu melhor som de animal e os outros adivinham.",
            "Elogie cada pessoa da roda em uma palavra.", "Fique num pé só até a próxima rodada.", "Cante o parabéns em câmera lenta."]


def letra_stop(rng=random) -> str:
    return rng.choice("ABCDEFGHIJLMNOPRSTUV")


def _timer(pl, nome, tempo):
    try:
        from core import registro_ferramentas
        registro_ferramentas.executar("cronometros", {"action": "timer", "nome": nome, "tempo": tempo}, pl)
    except Exception:
        pass


def _go(p, pl):
    a = p["action"]
    if a == "mimica":
        c = norm(p.get("categoria"))
        c = c if c in MIMICA else random.choice(list(MIMICA))
        _timer(pl, "mímica", "60 s")
        return f"Mímica, categoria {c}. Só quem vai fazer olha a tela: {random.choice(MIMICA[c]).upper()}. Valendo 1 minuto!"
    if a == "stop":
        _timer(pl, "stop", "90 s")
        return f"Stop! Letra {letra_stop()}. Categorias: {', '.join(random.sample(CATEGORIAS, 6))}. Vocês têm 90 segundos!"
    if a == "eu_nunca":
        return random.choice(EU_NUNCA) + " Quem já fez levanta a mão!"
    if a == "quem_e_mais":
        return f"Quem aqui é mais provável de {random.choice(QUEM)}? No três, todo mundo aponta!"
    return "Desafio: " + random.choice(DESAFIOS)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("mimica stop eu_nunca quem_e_mais desafio".split(), _go), player, "Jogos de festa")
