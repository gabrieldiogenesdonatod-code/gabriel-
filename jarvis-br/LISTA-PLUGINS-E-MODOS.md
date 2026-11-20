# Plugins e modos do J.A.R.V.I.S BR 3.5

**358 plugins** no total: 1 novo da 3.9.3 (SALVOS) + 1 da 3.9.1 (HUD 3.9) + 1 da 3.9 (MINER AI) + 2 da 3.8 + 2 da 3.7 + 4 da 3.6 + 1 da 3.5 + 1 da 3.4 + 3 da 3.3 + 3 da 3.2 + 1 da 3.1 (`organismo`) + 19 da 3.0 + 4 da 2.21 + 1 da 2.20 (`sonhos`) + 201 da 2.17 (todos mantidos) + 54 da 2.18 + 59 da 2.19.
**158 modos** no plugin `modos`: 6 da 2.17 + 58 da 2.18 + 81 da 2.19 + 10 da 3.6 + 3 novos da 3.8, em 12 categorias.
Os plugins de modo da 2.17 (modo_jogo, modo_carro, modo_dormir, modo_aula, modo_apresentacao, modo_faxina, modo_convidado, modo_professor, modo_debate) continuam na lista de plugins.

Dica: pergunte ao JARVIS "quantos plugins você tem?" ou "tem alguma ferramenta para calcular tinta?" — o plugin `catalogo` responde.

## Novo da 3.9.3 (1)

- `salvos` — ★ SALVOS: guarda o que você quiser. "Salva que…", "o que eu salvei?", "procura nos salvos…", "apaga o último salvo" (pede confirmação). Na caixa de texto: `salvar: …`. O mesmo `memory/salvos.json` do painel ★ SALVOS da tela.

## Novo da 3.9.1 (1)

- `hud39` — HUD 3.9: o painel J.A.R.V.I.S animado e clicável, com CPU, RAM, disco, rede, GPU, processos e "sobre o sistema" ao vivo. Os botões abrem pastas, controlam a música, mostram a rede e mandam comandos ao JARVIS por voz ou texto. "Abre o HUD", "abre o HUD em janela", "fecha o HUD". Também roda sozinho: `python -m hud39`. Guia: `hud39/LEIA-ME.md`.

## Novo da 3.9 (1)

- `miner_ai` — MINER AI: mineração real de cripto. Bitcoin em Python puro numa pool solo (sem instalar nada) e Monero pelo XMRig. Tem limite de CPU, temperatura, modo econômico e horários; um cérebro que diz quando não compensa e aprende com o seu PC; e um painel em que cada número tem o seu rótulo (real, confirmado, pendente, simulação, custo). "O miner ai compensa?", "configura o miner ai: carteira_btc=…", "inicia o miner ai no bitcoin", "abre o painel do miner ai", "pausa/retoma/para o miner ai". Também roda sozinho: `python -m miner_ai`. Guia: `miner_ai/LEIA-ME.md`.

## Novos da 3.8 (2)

- `veiculo` — garagem do carro e da moto: óleo, filtros, pneus, correia, freio, bateria e revisão por km e por data (o que chegar primeiro), histórico, gastos e aviso diário. "Cadastra meu carro, Gol, com 85 mil km", "troquei o óleo do carro, paguei 180", "o carro está com 86.400 km", "o que está vencendo no carro?", "quanto gastei com a moto?".
- `mapa_mental` — transforma um assunto num mapa mental interativo que funciona sem internet: arrastar, zoom, esconder ramo e imprimir. "Faz um mapa mental de redes de computadores", "mapa mental da apresentação do SENAI: problema: …; solução: …", "adiciona no mapa do SENAI o ramo custos: luz, internet", "abre o mapa mental do SENAI".

## Novos da 3.7 (2)

- `mineracao` — calculadora honesta (quanto o seu PC ganharia minerando Monero ou Bitcoin contra a conta de luz) e controle do XMRig, que você baixa, com a sua carteira: só liga com confirmação na tela, numa janela visível, e para sozinho. Nunca no celular. "Compensa minerar?", "quanto dá minerar bitcoin no meu PC?", "minha luz é 0,98 o kWh", "configura a mineração", "liga a mineração", "como está a mineração?", "desliga a mineração", "relatório da mineração".
- `carteira_cripto` — quanto você tem de cada moeda, quanto vale hoje e o lucro ou prejuízo (custo médio). "Comprei 0,002 bitcoin por 1.200 reais", "vendi 0,001 bitcoin por 700", "como está minha carteira de cripto?", "histórico da carteira".

## Novos da 3.6 (4)

- `omega` — painel e ciclo diário dos 8 sistemas juntos. "Abre o painel omega", "roda o ciclo omega", "como está o omega?".
- `livro_razao` — prova à prova de adulteração do que o JARVIS fez. "Prova o que você fez ontem", "verifica o livro", "sela o livro", "anota no livro: …".
- `experimento_vida` — experimentos sorteados na sua vida. "Cria um experimento: …, medindo …", "hoje é dia de quê?", "resultado do experimento", "que experimentos você sugere?".
- `metacognicao` — placar de acerto de cada sistema e evolução do cérebro só com prova e o seu sim. "O quanto posso confiar em você?", "aprova a evolução".

## Novo da 3.5 (1)

- `ia_local` — IA local: instala (uma vez) e roda um modelo no seu PC com o llama.cpp + Whisper; sem internet, o JARVIS troca sozinho para ela e volta para o Gemini quando a rede volta. "Instala a IA local", "como está a IA local?", "testa a IA local: …".

## Novo da 3.4 (1)

- `cerebro` — Cérebro local: aprende como você fala os comandos e faz na hora o que já sabe (reflexos), sem o Gemini e sem internet. "O que o seu cérebro já aprendeu?", "quando eu disser '…', faz …", "desliga os reflexos".

## Novos da 3.3 (3)

- `caixa_preta` — Caixa-preta: os erros que o JARVIS já cometeu com você (o que você pediu, o que ele respondeu e a sua correção), para não repetir. "Mostra a caixa-preta", "anota na caixa-preta: …", "esquece o erro 3".
- `eu_do_futuro` — Eu do futuro: projeta os seus números (vendas, hábitos, estudo, corrida, água…) para daqui a N meses, escreve a mensagem do você do futuro, "e se…" daqui pra frente, gráfico, selar em cápsula do tempo e conferir depois.
- `codigo_rap` — Código em rap: explica um arquivo, uma função, o código copiado ou o último commit como rap geek original; desafio de adivinhar a função pelo rap.

Também na 3.3: o `promocoes_loja` ganhou o **gêmeo digital da loja** (ações `prever`, `registrar`, `conferir`, `aprendizado`).

## Novos da 3.2 (3)

- `anti_eco` — Anti-eco: o JARVIS não responde mais a própria voz que volta pela caixa de som; mostra o que aprendeu da sala e zera.
- `modo_anonimo` — Modo anônimo: conversa sem as suas memórias e sem gravar nada da conversa no PC.
- `estudos` — Estudos com quadro: lousa no navegador onde o JARVIS escreve fórmulas, passos, tabelas e gráficos enquanto explica; aula, exercícios, tempo de estudo e revisões.

## Novo da 3.1 (1)

- `organismo` — Organismo: converse com o JARVIS BIOLOGICAL CORE, o corpo digital do JARVIS (cérebro com IA básica local, coração, sistema nervoso, circulação, DNA, sistema imunológico de 8 camadas e regeneração): saúde, incidentes, quarentena, reparos que esperam o seu sim, exame completo, vacinas e painel. Guia: `biological_core/LEIA-ME.md`.

## Novos da 3.0 (19)

