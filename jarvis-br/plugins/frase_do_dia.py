"""Frase do dia (2.19): uma frase curta para começar o dia — de foco, de programador, de quem tem loja ou de coragem; a do dia é a mesma o dia todo."""
from __future__ import annotations

import random
import zlib

from plugins._lote2 import P, hoje, norm, rodar

PLUGIN = P("frase_do_dia", "Short original motivational line for the day (focus, developer, shop owner, courage): today's line (stable all day), another one, themes.",
           "hoje | outra | temas", "outra: tema (foco|dev|loja|coragem).", "tema")

FRASES = {
    "foco": ["Uma coisa de cada vez, bem feita, vale mais que dez pela metade.", "Comece pelo que você está evitando.",
             "Vinte minutos de atenção inteira rendem mais que duas horas distraídas.", "O que não está na agenda vira 'um dia'.",
             "Feche as abas. A tarefa é só uma.", "Cansado não é motivo para desistir; é motivo para descansar e voltar."],
    "dev": ["Faça funcionar, depois deixe bonito, depois deixe rápido.", "O bug mais difícil é o que você tem certeza que não existe.",
            "Código simples é o que o você de daqui a seis meses agradece.", "Teste hoje o que você não quer depurar de madrugada.",
            "Commit pequeno, cabeça tranquila.", "Ler o erro inteiro resolve metade dos problemas."],
    "loja": ["Cliente bem atendido volta e ainda traz outro.", "Vitrine arrumada vende enquanto você atende.",
             "Quem anota o que vende descobre o que comprar.", "Preço se esquece; atendimento ruim, não.",
             "Uma foto boa do produto trabalha por você o dia inteiro.", "Pequeno todo dia vira grande no fim do ano."],
    "coragem": ["O impossível é só o que ainda ninguém terminou.", "Você não precisa ver a escada toda para subir o primeiro degrau.",
                "Medo e vontade podem andar juntos; vá assim mesmo.", "Quem tenta pode errar; quem não tenta já errou.",
                "Hoje é um bom dia para fazer o que o você de ontem achou difícil.", "Devagar também é para frente."],
}


def do_dia(dia: str) -> str:
    todas = [f for v in FRASES.values() for f in v]
    return todas[zlib.crc32(dia.encode()) % len(todas)]


def _go(p, pl):
    a = p["action"]
    if a == "temas":
        return "Temas: " + ", ".join(FRASES) + "."
    if a == "hoje":
        return do_dia(hoje())
    return random.choice(FRASES.get(norm(p.get("tema"))) or [f for v in FRASES.values() for f in v])


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"hoje": _go, "outra": _go, "temas": _go}, player)
