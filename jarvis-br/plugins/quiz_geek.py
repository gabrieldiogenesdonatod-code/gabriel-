"""
Quiz geek (fork PT-BR 1.6) — Marvel, DC, animes, games, Star Wars, tecnologia.

Perguntas de múltipla escolha valendo pontos, com sequência de acertos (vale
mais) e placar guardado. Com a chave do Gemini, ele cria perguntas novas do
tema que você pedir; sem ela, usa o banco de perguntas daqui.

    "Jarvis, quiz geek de animes"      "Jarvis, é a letra B"      "Jarvis, meu placar no quiz"
"""

from __future__ import annotations

import random
import re
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json

PLUGIN = {
    "name": "quiz_geek",
    "brief": "Geek trivia (Marvel, anime, games, Star Wars, tech) by voice, multiple choice, points and streaks.",
    "description": (
        "Geek quiz by voice. action='pergunta' with optional tema (marvel, dc, anime, games, star wars, tecnologia, "
        "or anything); action='responder' with resposta (letter or the answer text); action='placar'. Read the question "
        "and the options exactly as returned."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "pergunta | responder | placar"},
                       "tema": {"type": "STRING"}, "resposta": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "quiz_geek.json"
BANCO = [  # (tema, pergunta, [opções], índice certo)
    ("marvel", "Qual é o nome verdadeiro do Homem de Ferro?", ["Steve Rogers", "Tony Stark", "Bruce Banner", "Peter Parker"], 1),
    ("marvel", "De que metal é feito o escudo do Capitão América?", ["Adamantium", "Vibranium", "Uru", "Titânio"], 1),
    ("marvel", "Qual Joia do Infinito estava no cetro do Loki?", ["Joia da Mente", "Joia do Tempo", "Joia da Alma", "Joia do Poder"], 0),
    ("marvel", "Como se chama a IA que substituiu o J.A.R.V.I.S. nos trajes do Tony?", ["KAREN", "F.R.I.D.A.Y.", "EDITH", "ULTRON"], 1),
    ("marvel", "Em que país fica Wakanda?", ["No sul da Ásia", "Na África", "Na América do Sul", "Na Europa"], 1),
    ("dc", "Qual é a cidade do Batman?", ["Metrópolis", "Gotham", "Central City", "Star City"], 1),
    ("dc", "Qual é o ponto fraco do Superman?", ["Magia", "Kryptonita", "Luz amarela", "Água"], 1),
    ("anime", "Qual é o sonho do Naruto?", ["Ser Hokage", "Ser Rei dos Piratas", "Ser Mestre Pokémon", "Ser caçador"], 0),
    ("anime", "Em One Piece, qual fruta o Luffy comeu?", ["Mera Mera", "Gomu Gomu", "Hie Hie", "Bara Bara"], 1),
    ("anime", "Quem é o rival eterno do Goku?", ["Piccolo", "Vegeta", "Freeza", "Gohan"], 1),
    ("anime", "Em Death Note, qual é o nome do shinigami que acompanha o Light?", ["Rem", "Ryuk", "Sidoh", "Gelus"], 1),
    ("anime", "Em Attack on Titan, como se chama o protagonista?", ["Levi", "Armin", "Eren", "Reiner"], 2),
    ("anime", "Qual é o tipo do Pikachu?", ["Fogo", "Elétrico", "Normal", "Psíquico"], 1),
    ("games", "Em que jogo aparece o personagem Master Chief?", ["Gears of War", "Halo", "Doom", "Destiny"], 1),
    ("games", "Qual é o nome do encanador da Nintendo de macacão vermelho?", ["Luigi", "Mario", "Wario", "Toad"], 1),
    ("games", "Em Minecraft, qual material é necessário para o portal do Nether?", ["Pedra", "Obsidiana", "Diamante", "Ferro"], 1),
    ("games", "Qual destes é um jogo brasileiro?", ["Celeste", "Horizon Chase", "Hades", "Stardew Valley"], 1),
    ("games", "Em Free Fire, quantos jogadores começam uma partida clássica?", ["50", "100", "64", "30"], 0),
    ("games", "Qual empresa criou o Valorant e o League of Legends?", ["Blizzard", "Riot Games", "Valve", "Epic Games"], 1),
    ("star wars", "Quem é o pai do Luke Skywalker?", ["Obi-Wan", "Darth Vader", "Han Solo", "Yoda"], 1),
    ("star wars", "Qual é a cor do sabre de luz do Mace Windu?", ["Azul", "Verde", "Roxo", "Vermelho"], 2),
    ("tecnologia", "Em que ano o Python foi lançado?", ["1985", "1991", "2000", "2008"], 1),
    ("tecnologia", "O que significa 'HTML'?", ["HyperText Markup Language", "High Tech Modern Language",
                                               "Hyper Transfer Main Link", "Home Tool Markup Language"], 0),
    ("tecnologia", "Quem criou o Linux?", ["Bill Gates", "Linus Torvalds", "Steve Jobs", "Guido van Rossum"], 1),
    ("tecnologia", "Qual é a porta padrão do HTTPS?", ["80", "21", "443", "8080"], 2),
    ("filmes", "Em Matrix, qual pílula o Neo toma?", ["Azul", "Vermelha", "Verde", "Nenhuma"], 1),
    ("filmes", "Qual é o nome do robô em Wall-E que ele se apaixona?", ["EVA", "EVE", "ADA", "NOVA"], 1),
]
LETRAS = "ABCD"


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def resposta_indice(resposta: str, opcoes: list[str]) -> int | None:
    """'b', 'letra B', 'a dois', 'Tony Stark' → índice (pura)."""
    t = _dobrar(resposta).strip()
    m = re.fullmatch(r"(?:e\s+)?(?:a\s+)?(?:(?:letra|alternativa|opcao)\s+)?([abcd])[.!)]?", t)
    if m:
        return "abcd".index(m.group(1))
    numeros = {"1": 0, "um": 0, "primeira": 0, "2": 1, "dois": 1, "segunda": 1, "3": 2, "tres": 2, "terceira": 2,
               "4": 3, "quatro": 3, "quarta": 3}
    for k, v in numeros.items():
        if re.search(rf"\b{k}\b", t):
            return v
    for i, o in enumerate(opcoes):
        if _dobrar(o) in t or t in _dobrar(o) and len(t) > 2:
            return i
    return None


def pontos(sequencia: int) -> int:
    return 10 + 5 * min(sequencia, 6)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "pergunta").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("pontos", 0)
        d.setdefault("sequencia", 0)
        d.setdefault("acertos", 0)
        d.setdefault("total", 0)
        d.setdefault("feitas", [])
        if acao == "placar":
            return f"{d['pontos']} pontos, {d['acertos']} acertos em {d['total']} perguntas, sequência atual {d['sequencia']}."
        if acao == "responder":
            atual = d.get("atual")
            if not atual:
                return "Não há pergunta em andamento. Diga 'quiz geek'."
            i = resposta_indice(str(p.get("resposta") or ""), atual["opcoes"])
            if i is None:
                return "Não entendi a resposta. Diga a letra: A, B, C ou D."
            d["total"] += 1
            certa = atual["certa"]
            d.pop("atual")
            if i == certa:
                ganho = pontos(d["sequencia"])
                d["sequencia"] += 1
                d["acertos"] += 1
                d["pontos"] += ganho
                gravar_json(_ARQ, d)
                return f"[ACERTOU] +{ganho} pontos (sequência {d['sequencia']}). Total {d['pontos']}. Comemore curto e ofereça a próxima."
            d["sequencia"] = 0
            gravar_json(_ARQ, d)
            return f"[ERROU] A certa era {LETRAS[certa]}) {atual['opcoes'][certa]}. Total {d['pontos']}. Seja simpático e ofereça a próxima."
        tema = _dobrar(str(p.get("tema") or ""))
        pergunta = None
        from plugins import _ia
        conhecidos = {t for t, *_ in BANCO}
        if _ia.disponivel() and tema and not any(tema in c for c in conhecidos):
            r = _ia.perguntar_json(
                f"Crie 1 pergunta de quiz geek sobre '{tema}', de dificuldade média, com 4 alternativas e só uma certa, "
                'em português do Brasil. Responda SÓ JSON {"pergunta": "", "opcoes": ["", "", "", ""], "certa": 0-3}',
                False, 25)
            if isinstance(r, dict) and len(r.get("opcoes") or []) == 4 and str(r.get("certa")).isdigit():
                pergunta = (tema, r["pergunta"], [str(x) for x in r["opcoes"]], int(r["certa"]))
        if not pergunta:
            cands = [b for b in BANCO if (not tema or tema in b[0] or b[0] in tema) and b[1] not in d["feitas"]] or \
                [b for b in BANCO if b[1] not in d["feitas"]] or BANCO
            pergunta = random.choice(cands)
            d["feitas"] = (d["feitas"] + [pergunta[1]])[-len(BANCO) + 3:]
        _t, texto, opcoes, certa = pergunta
        ordem = list(range(4))
        random.shuffle(ordem)
        opcoes2 = [opcoes[i] for i in ordem]
        d["atual"] = {"pergunta": texto, "opcoes": opcoes2, "certa": ordem.index(certa)}
        gravar_json(_ARQ, d)
        return (f"[QUIZ] Leia como apresentador de quiz: \"{texto}\" "
                + " ".join(f"{LETRAS[i]}) {o}." for i, o in enumerate(opcoes2))
                + " Espere a resposta e chame quiz_geek action='responder'. NÃO diga qual é a certa.")
    except Exception as e:
        return f"O quiz falhou: {e}"