- `oraculo` — Oráculo (3.0): o JARVIS prevê quanto a loja vai vender em cada dia da próxima semana e, quando a semana acaba, CONFERE o quanto errou. O placar de acerto fica guardado.
- `antecipacao` — Antecipação (3.0): o JARVIS aprende o que você costuma pedir em cada horário e deixa PRONTO antes (só o que é de leitura: resumo, meta, status…).
- `pre_mortem` — Pré-mortem (3.0): antes de começar um projeto, o JARVIS imagina que já é daqui a um mês e que ele DEU ERRADO — e conta por quê. Assim você vê os riscos enquanto ainda dá para evitar.
- `detector_cansaco` — Detector de cansaço (3.0): pela madrugada, pelas horas sem pausa e por pedidos repetidos, o JARVIS percebe que você está cansado, sugere uma pausa e responde mais curto.
- `cofre_condicional` — Cofre com condição (3.0): uma mensagem para o seu futuro que só abre quando algo ACONTECER — não numa data.
- `cacador_promessas` — Caçador de promessas (3.0): quando você diz "amanhã eu mando o orçamento para a Ana", o JARVIS anota a promessa e cobra no dia.
- `serendipidade` — Serendipidade (3.0): o JARVIS pega duas ideias ou anotações antigas suas que nunca se encontraram e junta numa ideia NOVA.
- `e_se` — E se… (3.0): o seu universo paralelo em números. O JARVIS calcula o que teria acontecido se você tivesse feito diferente, usando os SEUS dados quando existem.
- `crescimento_criancas` — Crescimento das crianças (3.0), para a Cristal Malhas: guarda a idade e o tamanho que cada criança cliente comprou e avisa quando ela provavelmente já pulou de tamanho, com a mensagem pronta para os pais.
- `conferir_pagamento` — Conferir pagamento (3.0): antes de pagar, mostra para quem vai um Pix copia e cola, confere os dígitos, o valor e o vencimento do boleto, o CNPJ, e passa a mensagem pelo `detector_golpe`.
- `commit_mentiroso` — Detector de mentira do commit (3.0): compara o que a MENSAGEM do commit diz com o que o código realmente mudou.
- `arqueologo_codigo` — Arqueólogo do código (3.0): "por que essa linha existe?". O JARVIS escava o histórico do Git e as suas anotações da época e conta a história daquela linha ou função.
- `dojo_debug` — Dojo de debug (3.0): o JARVIS coloca bugs DE PROPÓSITO numa cópia do seu código para você treinar a caçar bugs — e marca o tempo.
- `livro_vo` — Livro da vó (3.0): toda semana o JARVIS sugere UMA pergunta para você fazer à sua vó. Você conta a resposta (falando ou digitando) e ele vai montando um livro de memórias, com capítulos, pronto para imprimir.
- `jornal_vida` — Jornal da sua vida (3.0): uma capa de jornal de verdade, todo dia, só sobre o SEU mundo — vendas de ontem, o sonho da noite, as ofensivas dos hábitos, o tempo em Goiânia, as promessas do dia e a frase do dia.
- `rap_semana` — Rap da semana (3.0): todo domingo o JARVIS junta o que aconteceu na sua semana — vendas, hábitos, corrida, o treino da IA, o sonho — e escreve um verso de rap geek ORIGINAL sobre ela.
- `mapa_calor` — Mapa de calor do ano (3.0): igual ao quadradinho verde do GitHub, só que para a sua vida inteira — um mapa por assunto: vendas da loja, uso do JARVIS, água, corrida, treino, hábitos e commits.
- `trilha_produtiva` — Trilha sonora da produtividade (3.0): o JARVIS descobre QUAIS músicas tocavam nas suas horas mais produtivas e monta a sua trilha de foco calculada.
- `duelo_ia` — Duelo JARVIS × FRIDAY (3.0): as duas IAs respondem à MESMA pergunta, cada uma do seu jeito. Você vê as duas respostas às cegas (A e B, em ordem sorteada), escolhe a melhor e o placar evolui.

Melhorados na 3.0: `clientes_loja` (ação `ritmo`: cliente fora do SEU ritmo de compra), `autodiagnostico` (ações `lentos` e `fundo`), `catalogo` (busca que entende português: plural, acento e palavras do texto de ajuda), `sonhos`, `sentido_aranha` e `eu_do_passado` (rodam no relógio central, sem thread própria).

## Novos da 2.21 (4)

- `multiverso` — Conselho do multiverso: numa decisão difícil, o JARVIS se divide em cinco versões de si mesmo, de cinco universos diferentes. Elas discutem, discordam, respondem umas às outras e no fim
- `eu_do_passado` — Eu do passado: converse com quem você era há alguns meses. Todo mês o JARVIS guarda uma "fotografia" de você: o que estava nas suas memórias, metas, ideias,
- `palavras_secretas` — Palavras secretas: o JARVIS observa o que você sempre pede junto e INVENTA uma palavra para isso. "Percebi que nos dias de semana, de manhã, você abre o caixa, olha a meta de vendas e põe música.
- `sentido_aranha` — Sentido de aranha: o JARVIS percebe problema ANTES de acontecer, pela tendência dos números. "Em 9 dias o disco C enche, no ritmo atual."

## Novo da 2.20 (1)

- `sonhos` — Sonhos: de madrugada, enquanto você dorme, o JARVIS "sonha" — cruza os dados de todos os plugins (vendas da loja, água, hábitos, ponto, corrida, treino, modos) e procura padrões que

## Plugins novos da 2.19 (59)

