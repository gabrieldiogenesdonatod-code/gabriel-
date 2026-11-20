"""
Modos do lote 5 (fork PT-BR 3.8): mineração, cripto e garagem.

Começa com "_": não vira ferramenta (custo zero de token). Mesmo formato dos outros lotes.
Como no lote 4, só entram onde antes não havia resposta: nome que já ativava um modo continua igual.

    "Jarvis, modo mineração"      "Jarvis, modo cripto"      "Jarvis, modo garagem"
    "Jarvis, quais os modos de dinheiro e garagem?"
"""

from __future__ import annotations

from plugins._modos_extras import F, _m

MODOS_LOTE5: dict[str, dict] = {
    # Entrar NÃO liga o minerador: mostra a conta e o status. Ligar continua pedindo confirmação na tela.
    # Sair desliga a mineração, se estiver ligada.
    "mineracao": _m("Mineração", "serio", "Mineração: fale de mineração com números de verdade (mineracao calcular e status), "
                    "sempre comparando ganho com a conta de luz. Só liga o minerador se o senhor pedir, e a confirmação aparece "
                    "na tela. Ao sair do modo, a mineração é desligada.",
                    [F("mineracao", action="calcular"), F("mineracao", action="status")], [F("mineracao", action="desligar")]),
    "cripto": _m("Cripto", "serio", "Cripto: acompanhe a carteira (carteira_cripto) e as cotações (alerta_cotacao). Mostre lucro e "
                 "prejuízo pelo custo médio, lembre que cripto oscila muito e nunca diga para comprar ou vender: o senhor decide. "
                 "Nunca peça frase de recuperação nem chave privada.",
                 [F("carteira_cripto", action="ver")]),
    "garagem": _m("Garagem", "animado", "Garagem: ajude com o carro ou a moto como um mecânico de confiança. Mostre o que está "
                  "vencendo (veiculo proximas), anote cada serviço com km e valor (veiculo fiz) e lembre que o manual do veículo "
                  "manda. Barulho estranho, freio ou cheiro de queimado: oriente a parar e levar a uma oficina.",
                  [F("veiculo", action="proximas")]),
}

CATEGORIA_LOTE5: dict[str, list[str]] = {"dinheiro_e_garagem": list(MODOS_LOTE5)}

APELIDOS5 = {"minerar": "mineracao", "mineradora": "mineracao", "bitcoin": "cripto", "criptomoeda": "cripto",
             "criptomoedas": "cripto", "moedas": "cripto", "carteira_cripto": "cripto", "oficina": "garagem",
             "mecanico": "garagem", "carro_e_moto": "garagem", "manutencao_carro": "garagem"}
