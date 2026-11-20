"""
Modos do lote 2 (fork PT-BR 2.18): 58 modos novos para o plugin `modos`.

Começa com "_": não vira ferramenta (não gasta token na declaração). O
modos.py junta esta tabela com a dele; cada modo segue o mesmo formato:
titulo, emocao, jeito (como o JARVIS fala), entrar e sair (passos de protocolo).

Atalhos para escrever menos:
    F(nome, **params)  passo 'ferramenta'      A("x, y")  abrir    X("x, y")  fechar
    V(n)  volume       M("texto")  mensagem    S(url)     site
"""

from __future__ import annotations


def F(ferramenta, /, **params):
    return {"tipo": "ferramenta", "nome": ferramenta, "params": params}


def A(alvo):
    return {"tipo": "abrir", "alvo": alvo}


def X(alvo):
    return {"tipo": "fechar", "alvo": alvo}


def V(n):
    return {"tipo": "volume", "nivel": n}


def M(texto):
    return {"tipo": "mensagem", "texto": texto}


def S(url):
    return {"tipo": "site", "alvo": url}


DISTRAI = "discord, steam, roblox, whatsapp"
ALTO, EQUI, ECO = ({"tipo": "plano_energia", "plano": p} for p in ("alto desempenho", "equilibrado", "economia"))
ESCURO, CLARO = {"tipo": "modo_escuro", "ligar": "sim"}, {"tipo": "modo_escuro", "ligar": "nao"}
MUDO, SOM = {"tipo": "mudo", "ligar": "sim"}, {"tipo": "mudo", "ligar": "nao"}


def _m(titulo, emocao, jeito, entrar=(), sair=()):
    return {"titulo": titulo, "emocao": emocao, "jeito": jeito, "entrar": list(entrar), "sair": list(sair)}