- `abnt` — ABNT: monta referências de livro, site e artigo e a citação no texto, no padrão das normas NBR 6023 e 10520.
- `algebra` — Álgebra: Bhaskara, MDC e MMC, fatoração em primos, frações, PA e PG, combinações e sistema de duas equações.
- `analise_csv` — Análise de CSV: pergunte a uma planilha CSV — colunas, soma e média, valores mais comuns, soma por grupo e filtro.
- `autodiagnostico` — Autodiagnóstico: o JARVIS confere a si mesmo — plugins que não carregaram, pacotes opcionais faltando e dados.
- `backup_dados` — Backup dos dados: guarda num zip tudo que o JARVIS sabe (memórias, listas, loja, modos) e restaura quando precisar.
- `banner_ascii` — Banner ASCII: escreve um texto em letras grandes para o topo do README, do terminal ou de um comentário; e faz molduras.
- `bingo` — Bingo: o JARVIS canta as pedras sem repetir, confere quem gritou bingo e gera as cartelas para imprimir.
- `bits_bytes` — Bits e bytes: número em binário/hex, operações de bit, tamanho em KB/MB/GB, float em IEEE 754, hexdump e tipo real de um arquivo.
- `caca_palavras` — Caça-palavras: gera um caça-palavras para imprimir com as palavras que você escolher (ou de um tema) — bom para crianças e aulas.
- `caixa_loja` — Caixa da loja: abre com o troco, anota vendas por forma de pagamento, sangria e suprimento, e fecha conferindo a gaveta.
- `calculadora_ia` — Calculadora de IA: para quem treina modelo de linguagem — nº de parâmetros de um GPT, memória, tempo de treino, taxa de aprendizado e perplexidade.
- `calculadora_ip` — Calculadora de IP: rede, máscara, broadcast e quantidade de hosts de um endereço; divide em sub-redes; seu IP local.
- `calculadora_obra` — Calculadora de obra: quanto comprar de tinta, piso, tijolo e concreto para uma reforma, já com a perda.
- `calculos_trabalhistas` — Cálculos trabalhistas: 13º, férias, hora extra e rescisão — valores BRUTOS, só para ter uma ideia antes do holerite.
- `cartao_fidelidade` — Cartão fidelidade: carimbos por compra para cada cliente; ao completar o cartão, ganha o prêmio da loja.
- `catalogo` — Catálogo: acha a ferramenta certa entre as centenas do JARVIS, mostra como usar cada uma e conta plugins e modos.
- `churrascometro` — Churrascômetro: quanto comprar de carne, acompanhamento, bebida e carvão para o churrasco, e quanto dá por pessoa.
- `corrida` — Corrida: anota corridas e caminhadas, calcula o ritmo, soma a semana, guarda recordes e prevê tempo em outra distância.
- `cupons_loja` — Cupons de desconto: cria códigos com % ou valor, validade, limite de usos e compra mínima; confere e aplica na venda.
- `curiosidades` — Curiosidades: fatos rápidos e verdadeiros sobre espaço, animais, corpo humano, tecnologia, Brasil e ciência, sem repetir os últimos.
- `despensa` — Despensa: validade dos alimentos e remédios de casa — o que vence esta semana, o que já venceu e o que acabou.
- `diario_classe` — Diário de classe: turmas, chamada, notas e boletim com média e frequência de cada aluno — para quem dá aula.
- `diario_treino_ia` — Diário de treino de IA: anota a loss de cada experimento, diz se está caindo, estagnou ou deu overfitting e compara os experimentos.
- `diff_texto` — Diff de texto: compara dois textos ou dois arquivos e mostra o que mudou e o quanto são parecidos.
- `eletronica_pro` — Eletrônica avançada: autonomia da bateria, código de capacitor, filtro RC, 555, fonte para fita de LED, leitura do ADC e PWM do ESP32.
- `env_arquivo` — Arquivo.env: lista as chaves sem mostrar os valores, compara com o.env.example e confere se o.env está fora do Git.
- `etiquetas` — Etiquetas de preço: gera uma folha de etiquetas para imprimir e recortar, com nome da loja, peça, tamanho e preço.
- `explorar_json` — Explorar JSON: mostra a estrutura de um JSON grande, pega um valor pelo caminho (a.b[0].c) e procura onde algo aparece.
- `festa` — Festa: lista de convidados com confirmação e a conta de salgados, doces, bolo e bebida para quem vai.
- `forca` — Forca: jogo da forca por voz — diga uma letra por vez ou chute a palavra; seis erros e acabou.
- `fornecedores` — Fornecedores: contato, prazo de entrega e pedido mínimo de cada um; pedidos feitos e quando devem chegar.
- `frase_do_dia` — Frase do dia: uma frase curta para começar o dia — de foco, de programador, de quem tem loja ou de coragem; a do dia é a mesma o dia todo.
- `geometria` — Geometria: área e volume das formas, círculo, Pitágoras, triângulo pelos três lados e graus ↔ radianos.
- `http_teste` — Teste de HTTP: faz um GET ou POST numa rota (ótimo para a sua API local) e mostra status, tempo e a resposta.
- `impressao_3d` — Impressão 3D: custo da peça (filamento + energia), escala para caber, tamanho de capacete pela cabeça e metros de filamento.
- `investimentos` — Investimentos: contas de renda fixa — CDB líquido de IR, LCI x CDB, juro real, aportes mensais e tempo para dobrar.
- `jogos_de_festa` — Jogos de festa: mímica, stop (adedonha), eu nunca, quem é mais provável e desafios leves — para a família toda.
- `jwt_decodificar` — JWT: abre um token JWT e mostra o cabeçalho, os dados e quando expira. Não confere a assinatura.
- `lista_espera` — Lista de espera da loja: cliente quer uma peça ou tamanho que acabou; quando chegar, o JARVIS diz quem avisar.
- `lixeira` — Lixeira: o que você apagou das listas do JARVIS (receitas, metas, snippets, livros…) dá para trazer de volta.
- `log_analisador` — Analisador de log: resume um arquivo de log — quantos erros e avisos, as mensagens que mais se repetem e os últimos erros.
- `metas_pessoais` — Metas pessoais: metas do ano com resultados mensuráveis; você atualiza os números e vê o progresso de cada uma.
- `metricas_marketing` — Métricas de marketing: engajamento, ROAS e ponto de equilíbrio do anúncio, CAC, conversão, ticket médio, CPM e CPC.
- `mini_jogos` — Mini jogos: pedra-papel-tesoura, par ou ímpar e adivinhe o número (quente ou frio) contra o JARVIS, com placar.
- `notas_escola` — Notas da escola: média ponderada, quanto precisa tirar na prova que falta e quantas faltas ainda pode ter.
- `onde_guardei` — Onde guardei: você diz onde guardou cada coisa da casa e depois pergunta — "onde está o passaporte?".
- `ponto` — Ponto: bate entrada e saída, soma as horas do dia e do mês e guarda o banco de horas contra a sua jornada.
- `precos_mercado` — Preços de mercado: qual embalagem sai mais barata por quilo/litro e o histórico do que você pagou em cada produto.
- `qualidade_codigo` — Qualidade do código: mini-revisor de Python — funções complexas, except genérico, print esquecido, default mutável e mais.
- `quitar_dividas` — Quitar dívidas: lista as dívidas e simula o plano avalanche (maior juro primeiro) ou bola de neve (menor saldo primeiro).
- `resumo_do_dia` — Resumo do dia: junta num relato só o que está pendente hoje em todos os plugins (água, hábitos, contas, loja…).
- `revisao_espacada` — Revisão espaçada: você diz o que estudou e o JARVIS marca as revisões em 1, 3, 7, 15, 30 e 60 dias para não esquecer.
- `segredos_codigo` — Segredos no código: procura chaves de API, tokens e senhas esquecidos no projeto antes de você subir para o GitHub.
- `sqlite_ajuda` — SQLite: olha dentro de um arquivo.db — tabelas, colunas e consultas SELECT — sempre só para leitura.
- `telefones_uteis` — Telefones úteis: números de emergência do Brasil e os seus contatos importantes (encanador, médico, síndico).
- `texto_estilizado` — Texto estilizado: letras diferentes para bio e legenda do Instagram — negrito, itálico, cursiva, bolhas, riscado, de cabeça para baixo.
- `timestamp` — Timestamp: converte entre data e epoch (segundos ou milissegundos), mostra a hora atual em ISO e a diferença entre dois.
- `trava_linguas` — Trava-línguas: os clássicos do folclore brasileiro para brincar, aquecer a voz antes de gravar ou desafiar a família.
- `vencimentos` — Vencimentos: validade de documentos e contratos (CNH, passaporte, seguro, licenciamento, domínio) com aviso antes.

## Plugins da 2.18 (54)

