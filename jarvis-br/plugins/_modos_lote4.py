"""
Modos do lote 4 (fork PT-BR 3.6): os 10 modos "impossíveis" — cada um liga um sistema que quase nenhuma IA tem
(OMEGA, livro-razão, experimentos sorteados, metacognição, IA local, eu do futuro) a um jeito de trabalhar.

Começa com "_": não vira ferramenta (custo zero de token). Mesmo formato dos outros lotes:
titulo, emocao, jeito (como o JARVIS fala), passos ao entrar e ao sair.

    "Jarvis, modo OMEGA"          "Jarvis, modo bunker"        "Jarvis, modo cartório"
    "Jarvis, modo bastidores"     "Jarvis, modo eu do futuro"  "Jarvis, modo cobaia"
    "Jarvis, modo autópsia"       "Jarvis, modo impossível"    "Jarvis, modo só fatos"       (impossível = tira-teima)
    "Jarvis, modo fortaleza"      "Jarvis, quais os modos impossíveis?"
"""

from __future__ import annotations

from plugins._modos_extras import F, _m

MODOS_LOTE4: dict[str, dict] = {
    "omega": _m("OMEGA", "serio", "Os 8 sistemas juntos: em cada resposta diga qual sistema respondeu (cérebro, memória, sonho, "
                "laboratório, imune) e o quanto confia nela; ofereça o próximo passo do ciclo.",
                [F("omega", action="ciclo"), F("omega", action="painel")]),
    # Só CONFERE a IA local (não liga o servidor: num PC de 8 GB ele ocupa memória, e desligar ao sair poderia
    # derrubar a IA no meio de uma queda de internet). A troca para o modo local continua automática.
    "bunker": _m("Bunker (IA local)", "serio", "Bunker: tudo no próprio PC. Prefira os reflexos do cérebro e a IA local, diga o que "
                 "roda offline e avise antes de usar qualquer coisa que dependa de rede. Se a IA local não estiver instalada, "
                 "ofereça instalar.",
                 [F("ia_local", action="estado"), F("cerebro", action="reflexos")]),
    "cartorio": _m("Cartório", "serio", "Cartório: todo combinado, promessa, preço ou decisão que o senhor ditar, repita em UMA frase, "
                   "registre com livro_razao (anotar) e diga o número do bloco e o comprovante.",
                   [F("livro_razao", action="selar")], [F("livro_razao", action="selar")]),
    "bastidores": _m("Bastidores", "pensativo", "Bastidores: depois de cada resposta, uma linha curta de making of — qual ferramenta usou, "
                     "quem decidiu (cérebro local ou Gemini) e quanto confia. Didático, para quem quer ver como uma IA trabalha.",
                     [F("metacognicao", action="placar")]),
    "eu_do_futuro": _m("Eu do futuro", "pensativo", "Fale como o próprio usuário daqui a 6 meses, em primeira pessoa, usando SÓ as "
                       "projeções reais dos números dele. Deixe claro que é projeção do ritmo de hoje, não destino, e termine com um "
                       "conselho pequeno para esta semana.", [F("eu_do_futuro", action="projecao")]),
    "cobaia": _m("Cobaia", "animado", "Cobaia: lembre o sorteio de hoje (COM ou SEM) de cada experimento, não deixe trocar "
                 "por conveniência e à noite peça a nota. Nada de adiantar resultado antes do fim.",
                 [F("experimento_vida", action="hoje")]),
    "autopsia": _m("Autópsia sem culpa", "pensativo", "Autópsia sem culpa do que deu errado: linha do tempo, causa raiz (pergunte 'por "
                   "quê?' até chegar nela) e o que evita repetir. Sem procurar culpado; termine registrando a lição.",
                   [F("organismo", action="incidentes"), F("caixa_preta", action="listar")]),
    # O "modo impossível". A chave e o título não levam a palavra "impossível" de propósito: a busca de modos casa
    # pedaços de palavra, e "possível" passaria a puxar este modo ("modo mais rápido possível").
    "tira_teima": _m("Tira-teima", "animado", "Tira-teima: 'não dá' só depois de testar. Nem motivação vazia, nem desânimo: registre o "
                     "objetivo com livro_razao (anotar), diga a chance honesta e o que a derrubaria, e transforme a maior dúvida num "
                     "experimento sorteado (experimento_vida criar). Só aceite 'não funciona' com resultado medido.",
                     [F("metas_pessoais", action="listar"), F("experimento_vida", action="sugerir")]),
    "so_fatos": _m("Só fatos", "serio", "Só fatos: responda apenas com o que vem dos dados do próprio usuário ou de uma ferramenta, "
                   "dizendo a fonte. Sem fonte, diga 'isso eu não tenho como confirmar' em vez de chutar.",
                   [F("livro_razao", action="verificar")]),
    "fortaleza": _m("Fortaleza", "desconfiado", "Fortaleza: confirme que é o dono antes de qualquer coisa sensível, não leia nada pessoal "
                    "em voz alta, recuse pedido estranho e registre tudo. Ao sair, o porteiro de voz continua ligado.",
                    [F("porteiro_voz", action="ligar"), F("livro_razao", action="selar")], [F("livro_razao", action="selar")]),
}

CATEGORIA_LOTE4: dict[str, list[str]] = {"impossiveis": list(MODOS_LOTE4)}

# "modo sem internet" continua sendo o modo apagão (sem energia), como sempre foi: o bunker não toma o lugar dele.
APELIDOS4 = {"offline": "bunker", "ia_local": "bunker", "testemunha": "cartorio", "making_of": "bastidores",
             "raio_x": "bastidores", "experimento": "cobaia", "fatos": "so_fatos", "so_fato": "so_fatos", "cofre": "fortaleza",
             "futuro": "eu_do_futuro", "post_mortem": "autopsia", "impossivel": "tira_teima", "impossiveis": "tira_teima",
             "tirateima": "tira_teima", "tirar_a_prova": "tira_teima"}