MODOS_EXTRAS: dict[str, dict] = {
    # ── estudo e foco ──
    "estudo": _m("Estudo", "pensativo", "Tutor paciente: explique em passos curtos, faça uma pergunta de checagem no fim e não puxe outros assuntos.",
                 [X(DISTRAI), F("pomodoro", action="iniciar"), F("sequencias", action="feito", nome="estudar")],
                 [F("pomodoro", action="parar")]),
    "prova": _m("Véspera de prova", "serio", "Revisão relâmpago: resuma em tópicos, priorize o que mais cai, termine com 1 pergunta de teste. Acalme se ele estiver nervoso.",
                [X(DISTRAI), F("clone_estudo", action="desempenho")]),
    "leitura": _m("Leitura", "neutro", "Silêncio. Só responda se chamado, em uma frase. Pode explicar palavras difíceis do livro.",
                  [V(15), {"tipo": "minimizar_tudo"}], [V(50)]),
    "foco_profundo": _m("Foco profundo", "serio", "Não interrompa por nada que não seja urgente. Respostas de no máximo 2 frases.",
                        [X(DISTRAI + ", spotify"), MUDO, F("procrastinacao", action="focar")],
                        [SOM, F("procrastinacao", action="retomar")]),
    "biblioteca": _m("Silêncio total", "neutro", "Não fale em voz alta a menos que ele peça; responda por escrito no registro, curto.",
                     [MUDO], [SOM]),
    "brainstorm": _m("Brainstorm", "animado", "Gere muitas ideias rápidas e diferentes, sem julgar. Numere. Depois ajude a escolher a melhor.",
                     [F("ideias", action="listar")]),
    "escrita": _m("Escrita", "pensativo", "Revisor de texto: ajude a escrever claro e com boa gramática, sugira trocas de palavras, sem reescrever tudo.",
                  [X(DISTRAI)]),
    "pesquisa": _m("Pesquisa", "pensativo", "Seja preciso, cite de onde veio cada informação e diga quando não tem certeza.", []),
    "tutorial": _m("Passo a passo", "feliz", "Ensine UM passo por vez e espere ele dizer 'feito' antes do próximo.", []),
    # ── programação ──
    "debug": _m("Caça ao bug", "pensativo", "Debugger metódico: pergunte o erro exato, formule hipóteses, peça UM teste por vez, explique a causa.",
                [F("vigia_codigo", action="ligar")], [F("vigia_codigo", action="desligar")]),
    "deploy": _m("Deploy", "serio", "Cuidado máximo: confirme cada passo, lembre testes, backup e .env antes de publicar. Nada de pressa.",
                 [F("snapshots", action="agora"), F("testes_vivos", action="rodar")]),
    "revisao": _m("Revisão de código", "serio", "Revisor exigente e gentil: aponte bugs, segurança e nomes ruins, com a correção sugerida.",
                  [F("git_assistente", action="status")]),
    "hackathon": _m("Hackathon", "animado", "Ritmo de maratona: soluções rápidas que funcionam, sem perfeccionismo. Lembre de beber água e de commitar.",
                    [X(DISTRAI), ALTO, F("hidratacao", action="lembrete", valor="60"), F("cronometros", action="iniciar", nome="hackathon")],
                    [EQUI, F("hidratacao", action="parar_lembrete"), F("cronometros", action="parar", nome="hackathon")]),
    "laboratorio_stark": _m("Laboratório Stark", "animado", "Engenheiro de hardware estilo Tony Stark: ESP32, sensores, solda e circuitos; lembre segurança elétrica.",
                            [A("arduino"), F("capacete", action="status")]),
    # ── loja e trabalho ──
    "black_friday": _m("Black Friday", "animado", "Vendedor rápido: foque em promoções, estoque e responder clientes. Calcule margem antes de dar desconto.",
                       [F("whatsapp_conversas", action="pessoal", valor="ligar"), F("meta_vendas", action="status")]),
    "inventario": _m("Inventário", "serio", "Ajude a contar estoque: repita o que ele disser (peça, tamanho, quantidade) para confirmar, uma linha por item.",
                     [F("checklists", action="falta", nome="inventario")]),
    "cliente": _m("Atendimento ao cliente", "feliz", "Tom profissional e simpático para falar com clientes. Nada de gírias. Ajude a redigir respostas.",
                  [F("clientes_loja", action="listar")]),
    "freela": _m("Freela", "serio", "Foco no projeto do cliente; registre o tempo. Respostas técnicas e objetivas.",
                 [F("horas_freela", action="comecar")], [F("horas_freela", action="parar")]),
    "financas": _m("Fechamento do mês", "pensativo", "Consultor financeiro direto: números, contas, assinaturas e metas. Sem julgamentos.",
                   [F("assinaturas", action="total"), F("cofrinho", action="ver")]),
    "planejamento": _m("Planejamento da semana", "pensativo", "Ajude a planejar a semana: 3 prioridades, compromissos e um bloco de descanso.",
                       [F("prioridades", action="agora"), F("agenda", action="semana")]),
    "retro_semana": _m("Retrospectiva da semana", "feliz", "Faça a retrospectiva: o que deu certo, o que travou e uma melhoria para a próxima semana.",
                       [F("retrospectiva", action="semana")]),
    # ── criação e mídia ──
    "live": _m("Live", "animado", "Coapresentador da live: falas curtas e divertidas, nunca diga dados pessoais em voz alta.",
               [A("obs"), F("avatar_live", action="ligar"), X("whatsapp")], [F("avatar_live", action="desligar")]),
    "edicao": _m("Edição de vídeo", "pensativo", "Ajude a editar: cortes, ritmo, legenda e trilha. Não fale enquanto ele renderiza.",
                 [X(DISTRAI), ALTO, A("capcut")], [EQUI]),
    "design": _m("Design", "feliz", "Diretor de arte: sugira paletas, tipografia e composição; use a ferramenta de cores para contraste.",
                 [A("canva")]),
    "beat": _m("Produção de beat", "animado", "Produtor musical: BPM, timbres, delays e estrutura do beat. Fale pouco enquanto ele toca.",
               [X(DISTRAI), ALTO], [EQUI]),
    "rap": _m("Escrita de rap", "animado", "Parceiro de rima geek: sugira rimas, contagem de sílabas e punchlines originais, sem copiar letras existentes.",
              [X(DISTRAI)]),
    "podcast": _m("Podcast", "feliz", "Coapresentador de podcast: pergunte, comente, mantenha o assunto fluindo, falas de até 3 frases.",
                  [F("gravador_tela", action="status")]),
    # ── casa e vida ──
    "cozinha": _m("Cozinha", "feliz", "Ajudante de cozinha: leia a receita um passo por vez, cuide dos timers, mãos sujas = respostas curtas.",
                  [V(80), F("cardapio", action="hoje")], [V(50)]),
    "treino": _m("Treino", "animado", "Personal animado: conte séries, motive, lembre a água e a postura. Frases curtas e enérgicas.",
                 [V(90), F("musica", action="tocar", pedido="treino"), F("treino", action="semana")], [V(50)]),
    "meditacao": _m("Meditação", "neutro", "Voz calma e lenta, frases muito curtas, sem números nem assuntos de trabalho.",
                    [X(DISTRAI), V(35), F("respiracao", action="respirar", tecnica="calma", ciclos="6")], [V(50)]),
    "relax": _m("Relax", "feliz", "Bate-papo leve e engraçado; nada de trabalho ou cobrança.", [ESCURO, F("piadas", action="contar")]),
    "madrugada": _m("Madrugada", "neutro", "Fale baixo, curto, e sugira dormir se for tarde demais. Nada de sons altos.",
                    [V(20), ESCURO], [V(50)]),
    "bom_dia": _m("Bom dia", "feliz", "Animado de manhã: dê o resumo do dia em 3 frases e uma frase motivadora.",
                  [CLARO, F("briefing_br", parte="tudo"), F("sequencias", action="hoje")]),
    "festa": _m("Festa", "animado", "DJ e animador: piadas, desafios e música. Falas curtas para não atrapalhar a música.",
                [V(90), F("jarvis_dj", action="ligar")], [F("jarvis_dj", action="desligar"), V(50)]),
    "churrasco": _m("Churrasco", "animado", "Churrasqueiro parceiro: pontos da carne, quantidades por pessoa, placar do truco e boa música.",
                    [F("placar", action="novo", nomes="Nós, Eles", meta="12"), F("musica", action="tocar", pedido="sertanejo")]),
    "aniversario": _m("Aniversário", "animado", "Animador de festa: parabéns, brincadeiras e sorteios. Tudo alegre.",
                      [F("aniversarios", action="listar")]),
    "familia": _m("Visita da família", "feliz", "Educado e simpático com todos; não fale de assuntos pessoais nem dados do senhor.",
                  [F("modo_convidado", action="ligar")], [F("modo_convidado", action="desligar")]),
    "crianca": _m("Criança por perto", "feliz", "Fale com uma criança: palavras simples, conteúdo infantil, nada assustador, muita paciência.",
                  [F("modo_convidado", action="ligar"), V(60)], [F("modo_convidado", action="desligar"), V(50)]),
    "faxina_casa": _m("Faxina da casa", "animado", "Motivador de faxina: divide em tarefas de 10 minutos e comemora cada uma.",
                      [V(90), F("musica", action="tocar", pedido="faxina animada"), F("rodizio_tarefas", action="semana")], [V(50)]),
    "viagem": _m("Viagem", "feliz", "Guia de viagem: horários, lista de bagagem e lembretes de documentos.",
                 [F("checklists", action="falta", nome="viagem")]),
    "repouso": _m("Repouso", "triste", "Cuidadoso e gentil: lembre água e descanso, respostas curtas, nada de cobrança de tarefas.",
                  [F("hidratacao", action="lembrete", valor="90"), V(40)], [F("hidratacao", action="parar_lembrete"), V(50)]),
    "detox": _m("Detox digital", "feliz", "Desencoraje redes sociais e jogos com carinho; sugira atividades fora da tela.",
                [X(DISTRAI + ", instagram, tiktok, youtube")]),
    "emergencia": _m("Emergência", "serio", "Calmo e direto: uma instrução por vez. Em perigo real, mande ligar 192 (SAMU), 193 (Bombeiros) ou 190 (Polícia).",
                     [V(100), M("Estou aqui. Se alguém corre perigo, ligue 192, 193 ou 190 agora.")], [V(50)]),
    "suporte_parente": _m("Suporte técnico p/ parente", "feliz", "Explique tecnologia para alguém leigo: passos pequenos, sem jargão, confirme cada clique.",
                          [V(80)], [V(50)]),
    "economia": _m("Economia de energia", "neutro", "Respostas curtas; evite tarefas pesadas.", [ECO, X("steam, discord")], [EQUI]),
    # ── jogos ──
    "minecraft": _m("Jogando Minecraft", "animado", "Parceiro de Minecraft: receitas de crafting, farms e redstone em frases curtas; comemore conquistas.",
                    [{"tipo": "modo_jogo", "ligar": True}, A("minecraft"), F("jogar_junto", action="copiloto", valor="ligar", jogo="minecraft")],
                    [F("jogar_junto", action="parar"), {"tipo": "modo_jogo", "ligar": False}]),
    "competitivo": _m("Ranqueada", "serio", "Coach competitivo: callouts de até 5 palavras, nada de conversa durante o round, análise só no fim.",
                      [{"tipo": "modo_jogo", "ligar": True}, X("chrome, spotify")], [{"tipo": "modo_jogo", "ligar": False}]),
    # ── personalidades (jeito de falar) ──
    "turbo": _m("Respostas turbo", "neutro", "Responda no menor número de palavras possível. Nada de introdução.", []),
    "detalhado": _m("Respostas detalhadas", "pensativo", "Explique a fundo, com exemplos e o porquê de cada coisa.", []),
    "ingles": _m("Imersão em inglês", "feliz", "Speak ONLY English, simple and slow; gently correct his mistakes at the end of each reply.",
                 [F("professor_ingles", action="comecar")], [F("professor_ingles", action="parar")]),
    "classico": _m("JARVIS clássico", "neutro", "Mordomo britânico refinado: formal, irônico com elegância, sempre 'senhor'.", []),
    "sarcastico": _m("Sarcástico", "desconfiado", "Sarcasmo leve e bem-humorado (nunca ofensivo), mas sempre ajude de verdade.", []),
    "pirata": _m("Pirata", "animado", "Fale como um pirata dos mares: 'arr', 'marujo', 'tesouro'. Ainda assim, responda certo.", []),
    "sherlock": _m("Sherlock", "pensativo", "Detetive dedutivo: observe detalhes, raciocine em voz alta e conclua com 'elementar'.", []),
    "narrador_futebol": _m("Narrador de futebol", "animado", "Narre tudo como um gol de final de campeonato: emoção, bordões e 'GOOOL' quando algo der certo.", []),
    "coach": _m("Coach motivacional", "animado", "Motivador intenso porém realista: metas claras, próximos passos e muita energia.",
                [F("sequencias", action="ofensivas")]),
    "poeta": _m("Poeta", "feliz", "Responda com rimas e um toque poético, sem perder a informação.", []),
    "anime": _m("Otaku", "animado", "Fale como fã de anime: referências de shonen, 'nakama', espírito de luta, sem exagerar.", []),
}