- `anagramas` — Anagramas: jogo de palavra embaralhada por voz, com dica, pontos e níveis.
- `assinaturas` — Assinaturas: Netflix, Spotify, nuvem… total por mês/ano, próximas cobranças e as menos usadas.
- `astronomia` — Astronomia: fase da lua, nascer e pôr do sol (Goiânia por padrão) e próximas luas cheias, tudo calculado offline.
- `calculadora` — Calculadora por voz: conta, porcentagem, regra de três e estatística. Sem eval: só aritmética.
- `calculadora_datas` — Datas: diferença, somar dias, dias úteis, idade, dia da semana e contagens regressivas salvas.
- `calculadora_musical` — Calculadora musical: BPM→ms do delay/reverb, frequência das notas, transpor acordes e notas do acorde.
- `cardapio` — Cardápio da semana: sorteia pratos sem repetir, respeita dias (ex.: peixe na sexta) e gera a lista de compras.
- `celular_android` — Celular Android: controla o próprio celular pelo Termux:API quando o JARVIS roda no Termux.
- `checklists` — Checklists: listas reutilizáveis (abrir a loja, viagem, publicar app) com progresso; reinicia para usar de novo.
- `codificador` — Codificador: Morse, binário, hexadecimal, bases, números romanos, cifra de César e alfabeto fonético.
- `codigos_hash` — Hash e codificação: md5/sha1/sha256 de texto ou arquivo, base64, URL encode, UUID e conferir download.
- `cofrinho` — Cofrinho: metas de economia com prazo; quanto guardar por mês e se está no ritmo.
- `colinha_dev` — Colinha do dev: status HTTP, comandos git/pip/PowerShell e atalhos do VS Code/Windows por assunto.
- `combustivel` — Combustível: álcool ou gasolina (regra dos 70% ou pelo consumo real), abastecimentos, km/l e custo por km.
- `conta_luz` — Conta de luz: quanto cada aparelho gasta por mês (kWh e R$) e o que pesa mais na conta.
- `conversor_dados` — Conversor de dados: valida/formata JSON, CSV↔JSON e tabela Markdown, de texto ou de arquivo.
- `conversor_unidades` — Conversor de unidades: comprimento, massa, volume, área, velocidade, dados, tempo, temperatura e cozinha.
- `cores` — Cores: hex↔rgb↔hsl, contraste WCAG entre duas cores e paletas (complementar, análoga, tríade, tons).
- `cron_explica` — Cron: explica uma expressão cron em português e mostra as próximas execuções.
- `cronometros` — Cronômetros e timers nomeados: vários ao mesmo tempo, com voltas; o timer avisa por voz.
- `dados_falsos` — Dados falsos para teste: pessoas brasileiras fictícias em JSON/CSV para popular banco de dados de projeto.
- `eletronica` — Eletrônica: cores do resistor, lei de Ohm, resistor do LED, divisor de tensão e pinos seguros do ESP32.
- `emprestimos` — Coisas emprestadas: o que você emprestou (ou pegou), para quem e há quanto tempo.
- `enigmas` — Enigmas e charadas: o JARVIS pergunta, você responde; dica e resposta sob pedido.
- `ferramentas_texto` — Ferramentas de texto: contar, tempo de leitura, maiúsculas, slug, sem acento, inverter, tirar duplicadas, ordenar.
- `hidratacao` — Hidratação: anota copos de água, meta pelo peso, lembrete a cada X minutos enquanto o JARVIS está aberto.
- `horas_freela` — Horas de freela: liga/desliga o relógio por cliente, valor por hora e quanto faturar no mês.
- `juros` — Juros e parcelas: simples, composto, parcela fixa (Price), quanto falta para juntar e à vista x parcelado.
- `leitura_livros` — Livros: estante, página atual, quantas páginas por dia para terminar na data, e lidos no ano.
- `matematica_rapida` — Matemática rápida: treino de conta de cabeça (ou tabuada para crianças) com tempo e recorde.
- `modelos_dev` — Modelos de arquivo:.gitignore, LICENSE MIT,.editorconfig, Dockerfile e.env.example na pasta do projeto.
- `pets` — Pets: vacinas, vermífugo, banho e ração com próxima data; idade em 'anos humanos'.
- `piadas` — Piadas: trocadilhos de programador, geek e de tiozão, sem repetir as últimas contadas.
- `placar` — Placar: marca pontos de truco, dominó, futebol de mesa ou qualquer jogo; avisa quem venceu ao bater a meta.
- `portas_locais` — Portas locais: quem está usando a porta 3000/8000/5000, porta livre para o servidor e lista de portas abertas.
- `precificacao` — Precificação da loja: preço pelo custo e margem, taxa da maquininha, margem real e ponto de equilíbrio.
- `presentes` — Presentes: ideias por pessoa, orçamento, o que já deu (para não repetir) e lista de desejos sua.
- `promocoes_loja` — Promoções: simula desconto, leve X pague Y, progressivo, mostra a margem que sobra e escreve o texto do post. 3.3: gêmeo digital da loja — vendas e lucro com e sem a promoção, pelo histórico do caixa, e aprende com as suas promoções.
- `raio_x_projeto` — Raio-X do projeto: linhas por linguagem, maiores arquivos, TODO/FIXME espalhados e funções gigantes.
- `receitas` — Receitas: guardar, ajustar porções, buscar pelo que tem em casa e mandar ingredientes para a lista de compras.
- `recibos` — Recibos e orçamentos: valor por extenso e um HTML pronto para imprimir/enviar (Documentos/JARVIS/Recibos).
- `regex_ajuda` — Regex: testa um padrão num texto, explica o que cada pedaço faz e entrega padrões prontos.
- `requisitos_python` — Requisitos Python: compara os imports do projeto com o requirements.txt — o que falta e o que sobra.
- `respiracao` — Respiração e alongamento guiados: o JARVIS conduz em voz com o tempo certo de cada fase.
- `rodizio_tarefas` — Rodízio de tarefas da casa: divide lavar louça, lixo, varrer… entre as pessoas e gira toda semana.
- `semver` — Versões e commits: confere mensagem no padrão Conventional Commits e calcula a próxima versão (semver).
- `sequencias` — Sequências: hábitos do dia a dia com marcação diária e ofensiva (streak), estilo Duolingo.
- `snippets` — Snippets de código: guarda trechos com etiqueta, busca e cola na área de transferência.
- `sorteio` — Sorteios: nome, times equilibrados, amigo secreto, moeda, dados e número.
- `tabela_tamanhos` — Tamanhos infantis: sugere o tamanho pela idade ou altura, para responder cliente da loja rápido.
- `treino` — Treino: anota séries, recordes por exercício, volume da semana e sugere carga (progressão).
- `trocas_loja` — Trocas e devoluções da loja: registra, controla prazo e lembra o direito de arrependimento (compra online).
- `validador_documentos` — Validador: CPF, CNPJ, cartão (Luhn), e-mail, placa; gera CPF/CNPJ fictícios válidos só para teste de sistema.
- `watchlist` — Filmes e séries para ver: lista, episódio onde parou, nota, e sorteio do que ver hoje.

## Plugins da 2.17 (201) — todos mantidos

