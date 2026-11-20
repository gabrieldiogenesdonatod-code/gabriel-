"""
Adivinha quem eu sou (fork PT-BR 2.17) — jogo de festa, funciona sem internet.

    "Jarvis, vamos jogar adivinha"          (tema: herois, animais, games, objetos, profissoes ou aleatório)
    "Jarvis, me dá uma dica"                → dicas cada vez mais fáceis
    "Jarvis, é o Homem-Aranha?"             → ele confere (aceita sem acento e parecido)
    "Jarvis, desisto"                        → revela

Pontos: 3 sem dica, 2 com uma, 1 com duas ou mais. Placar da sessão.
"""

from __future__ import annotations

import random
import unicodedata
from difflib import SequenceMatcher

PLUGIN = {
    "name": "adivinha",
    "brief": "Party guessing game: JARVIS thinks of something and gives clues; checks guesses; score.",
    "description": (
        "Guess-who game. action='novo' (optional tema = herois | animais | games | objetos | profissoes). "
        "action='dica'. action='chute' with resposta. action='desistir'. action='placar'. Say only what the tool "
        "returns; never reveal the answer before the user guesses or gives up."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "tema": {"type": "STRING"},
                                                    "resposta": {"type": "STRING"}}, "required": ["action"]},
}

CARTAS = {
    "herois": [("Homem de Ferro", ["sou um bilionário", "uso uma armadura", "tenho um assistente chamado JARVIS"]),
               ("Homem-Aranha", ["sou jovem e moro em Nova York", "minha tia se chama May", "solto teias"]),
               ("Batman", ["não tenho superpoderes", "moro em Gotham", "meu símbolo é um morcego"]),
               ("Mulher-Maravilha", ["sou uma princesa guerreira", "venho de uma ilha só de mulheres", "uso um laço da verdade"]),
               ("Hulk", ["sou cientista", "fico enorme quando tenho raiva", "sou verde"])],
    "animais": [("girafa", ["vivo na savana", "sou o animal mais alto", "tenho pescoço comprido"]),
                ("pinguim", ["sou uma ave", "não voo, mas nado muito bem", "gosto do frio e ando engraçado"]),
                ("polvo", ["vivo no mar", "solto tinta", "tenho oito braços"]),
                ("capivara", ["sou o maior roedor do mundo", "adoro água", "sou brasileira e todo mundo me ama"])],
    "games": [("Minecraft", ["tudo em mim é feito de blocos", "tem creeper", "você minera e constrói"]),
              ("Roblox", ["sou uma plataforma com milhões de jogos", "minha moeda é o Robux", "tem obby"]),
              ("Free Fire", ["sou um battle royale", "muito jogado no celular no Brasil", "a partida tem 50 jogadores"]),
              ("Fortnite", ["sou battle royale", "você constrói paredes na luta", "tenho danças famosas"]),
              ("Pac-Man", ["sou um clássico dos anos 80", "fujo de fantasmas", "como bolinhas num labirinto"])],
    "objetos": [("guarda-chuva", ["você me usa às vezes", "abro e fecho", "te protejo da chuva"]),
                ("geladeira", ["fico na cozinha", "sou fria por dentro", "guardo comida"]),
                ("controle remoto", ["sempre some no sofá", "tenho botões", "mudo o canal da TV"])],
    "profissoes": [("bombeiro", ["trabalho em equipe", "uso um caminhão vermelho", "apago incêndios"]),
                   ("programador", ["passo o dia no computador", "conserto bugs", "escrevo código"]),
                   ("padeiro", ["acordo muito cedo", "trabalho com forno", "faço pão francês"])],
}
_jogo = {"carta": None, "dicas": 0, "pontos": 0, "rodadas": 0}


def _n(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
                   if c.isalnum())


def acertou(chute: str, resposta: str) -> bool:
    a, b = _n(chute), _n(resposta)
    return bool(a) and (a == b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.8)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "novo").lower()
    if a == "novo":
        tema = _n(p.get("tema"))
        tema = tema if tema in CARTAS else random.choice(list(CARTAS))
        _jogo.update(carta=random.choice(CARTAS[tema]), dicas=0, tema=tema)
        return f"Pensei em algo do tema {tema}. Primeira dica: {_jogo['carta'][1][0]}. Pode chutar!"
    if not _jogo["carta"]:
        return "Não estamos jogando. Diga 'vamos jogar adivinha'."
    nome, dicas = _jogo["carta"]
    if a == "dica":
        _jogo["dicas"] += 1
        if _jogo["dicas"] >= len(dicas):
            return f"Acabaram as dicas! A primeira letra é '{nome[0]}'."
        return f"Dica: {dicas[_jogo['dicas']]}."
    if a == "chute":
        if acertou(str(p.get("resposta") or ""), nome):
            ganho = 3 if _jogo["dicas"] == 0 else 2 if _jogo["dicas"] == 1 else 1
            _jogo["pontos"] += ganho
            _jogo["rodadas"] += 1
            _jogo["carta"] = None
            return f"Acertou! Era {nome}. +{ganho} ponto(s), total {_jogo['pontos']}. Mais uma?"
        return "Não é isso. Quer outra dica?"
    if a == "desistir":
        _jogo["carta"] = None
        _jogo["rodadas"] += 1
        return f"Era {nome}! Mais uma rodada?"
    return f"Placar: {_jogo['pontos']} ponto(s) em {_jogo['rodadas']} rodada(s)."