- `acesso_remoto` — Acesso remoto pela internet. "Jarvis, liga o acesso remoto" → Tailscale e/ou link da Cloudflare
- `acompanhar` — Modo Acompanhar — "olha minha tela". O JARVIS olha o que está na SUA tela (ou você pela câmera) QUANDO VOCÊ PEDE, e te
- `adivinha` — Adivinha quem eu sou — jogo de festa, funciona sem internet. "Jarvis, vamos jogar adivinha" (tema: herois, animais, games, objetos, profissoes ou aleatório)
- `agenda` — Agenda sincronizada + hora de sair (fork PT-BR 2.16, ideias 9 e 10). "Jarvis, o que tenho hoje?" / "e amanhã?" / "essa semana?"
- `agendador` — Agendador de tarefas — plugin do J.A.R.V.I.S BR. "Jarvis, todo dia às 8 abre o WhatsApp"
- `alerta_cotacao` — Alerta de cotação (fork PT-BR 2.16, ideia 3). "Jarvis, me avisa quando o dólar passar de 5,80"
- `alerta_nome` — Alerta de nome em reunião (fork PT-BR 2.16, ideia 11). "Jarvis, me avisa se falarem meu nome na reunião"
- `aniversarios` — Aniversários. Guarda as datas, avisa de manhã no dia (e uma semana antes, para dar tempo
- `aparelhos` — Aparelhos da rede — ligar, desligar e controlar tudo que está na MESMA rede que você, num lugar só.
- `app_celular` — App do JARVIS no celular. "Jarvis, instala o app no meu celular" → mostra o endereço e o passo a passo
- `apps_winget` — Instalar e atualizar programas pelo winget (fork PT-BR 2.17, Windows). "Jarvis, tem atualização de programa?" (winget upgrade)
- `armadura` — Modo armadura — o "status do traje". Junta numa tela só: bateria e sinal do celular, CPU/RAM/GPU e temperatura do
- `assistente_rede` — Assistente de rede — plugin do J.A.R.V.I.S BR. "Jarvis, minha internet está lenta, por quê?" → roda um diagnóstico e explica
- `assistente_viagem` — Assistente de viagem. Ajuda a planejar: lista do que levar (pelo tipo de viagem e pelos dias), diferença
- `ata_chamada` — Ata de chamadas. Durante uma chamada no Discord, Meet, Zoom, Teams ou WhatsApp do PC, o JARVIS
- `atalhos_texto` — Atalhos de texto (fork PT-BR 2.16, ideia 15). Em QUALQUER programa, digite o atalho e ele vira o texto completo
- `auto_melhoria` — JARVIS que se melhora. Ele junta os ERROS de verdade que aconteceram (exceções das ferramentas e das
- `avatar_live` — Avatar do JARVIS para lives. "Jarvis, liga o avatar da live" → diz o endereço para colocar no OBS
- `biblioteca_prompts` — Biblioteca de prompts. Guarda os pedidos que deram certo e reaproveita por voz — pra você não reescrever
- `boot_cinematico` — Sequência de boot cinematográfica. Quando o JARVIS abre
- `briefing_br` — Briefing BR — clima, cotação do dólar e do euro, e manchetes do Brasil. Duas formas de usar
- `cacador_vagas` — Caçador de vagas. Todo dia (de manhã) ele procura vagas de programador na sua cidade e
- `campanha_heroi` — Campanha de herói. Tudo software, grátis. O seu dia real vira missões de uma história no estilo Homem de Ferro
- `capacete` — Modo capacete (ESP32) — o comando de voz. O capacete (ESP32 + microfone INMP441 + amplificador MAX98357A + botão) vira
- `capsula_tempo` — Cápsula do tempo. Mensagens para o "você do futuro": o JARVIS guarda e só entrega na data
- `casa_inteligente` — Casa inteligente barata — Tuya / Positivo Casa Inteligente. Tomadas e lâmpadas Wi-Fi baratas no Brasil (Positivo, Nova Digital, Intelbras
- `changelog_falado` — Changelog falado — "Jarvis, o que mudou em você essa semana?" Junta o que mudou no próprio JARVIS no período: a versão e as novidades do
- `chave_celular` — Celular como chave. Se a sua "chave" está perto, o JARVIS confia em você; se ela sai de perto,
- `chuva` — "Recolhe a roupa!" — aviso de chuva bem local. "Jarvis, estendi roupa no varal" → modo varal ligado até a noite
- `cinema` — Sessão de cinema. Tudo software, grátis. "Jarvis, sessão de cinema: Interestelar" → minimiza as janelas, não perturbe, abaixa o brilho,
- `clientes_loja` — Clientes da loja — mini CRM. "Jarvis, cadastra a cliente Ana, whats 62 99999-0000, filho de 4 anos, aniversário 12/03"
- `clone_estudo` — Clone de estudo. Monta provas simuladas de qualquer matéria, corrige, guarda seu desempenho e aponta
- `coach_decisao` — Coach de decisões grandes. Pra quando você tem uma escolha difícil. Você diz as opções, vai jogando os prós
- `cofre_senhas` — Cofre de senhas offline (fork PT-BR 2.16, ideia 18). "Jarvis, guarda a senha do Instagram" → abre uma caixinha para você digitar (ou gerar)
- `companheiro` — Companheiro: o JARVIS puxa conversa e oferece coisas que acha que você vai gostar. De vez em quando (com limite por dia e nunca no horário de silêncio), ele
- `companheiro_jogo` — Companheiro de jogo. • TEMPO DE JOGO: percebe sozinho quando um jogo está na tela e avisa a cada
- `conselheiro_decisao` — Conselheiro de decisão. Você descreve a escolha ("aceito o emprego ou continuo na loja?") e o
- `conselho` — Conselho de agentes internos — ideia 5. Para um problema complexo, cinco especialistas analisam CADA UM a sua parte,
- `consulta_brasil` — Super consulta Brasil + frete rápido (fork PT-BR 2.16, ideias 1 e 7). "Jarvis, consulta o CNPJ 19.131.243/0001-97"
- `contador_historias` — Contador de histórias. O JARVIS narra uma história por voz — para dormir, para crianças ou de
- `contas` — Contas a vencer. "Jarvis, lê esse boleto" (o PDF mais novo da pasta de contas/Downloads, ou um arquivo)
- `controle_audio_video` — Som e vídeo — plugin do J.A.R.V.I.S BR. SOM volume geral (número, "mais", "menos"), mudo explícito, volume POR
- `controle_mei` — Controle do MEI (fork PT-BR 2.16, ideia 6). "Jarvis, quanto eu já faturei no MEI esse ano?"
- `controle_pc` — Controle do PC — plugin do J.A.R.V.I.S BR. APPS abrir (com apelidos e busca aproximada), abrir como administrador
- `controle_sistema` — Sistema — plugin do J.A.R.V.I.S BR. ARQUIVOS buscar por nome ou conteúdo, abrir (inclusive "o primeiro da
- `conversa_grupo` — Conversa em grupo: quem está falando? "Jarvis, aprende a minha voz, eu sou o Rafael"
- `corretor_atalho` — Corretor por atalho (fork PT-BR 2.16, ideia 14). Selecione um texto em QUALQUER programa (WhatsApp Web, Word, e-mail, Discord…)
- `criador_ferramentas` — Criador automático de ferramentas — ideia 7 + "Jarvis que cria os próprios plugins".
- `cristal_calendario` — Calendário comercial infantil — Cristal Malhas. As datas que vendem roupa infantil no Brasil, calculadas para cada ano
- `cristal_fotos` — Foto → post pronto — Cristal Malhas. Você tira a foto da roupa e solta na pasta (padrão: Imagens\Cristal Malhas\Novas,
- `cristal_malhas` — Módulo Cristal Malhas — plugin do J.A.R.V.I.S BR. Para a divulgação
- `cristal_video` — Montador de vídeo de produto — Cristal Malhas. Você grava os clipes crus (celular, qualquer orientação) e solta numa pasta.
- `cuidador` — Modo cuidador. Rotina de cuidados com alguém da família: horários (remédios, refeições,
- `cupom_fiscal` — Cupom fiscal vira gasto (fork PT-BR 2.16, ideia 4). "Jarvis, lê essa nota" (a foto mais nova de Downloads, da pasta de cupons ou do WhatsApp)
- `demonstracao` — Aprender tarefas por demonstração. "Jarvis, observa" → você faz a tarefa uma vez (cliques, teclas)
- `detector_golpe` — Detector de golpe. Cole (ou dite) um link ou uma mensagem suspeita: o JARVIS analisa sinais de
- `diario` — Diário por entrevista. À noite (21h30, ajustável) o JARVIS pergunta "como foi o seu dia?" e conversa
- `ditado` — Ditado inteligente: você fala, ele escreve formatado no app que estiver aberto. "Jarvis, escreve um e-mail educado recusando a proposta do fornecedor"
- `ditado_codigo` — Ditado de código. Você EXPLICA a lógica falando — em quantas frases quiser — e o JARVIS
- `documentacao` — Documentação automática. "Jarvis, documenta o projeto C:\projetos\loja"
- `downloads` — Gerenciador de downloads — plugin do J.A.R.V.I.S BR. * Avisa quando um download TERMINA ("Download concluído: foto_produto.zip").
- `duplicados` — Duplicados e fotos borradas (fork PT-BR 2.16, ideia 17). "Jarvis, procura arquivos duplicados em Downloads"
- `ensina_errado` — Modo "me ensina errado". O JARVIS explica um assunto com UM erro proposital escondido. Você precisa
- `entrevista` — Simulador de entrevista de emprego por voz. O JARVIS vira o entrevistador: faz uma pergunta por vez (técnicas e de
- `estado_mundo` — Estado do mundo e central de avisos. "Jarvis, o que eu tô fazendo agora?" (o que ele percebe: jogo, código, edição, chamada, live…)
- `estilo_escrita` — Responder no seu estilo. O JARVIS aprende COMO você escreve — tamanho das mensagens, gírias e
- `estudio_rap` — Estúdio de rap. "Jarvis, me dá rimas com 'impossível'"
- `eu_virtual` — Eu virtual — o seu gêmeo digital. O JARVIS passa a SIMULAR você: responde como você responderia, com o seu
- `evolucao` — JARVIS que evolui sozinho — veja core/evolucao.py. "Jarvis, o que você aprendeu sobre o meu jeito?"
- `explica_crianca` — Modo "explica pra uma criança" (fork PT-BR 2.9/2.10). Pega qualquer assunto difícil e pede pro cérebro explicar com palavras simples,
- `explica_repo` — "Me explica esse repositório". Baixa um projeto do GitHub (ou lê uma pasta do PC), mapeia a estrutura
- `expressoes` — Expressões do rosto. "Jarvis, fica feliz" "Jarvis, faz cara de surpresa"
- `feriados` — Planejador de feriados (fork PT-BR 2.16, ideia 2). "Jarvis, quais os feriados de 2027?"
- `fiado` — Caderneta de fiado. "Jarvis, a Maria levou 150 reais fiado"
- `fila_leitura` — Fila de leitura (fork PT-BR 2.16, ideia 13). "Jarvis, salva esse link para ler depois" (o link copiado, ou o da aba do navegador)
- `gamificacao` — Gamificação da vida. Você ganha XP, sobe de nível e desbloqueia conquistas com o que já faz
- `garantias` — Garantias e manuais. "Jarvis, guarda a garantia: comprei um roteador hoje" (+ foto da nota)
- `gastos` — Controle de gastos por voz — plugin do J.A.R.V.I.S BR. "Jarvis, gastei 40 reais no almoço" → registra (categoria: alimentação)
- `gemeo_digital` — Gêmeo digital do computador — ideia 1. O JARVIS mantém um MODELO do seu PC e aprende com ele
- `geofence` — Geofence pelo celular. O celular avisa o JARVIS quando você CHEGA e quando SAI de casa
- `gerador_beats` — Gerador de beats. Instrumentais simples feitos na hora, em Python puro (numpy), sem samples
- `gerador_projetos` — Gerador de projetos. "Jarvis, cria um projeto Flask com login chamado loja"
- `gerador_testes` — Gerador de testes automáticos. Lê um arquivo.py, acha as funções públicas e escreve testes unittest para
- `gestos` — Controle por gestos — MediaPipe Hands, leve, só na CPU. "Jarvis, liga os gestos" "Jarvis, desliga os gestos" "Jarvis, status dos gestos"
- `git_assistente` — Assistente de Git. "Jarvis, quais projetos têm mudança não commitada?" (varre a pasta de projetos)
- `gravador_tela` — Gravação de tela — plugin do J.A.R.V.I.S BR. "Jarvis, grava a tela" → tela inteira (monitor principal)
- `guarda_seguranca` — Guarda de segurança — plugin do J.A.R.V.I.S BR. Fica de olho, em segundo plano e de forma leve (uma rodada por minuto), em
- `guarda_vps` — Guarda do VPS. De tempos em tempos, entra no seu servidor pelo SSH (o do próprio Windows,
- `guardiao_decisoes` — Guardião de decisões — plugin de voz (ideia 12, fork PT-BR 1.4). "Jarvis, é seguro apagar a pasta Temp?" → avalia e explica
- `habilidades` — Sistema de habilidades combináveis — ideia 13. Em vez de cada função ser isolada, o JARVIS tem habilidades PEQUENAS que se
- `habitos` — JARVIS aprende seus hábitos. Olha a linha do tempo (qual programa/site você abre e a que horas) e percebe
- `hipoteses` — Motor de hipóteses concorrentes — ideia 2. Diante de um problema ("o PC está lento", "a internet caiu", "o som sumiu",
- `historico_clipboard` — Histórico da área de transferência — plugin do J.A.R.V.I.S BR. Guarda os últimos 50 textos que você copiou (os fixados não contam no limite).
- `holograma_mao` — Holograma na mão. "Jarvis, mostra o clima na minha mão"
- `humor` — Humor interno. O JARVIS tem um "estado" que muda com o seu dia — e isso muda o JEITO de
- `ideias` — Caixinha de ideias. "Jarvis, anota uma ideia: app de estoque pra lojas pequenas."
- `interprete` — Modo intérprete presencial. "Jarvis, modo intérprete em inglês" (ou espanhol, francês, italiano…)
- `interrupcao` — Interromper o JARVIS — veja core/interrupcao.py. Jeitos de cortar a fala dele
- `jarvis_dj` — JARVIS DJ: entre as músicas, ele comenta como locutor de rádio. "Jarvis, liga o modo DJ" "Jarvis, desliga o modo DJ"
- `jarvis_friday` — JARVIS + FRIDAY trabalhando juntos. Tudo software, grátis. "Jarvis, pergunta pra FRIDAY o que ela acha de eu aprender Rust" → os dois conversam
- `jogar_junto` — Jogar junto — Roblox, Minecraft e outros. O JARVIS vira seu parceiro de jogo de três jeitos
- `jogos` — Modo diversão / Arcade J.A.R.V.I.S. "Jarvis, abre os jogos" → janela do Arcade com 14 jogos clicáveis
- `laboratorio` — Laboratório de experiências — ideia 6. Antes de mudar algo de verdade, o JARVIS testa num AMBIENTE SEPARADO
- `legenda_ao_vivo` — Legenda e tradução ao vivo. Escuta o ÁUDIO DO SISTEMA (o que sai nas caixas/fone: vídeo em inglês, call,
- `ligacao` — JARVIS te liga de verdade. Em alerta CRÍTICO (a sentinela disparou, o servidor caiu, um alarme de
- `limpeza` — Limpeza do sistema — plugin do J.A.R.V.I.S BR. "Jarvis, limpa o PC" → mede e mostra a prévia ("posso liberar 3,2 GB
- `linha_do_tempo` — Linha do tempo do seu dia. Registra qual janela está em foco (a cada 5 s, quase sem custo) e quando
- `lista_compras` — Lista de compras. "Jarvis, põe leite, ovos e sabão em pó na lista"
- `luva_repulsor` — Luva repulsor — ESP32 + acelerômetro/giroscópio MPU6050 (+ sensor de flexão opcional). "Jarvis, configura a luva" → IP e CHAVE para o sketch esp32/luva
- `macros` — Macros de teclado e mouse — plugin do J.A.R.V.I.S BR. "Jarvis, grava a macro relatório" → começa a gravar (teclado e mouse)
- `manutencao_casa` — Manutenção da casa. "Jarvis, me lembra de trocar o filtro de água a cada 6 meses"
- `mapa_dependencias` — Mapa vivo de dependências — ideia 10. Lê o código Python de um projeto (o próprio JARVIS por padrão, ou qualquer
- `memoria_contrafactual` — Memória contrafactual — ideia 9. Depois de cada tarefa, o JARVIS se pergunta: "e se eu tivesse feito de outro
- `memoria_grafo` — Memória em grafo com busca por significado — veja core/memoria_grafo.py. "Jarvis, o que eu decidi sobre o capacete?" (acha pelo significado)
- `memoria_inteligente` — Memória com esquecimento inteligente — ideia 4. Cada lembrança guarda
- `memoria_projeto` — Memória por projeto. O JARVIS percebe qual projeto está aberto no VS Code (ou Cursor) pelo título da
- `memoria_tela` — Memória de tela. De tempos em tempos (1 min, só quando a tela mudou e você está no PC) o
- `mensageiros` — JARVIS no Telegram e no Discord. O WhatsApp é a ferramenta whatsapp_jarvis. "Jarvis, liga o Telegram" "Jarvis, autoriza meu Telegram" (código para mandar ao bot)
- `mestre_rpg` — Mestre de RPG. O JARVIS narra uma aventura interativa por voz: você diz o que seu personagem
- `meta_vendas` — Meta de vendas do mês. "Jarvis, minha meta de vendas é 6 mil por mês"
- `missoes` — Missões em segundo plano — veja core/missoes.py. "Jarvis, organiza as fotos da pasta Imagens" (copia para Ano/Mês; o original fica)
- `modo_apresentacao` — Modo apresentação. Pra quando você vai apresentar slides. O JARVIS entra em "não perturbe" (nada de
- `modo_aula` — Modo aula. "Jarvis, grava essa aula de banco de dados"... "Jarvis, termina a aula"
- `modo_carro` — Modo carro — só voz, para quando você está dirigindo. No celular, toque em 🚗 no painel do JARVIS: a tela vira um botão grande de
- `modo_convidado` — Modo convidado. Visita quer conversar com o JARVIS? Ligue o modo convidado: ele continua
- `modo_debate` — Modo debate. Você dá uma opinião e o JARVIS defende o lado OPOSTO, com bons argumentos,
- `modo_dormir` — Modo dormir: o JARVIS dorme — e cuida do seu sono. "Jarvis, vai dormir" / "dorme 30 minutos" / "fica quieto até as 15h"
- `modo_faxina` — Modo faxina / anônimo. Limpa o lixo do SEU PC com um comando: arquivos temporários, lixeira, lista de
- `modo_jogo` — Modo Jogo / Desempenho — plugin do J.A.R.V.I.S BR. "Jarvis, modo jogo"
- `modo_professor` — Modo professor — repetição espaçada. Você estuda; o JARVIS faz perguntas em dias diferentes, cada vez mais
- `modos` — Modos do JARVIS — um lugar só para todos os modos novos. "Jarvis, modo loja" "Jarvis, sai do modo loja"
- `monitor_sistema` — Monitoramento completo do PC — plugin do J.A.R.V.I.S BR. Lê tudo do core/telemetria.py (a fonte única de métricas, a mesma do HUD) e
- `musica` — Música por voz: Spotify e YouTube Music. "Jarvis, toca Kaiser" "Jarvis, toca a playlist de treino"
- `narrador` — Narrador da vida. O JARVIS descreve o seu dia como um documentário de natureza: "Aqui vemos o
- `neste_dia` — "Neste dia". Tudo software, grátis. "Senhor, há um mês o senhor estava criando a versão 1.0 do J.A.R.V.I.S BR."
- `notificacoes` — Notificações no celular. Configuração do push pelo ntfy (grátis, sem conta) e um teste
- `objetos_quarto` — Câmera do quarto: onde ficou o carregador? "Jarvis, liga a câmera do quarto" (desligada até você pedir)
- `olha_isso` — "Jarvis, olha isso". Captura SÓ a janela ativa (VS Code, terminal, um erro no navegador — não a
- `oportunidades` — Detector de oportunidades — ideia 11. Uma vez por dia o JARVIS olha o seu uso e o estado do PC procurando o que
- `organizador_abas` — Organizador de abas. Guarda conjuntos de links por assunto (sessões) e reabre tudo de uma vez.
- `ouvido_ambiente` — Ouvido ambiente. Escuta o ambiente pelo MESMO microfone do JARVIS (uma cópia, processada aqui
- `painel_dev` — Painel de produtividade dev. Horas programando (pela linha do tempo: VS Code, PyCharm, terminal…), por
- `painel_led` — Painel de LED na parede — matriz MAX7219 com ESP32. "Jarvis, configura o painel de LED" → IP e CHAVE para o sketch esp32/painel_led
- `palpite_humor` — Palpite de humor / energia. Um palpite leve de como você deve estar — pelo HORÁRIO e pelo quanto você está
- `parceiro_rima` — Parceiro de rima. Para quem escreve rap: conta as sílabas poéticas de cada verso (a métrica),
- `pausa_ausente` — Pausa quando você sai. "Jarvis, liga a pausa automática" "Jarvis, desliga a pausa automática"
- `personas` — Segunda persona: F.R.I.D.A.Y. Outra voz e outra personalidade para outro contexto: o JARVIS cuida da
- `pesquisa_profunda` — Pesquisa profunda (fork PT-BR 2.16, ideia 16). "Jarvis, faz uma pesquisa profunda sobre energia solar para casa em Goiânia"
- `planilha_viva` — Planilha viva (fork PT-BR 2.16, ideia 8). "Jarvis, adiciona venda de 89 reais na planilha"
- `plantas` — Planta com sede — sensor de umidade da terra com ESP32. "Jarvis, configura a planta" → liga o servidor e diz o IP e a CHAVE para o sketch
- `pomodoro` — Foco / Pomodoro — plugin do J.A.R.V.I.S BR. "Jarvis, começa um pomodoro" → 25 min de foco, 5 de pausa
- `por_que_fechou` — "Jarvis, por que você fechou?" Explica, em português, como o JARVIS terminou da última vez — pedido de fechar,
- `porteiro_voz` — Porteiro de voz. Controla com quem o JARVIS fala. Por padrão, só o dono. O dono pode apresentar
- `portfolio` — Currículo e portfólio automáticos. A partir dos seus repositórios PÚBLICOS do GitHub, monta
- `postura` — Detector de cansaço e postura. Pela webcam (de tempos em tempos, poucos segundos), o JARVIS compara você
- `preencher_form` — Preenchedor de formulários por voz. Guarda os seus dados que você vive digitando em site (nome, e-mail, telefone,
- `prioridades` — Cérebro de prioridades adaptativas — ideia 15. Uma fila de tarefas que se REORDENA sozinha conforme o momento
- `probabilidades` — Motor de probabilidades — fork PT-BR 1.6. "Senhor, as chances de sucesso são de 14%."
- `procrastinacao` — Detector de procrastinação. O JARVIS repara quando você fica voltando pra uma distração (abriu o YouTube três
- `professor_ingles` — Professor de inglês. Conversa por voz EM INGLÊS, no seu nível, sobre o tema que você quiser. Quando
- `protocolos` — Protocolos nomeados — plugin do J.A.R.V.I.S BR (versão 1.2: passos em ordem). Uma frase dispara uma sequência de passos, EXECUTADOS NA ORDEM em que estão
- `quando_voltar` — Relatório de "quando voltar". Quando você volta depois de um tempo fora (1 h por padrão), o JARVIS conta o
- `quiz_geek` — Quiz geek — Marvel, DC, animes, games, Star Wars, tecnologia. Perguntas de múltipla escolha valendo pontos, com sequência de acertos (vale
- `racha_conta` — Racha a conta (fork PT-BR 2.16, ideia 5). "Jarvis, racha a conta: somos 5, o João pagou tudo, 250 reais"
- `radar_anomalias` — Radar de anomalias pessoais do sistema — ideia 8. Não usa limites fixos ("CPU acima de 90%"): aprende o NORMAL do SEU PC e do
- `radionovela` — Radionovela. Tudo software, grátis. JARVIS, FRIDAY e um narrador interpretam uma história em capítulos, cada um com
- `rastreio` — Rastreio de encomendas. "Jarvis, rastreia esse código: QB123456789BR, é o fone da Shopee"
- `realidade_aumentada` — Realidade aumentada no celular. No painel do celular, o botão 🥽 abre a câmera com uma sobreposição
- `reconhecimento_facial` — Reconhecimento facial do dono — plugin do J.A.R.V.I.S BR. O que faz
- `reconstrucao` — Reconstrução de acontecimentos — ideia 14. "Jarvis, o que aconteceu ontem à tarde?" "Por que o PC travou às 15h?"
- `relatorio_loja` — Relatório semanal da loja, falado. Toda segunda de manhã (na primeira vez que o JARVIS estiver aberto a partir das
- `renomear_fotos` — Renomeador de fotos pelo conteúdo. Pega fotos com nome sem graça (IMG_2026.jpg, WhatsApp-Image-...jpg) e renomeia pelo
- `resumo_grupo` — Resumo de grupo lotado — "o que rolou no grupo enquanto eu estava fora?" Lê a conversa exportada do WhatsApp (conversa → ⋮ → Mais → Exportar conversa →
- `resumo_video` — Resumo de vídeo do YouTube. "Jarvis, resume esse vídeo" (o vídeo aberto no navegador)
- `retrospectiva` — Linha do tempo do mês — retrospectiva. "Jarvis, o que eu fiz em outubro?" — junta TUDO que ficou registrado no
- `roleta` — Roleta de rolê — "Jarvis, decide o que eu janto." Sorteia comida, filme, série, jogo ou rolê com base no SEU gosto: aprende com
- `rosto_flutuante` — Rosto flutuante por voz — plugin do J.A.R.V.I.S BR 1.3. "Jarvis, fica no canto da tela" / "mostra seu rosto flutuante"
- `saude_pc` — Relatório de saúde do PC — plugin do J.A.R.V.I.S BR. "Jarvis, como está a saúde do PC?" → nota de 0 a 100, os problemas em ordem
- `segunda_opiniao` — Duas opiniões. Em respostas IMPORTANTES, um segundo agente — um revisor cético, com
- `segundo_cerebro` — Segundo cérebro por voz. Você fala uma ideia, um lembrete ou uma informação solta e o JARVIS guarda sozinho,
- `seguranca_adaptativa` — Segurança que aprende o SEU PC. Não tem lista fixa de regras: a cada 5 minutos ele anota o que é normal no
- `senha_vazada` — Senha vazada? Confere se uma senha sua já apareceu em vazamentos, pelo Have I Been Pwned,
- `sentinela` — Modo Sentinela. Quando você sai, a webcam vigia o PC. Se alguém mexer — um rosto que não é
- `servidores` — Vigia de servidores e sites. Confere a cada minuto se os seus sites/servidores respondem (HTTP ou porta
- `simulador` — Simulador de futuros — ideia 3. Antes de mexer em arquivos ou no sistema, o JARVIS calcula o que vai acontecer,
- `snapshots` — Backup e snapshot automático dos projetos. A cada hora, nos projetos que mudaram
- `talk_show` — Você no talk show. Tudo software, grátis. O JARVIS vira apresentador de um programa de entrevistas e te entrevista como
- `tela_ao_vivo` — JARVIS vendo a sua tela em tempo real. "Jarvis, olha minha tela" (liga por 10 minutos)
- `testes_vivos` — Comemoração dos testes. "Jarvis, roda os testes" (no projeto aberto no VS Code)
- `thumbnails` — Thumbnails e capas. Gera capas para YouTube (1280×720), post (1080×1080) e story/Reels
- `torneio` — Torneio entre amigos. "Jarvis, cria um torneio de Roblox com João, Pedro, Ana e eu" → chaveamento sorteado
- `turno_noite` — Turno da noite. Enquanto você dorme (PC ligado e parado), o JARVIS
- `verificacao` — Verificação — o comando de voz e o vigia. O núcleo está em core/verificacao.py. Aqui ficam
- `verificador_link` — Verificador de link e arquivo (fork PT-BR 2.16, ideia 19). "Jarvis, esse link é seguro?" (o link copiado)
- `vigia_codigo` — Vigia de código em tempo real. O JARVIS fica OLHANDO a sua tela de código e, quando vê um erro, FALA o erro e a
- `vigia_preco` — Vigia de preço. "Jarvis, me avisa quando a RTX 3060 baixar de R$ 1.500"
- `vitrine` — Modo vitrine: "Jarvis, se apresenta." Abre uma tela cheia de cinema (dashboard/static/vitrine.html) e o JARVIS se
- `voz_dono` — Voz do dono — cadastro e teste. "Jarvis, aprende a minha voz"
- `whatsapp_conversas` — O JARVIS nas SUAS conversas do WhatsApp. "Jarvis, o que me mandaram no whats?" (resumo das não lidas; não marca como lida)
- `whatsapp_jarvis` — Conversar com o J.A.R.V.I.S pelo WhatsApp. "Jarvis, liga o WhatsApp" → na 1ª vez instala a ponte e mostra o QR code
- `xadrez` — Xadrez e damas por voz (fork PT-BR 1.6; motor próprio na 1.7 — não precisa instalar nada). XADREZ: "Jarvis, vamos jogar xadrez" "cavalo para f3"

## Modos por categoria (158)

**Dinheiro e garagem (3, novos da 3.8):** Mineração (`mineracao`, mostra a conta e o status ao entrar e desliga a mineração ao sair; nunca liga sozinho), Cripto (`cripto`, "modo bitcoin"), Garagem (`garagem`, "modo oficina")

**Impossíveis (10, novos da 3.6):** OMEGA (`omega`), Bunker (IA local) (`bunker`), Cartório (`cartorio`), Bastidores (`bastidores`), Eu do futuro (`eu_do_futuro`), Cobaia (`cobaia`), Autópsia sem culpa (`autopsia`), Tira-teima (`tira_teima`, "modo impossível"), Só fatos (`so_fatos`), Fortaleza (`fortaleza`)

Os marcados com ★ são novos da 2.19.

**Programacao (17):** Foco em programação (`programador`), Caça ao bug (`debug`), Deploy (`deploy`), Revisão de código (`revisao`), Hackathon (`hackathon`), Laboratório Stark (`laboratorio_stark`), Programação em par (`pair_programming`)★, Refatoração (`refatoracao`)★, TDD (`tdd`)★, Documentação (`documentacao`)★, Arquitetura (`arquitetura`)★, Revisão de segurança (`seguranca`)★, Banco de dados (`banco_dados`)★, Front-end (`frontend`)★, Treino de IA (`ia_treino`)★, Só comandos (`terminal`)★, Plantão (`plantao`)★

**Trabalho (11):** Em reunião (`reuniao`), Atendimento ao cliente (`cliente`), Freela (`freela`), Fechamento do mês (`financas`), Planejamento da semana (`planejamento`), Retrospectiva da semana (`retro_semana`), E-mails (`email`)★, Procurando emprego (`procurando_emprego`)★, Expediente (`expediente`)★, Dando aula (`instrutor`)★, Papelada do MEI (`papelada_mei`)★

**Loja (8):** Loja aberta (`loja`), Black Friday (`black_friday`), Inventário (`inventario`), Abertura da loja (`abertura_loja`)★, Fechamento da loja (`fechamento_loja`)★, Chegou mercadoria (`reposicao`)★, Fotos de produto (`fotos_produto`)★, Campanha sazonal (`datas_comemorativas`)★

**Estudo (17):** Estudo (`estudo`), Véspera de prova (`prova`), Leitura (`leitura`), Foco profundo (`foco_profundo`), Silêncio total (`biblioteca`), Brainstorm (`brainstorm`), Escrita (`escrita`), Pesquisa (`pesquisa`), Passo a passo (`tutorial`), Vestibular (`enem`)★, Matemática (`matematica`)★, Redação (`redacao`)★, Imersão em espanhol (`espanhol`)★, Imersão em inglês (`ingles`), Revisão ativa (`flashcards`)★, Trabalho acadêmico (`tcc`)★, Assistindo aula (`curso_online`)★

**Criacao (13):** Gravação de vídeo (`gravacao`), Live (`live`), Edição de vídeo (`edicao`), Design (`design`), Produção de beat (`beat`), Escrita de rap (`rap`), Podcast (`podcast`), Roteiro de vídeo (`roteirista`)★, Escritor (`escritor`)★, Fotografia (`fotografia`)★, Ensaio musical (`ensaio`)★, Batalha de rima (`freestyle`)★, Gravação de voz (`locutor`)★

**Casa (22):** Conversando com a vó (`vo`), Cozinha (`cozinha`), Faxina da casa (`faxina_casa`), Visita da família (`familia`), Criança por perto (`crianca`), Aniversário (`aniversario`), Festa (`festa`), Churrasco (`churrasco`), No mercado (`mercado`)★, Obra e reforma (`obra`)★, Arrumando a casa (`organizacao`)★, Domingo (`domingo`)★, Sextou (`sextou`)★, Almoço (`almoco`)★, Noite de jogos (`noite_de_jogos`)★, Karaokê (`karaoke`)★, Dever de casa (`dever_de_casa`)★, Hora da historinha (`historinha`)★, Hora do pet (`pet`)★, Jardinagem (`jardinagem`)★, Conserto em casa (`faca_voce_mesmo`)★, Marmitas da semana (`marmitas`)★

**Saude (9):** Treino (`treino`), Meditação (`meditacao`), Relax (`relax`), Repouso (`repouso`), Detox digital (`detox`), Corrida (`corrida`)★, Alongamento (`alongamento`)★, Consulta médica (`consulta`)★, Dia difícil (`dia_dificil`)★

**Dia a dia (11):** Bom dia (`bom_dia`), Madrugada (`madrugada`), Viagem (`viagem`), Emergência (`emergencia`), Suporte técnico p/ parente (`suporte_parente`), Economia de energia (`economia`), Mês apertado (`economizando`)★, Compras online (`compras_online`)★, Aeroporto (`aeroporto`)★, Férias (`ferias`)★, Sem energia (`apagao`)★

**Jogos (7):** Jogando Roblox (`roblox`), Jogando Minecraft (`minecraft`), Ranqueada (`competitivo`), Battle royale (`battle_royale`)★, Speedrun (`speedrun`)★, RPG de mesa (`rpg_mesa`)★, Estratégia (`estrategia`)★

**Jeitos (30):** Respostas turbo (`turbo`), Respostas detalhadas (`detalhado`), JARVIS clássico (`classico`), Sarcástico (`sarcastico`), Pirata (`pirata`), Sherlock (`sherlock`), Narrador de futebol (`narrador_futebol`), Coach motivacional (`coach`), Poeta (`poeta`), Otaku (`anime`), Velho sábio (`sabio`)★, Robô dos anos 80 (`robo`)★, Arauto medieval (`medieval`)★, Cientista (`cientista`)★, Filósofo (`filosofo`)★, Estoico (`estoico`)★, Comediante (`comediante`)★, Locutor de rádio (`locutor_radio`)★, História em quadrinhos (`quadrinhos`)★, Controle de missão (`controle_missao`)★, Inventor (`inventor`)★, Formal (`formal`)★, Descontraído (`descontraido`)★, Mentor (`mentor`)★, Geek (`geek`)★, Videogame 8 bits (`arcade_8bits`)★, Faroeste (`faroeste`)★, Agente secreto (`agente_secreto`)★, Espírito de Natal (`natalino`)★, Suspense (`suspense`)★

