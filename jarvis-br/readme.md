# 🤖 J.A.R.V.I.S BR

Assistente de voz estilo J.A.R.V.I.S para o computador, **em português**.
Ouve, vê a tela, fala, **monitora e controla o PC** no Windows, macOS e Linux.

> Este projeto é um **fork** do [Mark LVI](https://github.com/FatihMakes/Mark-LVI),
> criado por **FatihMakes** ([YouTube](https://www.youtube.com/@FatihMakes)).
> Toda a base do assistente é trabalho dele. O que muda nesta versão está em
> [CHANGELOG.md](CHANGELOG.md), e o README original está em
> [docs/README_ORIGINAL_MARK_LVI.md](docs/README_ORIGINAL_MARK_LVI.md).

**Versão atual: 3.9.4**: **cérebro pronto** — o cérebro local já vem treinado com ~4.900 comandos do dia a dia em português (volume, brilho, prints, abrir e fechar apps, música, clima, dólar, PC lento, limpeza, modo jogo, pomodoro, luzes, lista de compras, agenda…) **com a ação certa**, mais padrões como "abre <app>", "toca <música>", "volume 40", "timer de 10 minutos" e "tempo em <cidade>". Sem o Gemini, ele já faz esses comandos no primeiro dia; o que você ensina ou corrige sempre vence a base. Para treinar de novo: `python -m core.cerebro_treino`.

**3.9.3**: J.A.R.V.I.S na capa com botão ⇄ para a SEXTA-FEIRA, botões de música na tela, painéis que abrem por cima da interface, **`youtube: …`** na caixa mostra e toca vídeos na tela do JARVIS (sem abrir o YouTube) e **`salvar: …`** guarda o que você quiser em ★ SALVOS.

**3.9.2**: interface **F.R.I.D.A.Y** no centro da janela — a assistente com os hologramas, viva com a voz, menu clicável e os números do PC (o HUD 3.9, o rosto e o núcleo continuam em ⚙ → **HUD:**).

**3.9.1**: **HUD 3.9** — o painel J.A.R.V.I.S animado, clicável e com os números reais do PC, numa janela própria ("Jarvis, abre o HUD" ou o botão 🛰 HUD 3.9; veja `hud39/LEIA-ME.md`).

**3.9**: **MINER AI**, mineração real de cripto (Bitcoin em Python puro, sem instalar nada, e Monero pelo XMRig) com economia de energia, um cérebro que diz quando não compensa e um painel em que cada número tem o seu rótulo (veja `miner_ai/LEIA-ME.md`).

**3.8**: **modo mineração**, **modo cripto**, **modo garagem**, plugin **veiculo** (manutenção do carro e da moto) e **mapa mental** interativo.

**3.7**: **mineração** (calculadora honesta contra a conta de luz e controle seguro do XMRig) e **carteira de cripto** (custo médio, lucro e prejuízo).

**3.6.1**: **app para Android (APK)**. É o JARVIS do celular dentro de um app, sem Termux, com a voz do Android (veja `android/LEIA-ME-ANDROID.md`).

**3.6**: **OMEGA** — os 8 sistemas (cérebro, coração, imune, memória, conselho, evolução, sonho, laboratório) num painel e num ciclo diário; **livro-razão** que prova o que ele fez; **experimentos sorteados** na sua vida; **metacognição** (ele mede o quanto acerta e só evolui com prova e o seu sim); 10 modos novos.

**3.5**: **IA local** — instala uma vez um modelo pequeno no seu PC (llama.cpp + Whisper, sem Ollama e sem nada pago); quando a internet cai, o JARVIS troca sozinho para ela e volta para o Gemini quando a rede volta.

Da 3.4: **cérebro local** — uma IA pequena no seu PC que aprende como você fala os comandos; o que você já usou vira reflexo e roda na hora, sem o Gemini, inclusive sem internet.

Da 3.3: **caixa-preta** (quando você corrige o JARVIS, ele anota o erro e não repete — no PC e no celular), **eu do futuro** (você daqui a alguns meses, projetado com os seus próprios números: loja, hábitos, estudo, corrida), **gêmeo digital da loja** (simula a promoção com o histórico do caixa — vendas e lucro com e sem ela — e aprende com cada promoção que você faz) e **código em rap** (explica arquivo, função ou commit como rap geek original, com desafio de adivinhar a função). Mais uma varredura automática de bugs no projeto inteiro: o WhatsApp por voz agora usa a ponte e confirma o envio.

Da 3.2: **anti-eco** (o JARVIS não responde mais a própria voz que volta pela caixa de som — percebe pelo texto e aprende a sala), **modo anônimo** (sem as suas memórias e sem gravar nada da conversa) e **estudos com quadro** (uma lousa no navegador onde ele escreve fórmulas, passos e gráficos enquanto explica; você desenha por cima).

Da 3.1: o **JARVIS BIOLOGICAL CORE** — o JARVIS ganhou um corpo digital: cérebro com IA básica local (aprende a classificar erros, raciocina sobre a causa com probabilidades e escolhe o reparo que já funcionou), coração, sistema nervoso, circulação, **DNA digital** assinado, **sistema imunológico de 8 camadas** (isola só a parte doente, bloqueia quem tenta desligar antivírus/firewall, testa e libera sozinho) e **regeneração** em 10 passos que nunca apaga arquivo e pede o seu sim na tela para mexer em qualquer coisa. Painel futurista e aba **Corpo** no celular. Guia: [biological_core/LEIA-ME.md](biological_core/LEIA-ME.md).

Da 3.0: **mais leve, mais rápido e sem travar** (nenhuma ferramenta segura a conversa por mais de 30 s; rotinas de fundo numa thread só) e 20 ideias "impossíveis" — oráculo de vendas, pré-mortem, livro da vó, rap da semana, conferir pagamento… Da 2.17 à 2.21: os lotes de plugins e modos, o catálogo sob demanda, os sonhos e o conselho do multiverso (tudo em [CHANGELOG.md](CHANGELOG.md); lista completa em [LISTA-PLUGINS-E-MODOS.md](LISTA-PLUGINS-E-MODOS.md)).

Da 2.11: nove funções novas de uma vez — **renomeador de fotos** (pelo conteúdo), **organizador de abas** (sessões por assunto), **modo apresentação** (slides por voz), **assistente de viagem** (mala, fuso, câmbio, roteiro), **clone de estudo** (provas simuladas), **modo faxina/anônimo** (limpa o PC), **palpite de humor**, **preenchedor de formulário por voz** e o **Modo Acompanhar** (olha a sua tela quando você pede).

Da 2.10: mais três — **explica pra uma criança** (qualquer assunto difícil em palavras simples), **coach de decisões** (prós e contras com pesos que você ajusta) e **detector de procrastinação** (ele cutuca de leve quando você fica voltando pro YouTube).

Da 2.9: dois novos — o **segundo cérebro por voz** (você fala uma ideia ou informação solta e ele guarda organizada em pasta e tags, e acha depois) e a **biblioteca de prompts** (guarda os seus pedidos bons e reaproveita por voz).

Da 2.8.3: corrigida a queda **"access violation" no volume do Windows** (pycaw/COM): os objetos de som do Windows agora vivem numa thread só e não derrubam mais a janela.

Da 2.8.2: corrigido o JARVIS **fechando depois de pesquisar na internet** (a busca do DuckDuckGo agora roda num processo separado; se ela cair, o JARVIS continua).

Da 2.8.1: corrigido o JARVIS **fechando sozinho por causa do som** (a placa de som era aberta e fechada em duas threads ao mesmo tempo, principalmente ao reconectar) e agora ele **diz por que fechou** — no fim da janela preta do `iniciar.bat`, na próxima abertura, ou perguntando "Jarvis, por que você fechou?".

Da 2.8: **modo dormir de verdade** — "Jarvis, vai dormir" e ele para de ouvir (nada vai para a internet), guarda os avisos e acorda com **duas palmas**, **Ctrl+Alt+D**, "Jarvis, acorda" (no próprio PC) ou na hora marcada, sem precisar da ativação por voz. E o JARVIS cuida do seu sono: **boa noite** (não perturbe, som para dormir, luzes, tela apagada), **bom dia** com quanto você dormiu, **despertador com soneca**, **cochilo**, **ciclos de sono**, **diário do sono**, **ruído branco/ventilador** e **respiração guiada**. Também corrige o firewall do painel no Linux, o "olha isso" no Python 3.11, o falso "chave inválida" e o botão ACORDAR do celular.

Da 2.7.4: corrigido o JARVIS **fechando ao reconectar** com o Gemini (e a sessão não cai mais por inatividade). Da 2.7.3: o botão **INTERROMPER** não fecha mais o programa (o código que derrubava foi apagado). Da 2.7.2: corrigido o JARVIS **fechando do nada** quando você dizia "Jarvis, fecha (outra coisa)"; agora ele anota por que fechou. Da 2.7.1: acentos na voz do Windows, microfone no cinema. Da 2.7: **JARVIS + FRIDAY** juntos, cada um com a sua voz e o seu rosto (conversam, dividem
tarefas, passam o turno, um revisa o outro, competem, fazem reunião de equipe e tem o **modo Ultron**),
**sessão de cinema** (não perturbe, "o que eu perdi?" sem spoiler, catálogo, maratona, quiz) e mais
diversão: **radionovela**, **talk show**, **"neste dia"** e **campanha de herói**. Tudo software e grátis.

Da 2.6.2: corrigido o programa **fechando depois de interromper** o JARVIS.

Da 2.6.1: corrigido o JARVIS **fechando sozinho** ("tchau", "para" ou "desliga o intérprete" não fecham mais o programa; erros vão para `memory/erros.log` em vez de derrubar a janela).

Da 2.6: **modo vitrine** — "Jarvis, se apresenta" e ele mostra sozinho as melhores
funções, uma por uma, com a própria voz, legenda, efeitos e demonstrações animadas (dados de exemplo),
em 16:9 ou 9:16, pronto para gravar o vídeo de divulgação no OBS.

Da 2.5: o JARVIS cuida da **casa e das contas** — lê os **boletos** do e-mail e dos
PDFs e avisa 3 dias antes ("A conta de luz vence sexta, R$ 142."), **rastreia encomendas** (Correios,
Shopee, Mercado Livre, transportadoras) e avisa quando saem pra entrega, guarda **garantias** pela foto
da nota e acha o **manual** ("Como reseto o roteador?"), avisa a **chuva chegando** pelo radar
("melhor tirar a roupa do varal") e mantém uma **caixinha de ideias**. Na câmera e no ESP32: **celular
na mão no pomodoro**, **negociação de distração**, **câmera do quarto** que lembra onde ficou o
carregador, **planta com sede**, **painel de LED** e a **luva repulsor**. Para lives e visitas:
**conversa em grupo** (reconhece quem fala), **avatar** que reage na live, **holograma na palma da
mão** e **modo intérprete**. E o Arcade ganhou **5 jogos** (19 no total).

Da 2.4.1: **interromper o JARVIS funciona** — falando por cima dele, com ESC, com
**Ctrl+Alt+P em qualquer janela** ou com a tecla do push-to-talk — e a resposta seguinte não sai
mais muda depois de uma interrupção.

Da 2.4: o JARVIS **evolui sozinho** (testa jeitos de responder e fica com o que
funciona para você), **memória em grafo** com busca por significado e uma **rede neural treinada
no seu PC**, **missões** que rodam por horas e sobrevivem ao reinício, **estado do mundo** e
**central de avisos** (não fala no meio do jogo; resume depois), **estúdio de rap**, **cápsula do
tempo com a sua voz**, **diário por entrevista** e **segurança que aprende o seu PC**.

Da 2.3: o JARVIS nas **suas conversas do WhatsApp** (lê, resume, manda no seu
nome, faz rascunho e, onde você liberar, responde como seu assistente), **secretária** que
recusa ligações do WhatsApp e anota o recado, e o **número da Twilio atendendo** ligações:
você fala com o JARVIS por voz (com PIN) e outras pessoas deixam recado.

Da 2.2: tela **"Tocando agora"** do Spotify com playlists, **QR do WhatsApp**
numa janela própria (sem baixar navegador), o JARVIS **vendo a sua tela em tempo real**,
despertador musical, timer de sono, música por humor e rádio do seu gosto.

Da 2.1: **JARVIS só no celular** — uma versão que roda inteira no celular, sem
depender do computador (pasta `celular/app`, hospedada de graça no GitHub Pages).

Da 2.0: **música** (Spotify e YouTube Music), **conversa por WhatsApp, Telegram,
Discord e ligação**, um **companheiro** que puxa assunto e oferece coisas do seu gosto, **treinador
de jogos** (Roblox e outros) e o **app do JARVIS no celular**, que funciona sozinho ou como o
JARVIS completo do PC.

Da 1.9: **14 ideias novas** — gestos com a mão pela webcam, memória por projeto
("onde eu parei?"), modo aula, snapshots automáticos dos projetos, vigia do servidor com CPU e disco,
ditado inteligente em qualquer app, comemoração dos testes, rascunhos de resposta para clientes no
WhatsApp, relatório semanal da loja, holograma de pirâmide, JARVIS DJ, XP estilo Stark, pausa quando
você sai e resumo de vídeo do YouTube.

Da 1.8: **modo remoto** — de qualquer lugar, veja as câmeras e a tela do PC ao
vivo, controle TV, celular, PCs e luzes pela **Central** 🛰 (Tailscale ou link da Cloudflare) e
**converse com o JARVIS pelo WhatsApp** (pedidos, fotos da câmera, avisos, áudio).

Da 1.7: **Arcade J.A.R.V.I.S** — uma janela com 14 jogos clicáveis (xadrez e
damas contra o JARVIS, jogo da velha, lig 4, campo minado, 2048, cobrinha, blocos,
quebra-tijolos, memória, forca, genius, pedra-papel-tesoura e reflexo), jogos por voz e o
xadrez com **motor próprio** (não precisa instalar nada).

Da 1.6: **controle dos aparelhos da sua rede** (outros PCs, TV Roku/Samsung/
LG/Android TV, celular Android e as luzes, num lugar só) e mais 42 ideias: AR no celular,
modo armadura e modo carro, turno da noite, gerador de testes, de projetos e de documentação,
detector de golpe, senha vazada, guarda do VPS, modo convidado, ata de chamadas, entrevista,
caçador de vagas, professor de inglês, beats, RPG, xadrez e damas, cuidador, gamificação…
Tudo é plugin em `plugins/`: liga e desliga em 🧩 PLUGINS, e as opções de cada um ficam
em ⚙ CONFIG. DE PLUGINS.

---

## 🚀 Como usar

```bash
python setup.py      # instala tudo que o seu sistema precisa
python main.py       # ou dê dois cliques em iniciar.bat / iniciar.sh
```

Na primeira vez, cole sua chave **gratuita** da API do Gemini
(pegue em [aistudio.google.com](https://aistudio.google.com/app/apikey)).

Para conferir se está tudo certo (não abre janela nem mexe nos seus dados):

```bash
python -m unittest discover -s tests
```

---

## 😴 Novidades da 2.8 — modo dormir e sono

**O JARVIS dorme** (funciona sem a ativação por voz; dormindo, o microfone não vai para o Gemini)

| Diga | O que acontece |
|---|---|
| "Jarvis, vai dormir" / "dorme 30 minutos" / "fica quieto até as 15h" | Ele para de ouvir; os avisos ficam guardados para quando acordar |
| 👏👏 duas palmas · Ctrl+Alt+D · 👂 ACORDAR AGORA · digitar · celular | Acorda e conta "Enquanto eu dormia…" (só o urgente passa antes) |
| "Jarvis, acorda" | Reconhecido no próprio PC, sem internet (precisa do `faster-whisper`) |

**E cuida do seu sono** (⚙ CONFIG. DE PLUGINS → Modo dormir e sono)

| Diga | O que acontece |
|---|---|
| "Jarvis, vou dormir, me acorda às 6h30" | Não perturbe, som para dormir, cena da casa, tela apagada, música abaixando e o despertador |
| (de manhã) | Bom dia: quanto dormiu, média da semana, clima, o que vence hoje e o que chegou de noite |
| "Mais 10 minutos" | Soneca (o despertador toca de novo) |
| "Vou tirar um cochilo de 20 minutos" | Cochilo com despertador |
| "Que horas eu acordo se dormir agora?" | Os melhores horários pelos ciclos de 90 minutos |
| "Como foi meu sono?" / "dormi das 23h às 7h" | Diário do sono: média, dívida de sono e regularidade |
| "Toca chuva para dormir" / "ruído branco" / "ventilador" | Sons gerados no PC, que somem devagar |
| "Me ajuda a relaxar" | Respiração 4-7-8 (ou caixa) guiada por sons |

Se o PC reiniciar de madrugada, ele volta dormindo. Acordou de madrugada por um aviso urgente? Volta a dormir
sozinho depois de 2 minutos. O despertador precisa do PC ligado (a tela pode ficar apagada).

---

## 🤖 Novidades da 2.7 — JARVIS + FRIDAY, cinema e diversão

**JARVIS + FRIDAY** (abre o palco: um rosto para cada um, quem fala acende; Esc ou "para a cena" encerra)

| Diga | O que acontece |
|---|---|
| "Jarvis, pergunta pra FRIDAY o que ela acha de eu aprender Rust" | Os dois discutem de verdade, cada um com a sua voz, e chegam numa sugestão |
| "Jarvis, passa a música pra FRIDAY" | "FRIDAY, assuma a música, estou compilando o projeto." "Pode deixar, JARVIS." |
| "Passa o turno" (ou sozinho às 19h e 8h, ⚙ → JARVIS + FRIDAY) | O JARVIS lê o relatório do seu dia para a FRIDAY da noite, com voz mais calma |
| "FRIDAY, revisa o que o JARVIS disse" | Ela confere a última resposta: "Na verdade, JARVIS, essa conta está errada." |
| "Competição: expliquem recursão" → "a FRIDAY ganhou" | As duas respostas na tela; placar guardado e provocações |
| "Reunião de equipe: Rust ou Python?" | JARVIS, FRIDAY, ENGENHEIRA e CRÍTICO debatem, votam e decidem |
| "Cria o personagem Mestre Yoda: sábio, fala invertido" | Entra nas próximas reuniões |
| "Jarvis, modo Ultron" / "volta ao normal" | Vilão dramático e engraçado (faz tudo certo), a FRIDAY tenta salvar ele |
| "Podcast da manhã" / "Trailer do meu dia" / "Narra meu jogo" | Extras: notícias a dois, seu dia como trailer de cinema, narração da partida |

**Sessão de filme**

| Diga | O que acontece |
|---|---|
| "Jarvis, sessão de cinema: Interestelar" | Minimiza as janelas, não perturbe, abaixa o brilho, vinheta e "a sessão começa em 3, 2, 1…" |
| "Intervalo de 10 minutos" | Pausa o filme, avisa 1 min antes e dá play |
| "O que eu perdi?" / "dormi uns 20 minutos" | Resume só o que já passou, sem spoiler (ele anota o filme ouvindo o som do PC) |
| "Quem é esse ator?" (pausado) | Olha a tela e responde |
| "Acabou o filme, nota 9" | JARVIS e FRIDAY comentam: teorias, detalhes, a nota de cada um |
| "Assisti Dark, temporada 2 episódio 5" / "onde parei em Dark?" / "o que eu vejo agora?" | Catálogo com nota e recomendação |
| "Planeja uma maratona da Marvel na ordem da história" | Lista, tempo total e intervalos; "próximo da maratona" acompanha |
| "Quiz do filme" | 5 perguntas, você contra a FRIDAY |

**Mais diversão**

| Diga | O que acontece |
|---|---|
| "Começa uma radionovela de ficção científica" → "opção 2" | Capítulos com narrador, vozes e efeitos; você decide o rumo; um capítulo por dia |
| "Me entrevista no talk show" → "encerra o programa" | Ele vira apresentador, grava e salva o seu "episódio" (áudio + transcrição) |
| "Neste dia" | "Há um mês o senhor lançou a versão 1.0 do J.A.R.V.I.S BR." (diário, linha do tempo, changelog) |
| "Como está o vilão?" / "capítulo da semana" | Seu dia vira missões do Homem de Ferro; vilão da semana com vida e capítulo encenado |

Vozes dos personagens: `python -m pip install edge-tts miniaudio soundcard` (o instalador já tenta). Sem
eles, as cenas usam as vozes do Windows.

## 🎬 Novidades da 2.6 — modo vitrine

| Diga | O que acontece |
|---|---|
| "Jarvis, se apresenta" | Tela cheia de cinema: abertura, 13 funções (voz, PC, visão, contas, encomendas, chuva, foco, memória, loja, Homem de Ferro, holograma, avatar, Arcade) e encerramento com os créditos. Ele narra com a própria voz, com legenda e efeitos (~4 min) |
| "…em versão curta" / "…na vertical" | ~1 min com as melhores; 9:16 para Reels, TikTok e Shorts |
| "Jarvis, abre o roteiro da vitrine" | Edite falas, ordem e quais cenas entram |

Grave com o OBS (janela da vitrine + áudio do PC). O microfone fica pausado durante a apresentação.

## 🏠 Novidades da 2.5 — casa, contas, câmera, ESP32 e lives

**Casa e contas**

| Diga | O que acontece |
|---|---|
| (sozinho) / "Jarvis, lê esse boleto" | **Contas a vencer**: lê os boletos em PDF (pasta Documentos\JARVIS\Contas e Downloads), do **e-mail** (IMAP com senha de app, ⚙ → Contas a vencer), da linha digitável ditada ou da foto. Confere os dígitos verificadores (número errado não vira conta) e avisa 3 dias antes, no dia e se passar: *"A conta de luz vence sexta, R$ 142."* "Paguei a conta de luz" tira da lista; "copia o código da conta de luz" põe a linha no Ctrl+V. Ele nunca paga nada |
| "Jarvis, rastreia esse código" | **Rastreio**: pega o código que você copiou (ou ditou) e acompanha pelo 17TRACK (Correios, Shopee Xpress, Mercado Livre, Jadlog, Loggi, J&T, AliExpress…). Avisa sozinho: *"Senhor, sua encomenda saiu pra entrega."*, entregue, esperando retirada, taxa de importação, problema. "É pedido do fornecedor Malhas Sul" põe na **lista da loja**. "Mostra as encomendas" abre a tela |
| "Jarvis, olha essa nota fiscal" | **Garantias**: lê a nota pela webcam, pela foto que o celular mandou ou pelo PDF e avisa 30 e 7 dias antes de a garantia acabar |
| "Jarvis, como reseto o roteador?" | **Manuais**: acha o PDF do manual na internet, guarda e responde pelo texto dele, com a página |
| "Jarvis, estendi roupa no varal" | **Recolhe a roupa!** Olha o radar de chuva (RainViewer) e a previsão de 15 em 15 min (Open-Meteo): *"Vai chover em uns 20 minutos, melhor tirar a roupa do varal."* |
| "Jarvis, anota uma ideia: app de estoque pra lojas pequenas" | **Caixinha de ideias** por tema; todo domingo lembra das ideias paradas e pergunta se alguma vira projeto ("vira projeto" cria a pasta com um primeiro plano) |

**Foco, câmera e ESP32**

| Diga | O que acontece |
|---|---|
| "Jarvis, me vigia no foco" | No pomodoro, a webcam percebe o **celular na sua mão** (visão no próprio PC, MediaPipe): *"Senhor, o celular pode esperar mais 12 minutos."* |
| "Jarvis, me dá 5 minutos de YouTube?" | **Negociação**: *"Libero 5 se você terminar essa função primeiro."* Terminou? Ele libera e cobra quando acaba. Quer agora? Fica devendo — os minutos voltam no fim do foco |
| "Jarvis, liga a câmera do quarto" / "onde está o meu fone?" | De tempos em tempos (só quando a cena muda) anota onde ficaram carregador, fone, chave, controle… *"Vi seu fone em cima da cama às 14:20."* Começa desligada; não descreve pessoas |
| "Jarvis, configura a planta" | **Planta com sede** (ESP32 + sensor de umidade): *"A planta da sala está seca há 2 dias."* |
| "Jarvis, configura o painel de LED" | **Letreiro na parede** (ESP32 + MAX7219): hora, música tocando, avisos e vendas do dia; "escreve no painel: …" |
| "Jarvis, configura a luva" | **Luva repulsor** (ESP32 + MPU6050): abriu a mão com a palma para a frente, toca o som do repulsor e fecha a janela (ou passa o slide — você escolhe a ação de cada gesto) |

Os sketches e o passo a passo (peças, ligações, calibração) estão em `esp32/planta`,
`esp32/painel_led` e `esp32/luva`. Os aparelhos falam com o PC na porta 8765, com uma chave só sua.

**Lives, visitas e diversão**

| Diga | O que acontece |
|---|---|
| "Jarvis, aprende a voz da Maria" + "modo conversa em grupo" | **Conversa em grupo**: reconhece quem está falando (impressão de voz no PC) e responde cada um pelo nome |
| "Jarvis, liga o avatar da live" | **Avatar no OBS** (fonte Navegador, fundo transparente): o rosto do JARVIS fala, **ri, se surpreende e comemora** — com o que é dito, com cada venda da loja e com o chat da Twitch |
| "Jarvis, mostra o clima na minha mão" | **Holograma na mão**: janela com a webcam; mostre a palma aberta e o cartão aparece em cima dela (clima, música, vendas, imagem, texto). Fechar a mão esconde; pinça troca |
| "Jarvis, modo intérprete em inglês" | **Intérprete presencial**: você fala português e a tradução sai na caixa de som; a resposta da outra pessoa chega em português no seu fone |
| "Jarvis, abre o caça-palavras" | **Arcade +5**: caça-palavras (temas Tecnologia, Loja, Goiás, Games e Música), meteoros, **labirinto do Bitinho** (personagem nosso: um robô fugindo dos vírus num circuito), sudoku e pong contra o JARVIS |

## ✋ Novidades da 2.4.1 — interromper o JARVIS

| Como | O que acontece |
|---|---|
| **Fale por cima dele** | Ele para em ~0,3 s e ouve o que você disse desde o começo da frase. Com fone funciona na hora; com caixa de som ele separa a sua voz do eco dele (fale normal ou um pouco mais alto que a caixa). TV, música e teclado não cortam |
| **ESC** ou **✋ INTERROMPER** | Corta na hora (antes ainda saía até meio segundo do buffer da placa de som) |
| **Ctrl+Alt+P** | O mesmo, em qualquer janela — jogando, no VS Code (Windows) |
| **Tecla do push-to-talk** | Apertar para falar enquanto ele fala também corta |
| "Jarvis, desliga a interrupção por voz" | Se ele estiver se cortando sozinho por causa do eco (ou em ⚙ CONFIG. DE PLUGINS → Interrupção) |

Erros corrigidos: depois de um ESC a **próxima resposta saía muda**; o aviso de interrupção do
Gemini era ignorado (o áudio velho continuava tocando); e o detector de eco (`core/echo.py`)
falhava com o formato do microfone, então jogava fora até a sua voz logo depois que o JARVIS
parava de falar.

## 🧬 Novidades da 2.4 — o JARVIS que aprende você

| Diga | O que acontece |
|---|---|
| (sozinho) | **Evolui sozinho**: a cada conversa ele testa, discretamente, resposta curta × completa, tom formal × descontraído, resposta antes × passos antes. Se você **interrompe**, **corrige** ("não, não foi isso"), **pede de novo** ("repete", "o quê?") ou pede "resume"/"explica melhor", aquele jeito perde ponto; "valeu"/"perfeito" ganha. Quem funciona aparece mais (amostragem de Thompson) — seleção natural |
| "Jarvis, o que você aprendeu sobre o meu jeito?" | O placar ("respostas curtas funcionam melhor: 81% em 40 respostas"). "Sempre responde curto" fixa; "para de experimentar" pausa |
| "Jarvis, o que eu decidi sobre o capacete?" | **Memória em grafo**: acha "Escolhi o ESP32-S3 para o Mark" **sem a palavra exata**. Pessoas, projetos, produtos e lugares ficam ligados entre si |
| "Jarvis, abre o mapa da memória" | O mapa visual: bolinhas ligadas, clique para ver o que está ligado, busca por significado |
| "Jarvis, treina a rede da memória" | Treina a **rede neural** (skip-gram com pedaços de palavra, em numpy) nas SUAS memórias: aprende que "capacete" anda junto com "ESP32" e "LED" no seu mundo. Com a chave do Gemini, junta os embeddings do Google |
| "Jarvis, organiza as fotos da pasta Imagens" | **Missão**: copia para Ano/Mês pela data da foto (mover pede confirmação e dá para desfazer) |
| "Jarvis, monitora o preço do PS5 por uma semana" | **Missão** de dias: consulta de 3 em 3 h e avisa no menor preço / no preço alvo |
| "Jarvis, converte todos os vídeos da pasta Vídeos" | **Missão**: tudo para MP4 numa pasta "convertidos" (os originais ficam) |
| "Jarvis, abre o painel de missões" | Painel **MISSÕES**: progresso, pausar, continuar, cancelar. Fechou o JARVIS ou reiniciou o PC? Elas voltam de onde pararam |
| "Jarvis, o que eu tô fazendo agora?" | **Estado do mundo**: hora, se você está jogando, programando, editando, numa chamada, numa live, assistindo ou longe; se tem música. Todo aviso consulta isso |
| "Jarvis, o que eu perdi?" | **Central de avisos**: o urgente fala na hora (internet caiu, temperatura crítica); o normal espera uma brecha; o sem importância vira resumo: "Enquanto você jogava: 2 downloads terminaram e 1 alerta de RAM" |
| "Jarvis, me dá rimas com 'impossível'" / "grava um take num trap" | **Estúdio de rap**: rimas, beat em loop, conta 1 compasso e grava a sua voz por cima; salva a mixagem e a voz em Música\JARVIS\takes (use fone) |
| "Jarvis, guarda esse recado pro meu eu daqui 1 ano" | **Cápsula do tempo com a sua voz**: grava e, no dia, toca o áudio |
| (à noite) / "Jarvis, vamos fazer o diário" | **Diário por entrevista**: "como foi o seu dia?" — você conta falando; depois: "o que eu estava fazendo em novembro do ano passado?" |
| "Jarvis, como está a segurança?" | **Segurança que aprende o seu PC**: quanto sobe pela internet em cada hora, que programas rodam e de onde, portas, quem conecta de fora. Avisa o que foge do padrão: "um programa enviou 2 GB às 3h da manhã. Isso nunca aconteceu antes." "Isso é normal" ensina |

Tudo local, em `memory/` (evolucao.json, memoria_grafo.db, rede_memoria.npz, missoes.json,
diario.json, seguranca_padrao.json). A evolução só muda o JEITO de responder, nunca as regras de
segurança; e o estado do momento entra nas instruções a cada conversa nova.

## 📞 Novidades da 2.3 — WhatsApp pessoal e ligações

| Diga | O que acontece |
|---|---|
| "Jarvis, o que me mandaram no whats?" | Resumo das conversas **não lidas** (não marca como lida; grupos ficam de fora) |
| "Jarvis, o que a Ana falou?" | Lê e resume a conversa com a Ana (aparece na tela também) |
| "Jarvis, manda pra Ana que eu chego às 8" | Manda **com as suas palavras**, sem 🤖, depois que você aperta CONFIRMAR |
| "Jarvis, responde a Ana por mim" | **Rascunho** escrito como se fosse você; "aprovar 3" manda, "editar 3 …" troca |
| (modo pessoal ligado) | Quando alguém te escreve, o JARVIS avisa e já deixa um rascunho para você aprovar (no PC ou no seu chat "Você") |
| "Jarvis, libera resposta automática para a minha mãe" | Para os contatos liberados ele **responde sozinho**, sempre como "🤖 Assistente de <seu nome>:", sem prometer nada nem contar nada seu |
| "Jarvis, modo ausente por 2 horas" | Responde **todas** as conversas privadas como seu assistente até acabar o tempo |
| "Jarvis, liga a secretária do whats" | Ligações no WhatsApp são **recusadas** e a pessoa recebe "não pode atender agora, quer deixar recado?"; o recado (texto ou áudio, que vira texto) chega para você |
| "Jarvis, tem recado?" | Lista os recados (WhatsApp e telefone) |
| "Jarvis, liga o atendimento de ligações" | O **número da Twilio atende**: você (do seu número + **PIN**) conversa com o JARVIS por voz com todas as ferramentas; qualquer outra pessoa fala com a **secretária**, que anota o recado e te avisa |

Por que a ligação de VOZ é pela Twilio e não pelo WhatsApp: o WhatsApp Web (o que a ponte usa)
não tem áudio, então ninguém consegue atender uma chamada por ele. A secretária do WhatsApp
resolve o "atender" por mensagem; a Twilio resolve por voz.

**Segurança:** ler e responder suas conversas só com o modo pessoal ligado (⚙ → WhatsApp do
JARVIS); resposta automática só para quem você liberou ou no modo ausente, com freio (1 a cada
20 s, 6 por hora por conversa) e nunca para outro robô. No telefone, o número de quem liga dá
para falsificar, por isso o JARVIS só obedece depois do **PIN**; cada chamada da Twilio é
conferida pela assinatura (`X-Twilio-Signature`). ⚠️ Automação do WhatsApp Web não é oficial:
use com calma.

## 🔧 Novidades da 2.2

| Diga | O que acontece |
|---|---|
| "Jarvis, toca Kaiser" / "abre o player" | Abre a tela **Tocando agora**: capa, música, artista, barra de tempo, ⏮ ⏯ ⏭, aleatório, repetir, volume, curtir, **suas playlists** e busca (clique para tocar, ＋ para a fila) |
| "Jarvis, liga o WhatsApp" | Abre a janela do WhatsApp com o andamento (instalando → abrindo → **QR code ao vivo** → conectado) e o erro, se houver. Usa o Edge do Windows: não baixa mais os 150 MB |
| "Jarvis, olha minha tela" | **Tela ao vivo**: ele acompanha a tela (~1 quadro/s, 10 min) e responde sobre o que aparece, sem print |
| "Jarvis, me acorda às 7h com Kaiser" | **Despertador musical** com volume subindo devagar |
| "Jarvis, para a música daqui a 30 minutos" | **Timer de sono**: abaixa devagar e para |
| "Jarvis, música para focar" / "pra treinar" | **Música por humor ou atividade** |
| "Jarvis, toca a rádio do meu gosto" | **Rádio JARVIS** misturando os artistas que você mais ouve |

**Correção:** com mais de 140 ferramentas, o começo de cada conversa ficava pesado demais para o
Gemini. Agora só as 80 mais usadas vão como ferramenta própria e as outras continuam
funcionando por uma ferramenta de apoio (`core/orcamento_ferramentas.py`). O limite muda com
`"limite_ferramentas"` no `config/api_keys.json`.

## 📱 Novidades da 2.1 — JARVIS só no celular

A pasta `celular/app` é o JARVIS que roda **inteiro no celular**: você publica os 4 arquivos de
graça (GitHub Pages) uma vez, instala como app e pronto, o PC pode ficar desligado. Conversa
por voz (com modo **mãos livres**), **memória** e notas guardadas no celular, pesquisa na
internet, música (Spotify/YouTube Music), WhatsApp, discador, rota, Google Agenda e lembretes.
Usa a sua chave grátis do Gemini, que fica só no aparelho. Passo a passo em
[celular/app/LEIA-ME.md](celular/app/LEIA-ME.md).

## 🎧 Novidades da 2.0

| Diga | O que acontece |
|---|---|
| "Jarvis, toca Kaiser" / "toca a playlist de treino" | **Música** no Spotify (conectado uma vez) ou no YouTube Music; pausa, próxima, volume, fila, curtir, "que música é essa?" |
| "Jarvis, me sugere uma música" | Sugere pelo **seu gosto** (lançamentos de quem você ouve, ou parecidas) |
| (sozinho, com limite e horário de silêncio) | **Companheiro**: puxa assunto, oferece música nova, lembra do projeto parado, sugere vídeo ou pausa; no PC ele fala, fora do PC manda no WhatsApp/Telegram/Discord (com botões 👍/👎 no Telegram) e aprende com o que você aceita |
| "Jarvis, liga o Telegram" / "liga o Discord" | Converse com o JARVIS por **Telegram** e **Discord** (DM), como no WhatsApp: pedidos, áudio, fotos, atalhos |
| "Jarvis, me liga às 20h" | **Ligação de verdade** (Twilio): ele fala a mensagem no seu celular |
| "Jarvis, o que você acha que eu gosto?" | Mostra o perfil de gosto que ele aprendeu (músicas, vídeos, jogos, ofertas aceitas) |
| "Jarvis, me treina no Roblox, quero passar do obby" | **Treinador**: enquanto VOCÊ joga, ele olha a tela e dá dicas; aprende o jogo de um treino para o outro. "O que eu faço agora?" dá a dica na hora |
| "Jarvis, roda a macro farm sem parar no roblox" | **Repete uma rotina** gravada, só com o jogo em frente (pausa se você trocar de janela), até F12 — ⚠️ pode banir a conta: use uma secundária |
| "Jarvis, instala o app no meu celular" | **App do JARVIS** (PWA): 📱 modo Celular conversa por voz sozinho (Gemini direto do celular, abre música, WhatsApp, discador, rota, lembretes, pesquisa); 💻 modo PC é o JARVIS completo |

O app precisa de HTTPS para o microfone e a instalação: "liga o acesso remoto" agora também liga o
HTTPS do Tailscale (`tailscale serve`, endereço `https://seu-pc.….ts.net`).

## 🦾 Novidades da 1.9 — as 14 ideias

| Diga | O que acontece |
|---|---|
| "Jarvis, liga os gestos" | ✋ mão aberta pausa a música, 👋 deslizar troca de janela, 🤏 pinça + subir/descer muda o volume, ✌ chama o JARVIS sem falar (MediaPipe, só CPU) |
| "Jarvis, onde eu parei?" | **Memória por projeto**: sabe o projeto aberto no VS Code, os arquivos em que você mexeu, o git e as suas notas; salva um resumo quando você fecha |
| "Jarvis, anota no projeto: falta o menu de transparência" | Nota guardada no projeto |
| "Jarvis, grava essa aula" → "termina a aula" | **Modo aula**: som do PC + microfone, transcrição, resumo, tópicos, conceitos e tarefas em Markdown |
| "Jarvis, me faz 5 perguntas sobre a aula de ontem" | Quiz de revisão |
| "Jarvis, volta o jarvis-br pra como estava às 15h" | **Snapshots** a cada hora (ref git escondida ou .zip), backup no pendrive/nuvem, volta com confirmação e desfazer |
| "Jarvis, como está o uso do VPS?" | **Vigia do servidor**: CPU, memória e disco pelo SSH, com alerta (além de site no ar/fora do ar) |
| "Jarvis, escreve um e-mail educado recusando…" / "escreve uma função que…" | **Ditado inteligente** no app aberto (no VS Code, na linguagem do arquivo); "digita: …" para ditado literal |
| "Jarvis, roda os testes" / "fica de olho nos testes" | **Testes comemorados**: som de vitória e o rosto comemora; se falhar, ele diz qual teste e a linha |
| (modo loja ligado) cliente pergunta "tem tamanho 4?" | **Rascunho de resposta** com o estoque do Cristal Malhas no seu WhatsApp: *aprovar 3*, *editar 3 …* ou *ignorar 3*. Nunca envia sozinho |
| (toda segunda, 8h) | **Relatório semanal da loja**: vendas, mais vendido, o que está parado e o que divulgar |
| painel do celular → 🔺 | **Holograma de pirâmide**: o rosto do JARVIS em 4 lados, espelhado, mexe a boca quando ele fala |
| "Jarvis, liga o modo DJ" | **JARVIS DJ**: entre as músicas, comenta como locutor (artista, hora, curiosidade) e abaixa só a música |
| (automático) | **XP estilo Stark**: "Parabéns, senhor. Nível 12 alcançado. Novo título desbloqueado: Engenheiro Chefe." |
| "Jarvis, liga a pausa automática" | **Pausa quando você sai** da frente da câmera e continua quando volta |
| "Jarvis, resume esse vídeo" | **Resumo do YouTube** aberto no navegador, em ~30 s (pela legenda, ou pelo Gemini) |

**Opcionais da 1.9** (o JARVIS abre sem eles):

```bash
python -m pip install mediapipe youtube-transcript-api
```

`mediapipe` liga os gestos (se o pip não achar versão para o seu Python, use o 3.12) e o
`youtube-transcript-api` lê a legenda dos vídeos (sem ele, o resumo usa o Gemini).

## 🛰 Novidades da 1.8 — modo remoto

### Acesso pela internet e a Central

| Diga | O que acontece |
|---|---|
| "Jarvis, instala o Tailscale" | Instala a VPN grátis (só os seus aparelhos enxergam o PC) |
| "Jarvis, liga o acesso remoto" | Liga o Tailscale e/ou um link `https://…trycloudflare.com` e mostra os endereços |
| "Jarvis, me dá o link do painel" | Link de entrada de uso único (10 minutos) |
| "Jarvis, desliga o acesso remoto" | Desliga o link da Cloudflare |

No painel do celular, toque em **🛰 Central**:
- **Câmeras ao vivo**: a webcam do PC e câmeras IP (RTSP/HTTP) que você cadastrar em ⚙ → *Acesso remoto*. A webcam só fica ligada enquanto você está olhando.
- **Tela do PC** ao vivo, com botão para salvar o print.
- **Aparelhos**: TV (controle com setas, OK, volume, apps), PCs (status, ligar, bloquear, reiniciar, desligar), luzes e tomadas.

O painel continua exigindo o pareamento (chave de uso único e token) e limita as tentativas. Pelo túnel da Cloudflare, o limite conta o IP real de quem tenta.

### WhatsApp

| Diga | O que acontece |
|---|---|
| "Jarvis, liga o WhatsApp" | Instala a ponte na 1ª vez (precisa do Node.js) e abre o QR code para ler no WhatsApp |
| "Jarvis, autoriza meu WhatsApp" | Mostra um código para mandar do seu WhatsApp |
| "Jarvis, me manda no whats …" / "manda uma foto da câmera no meu whats" | Manda para você |

Pelo WhatsApp você conversa com o JARVIS como na voz ("liga a TV da sala", "como está o PC?"),
com as mesmas ferramentas. As respostas voltam por texto e, por padrão, **não** são faladas em
casa. Atalhos: *foto*, *foto 2*, *tela*, *status*, *link*, *câmeras*, *confirmar*, *cancelar*,
*ajuda*. Áudio é transcrito e foto com pergunta é explicada. Os avisos (Sentinela, alertas)
também chegam por lá.

⚠️ Usa o WhatsApp Web (`whatsapp-web.js`), **não** a API oficial: a Meta pode limitar ou banir o
número. Prefira um chip só para o JARVIS. Com o seu número, fale com ele no chat "Você"; as suas
outras conversas não são lidas. Detalhes em [whatsapp_ponte/LEIA-ME.md](whatsapp_ponte/LEIA-ME.md).

## 🎮 Novidades da 1.7

### Arcade J.A.R.V.I.S

| Diga | O que acontece |
|---|---|
| "Jarvis, abre os jogos" | Abre o **Arcade**: uma janela com 14 jogos clicáveis e o placar de cada um |
| "Jarvis, abre o campo minado" | Já abre direto no jogo (vale para qualquer um da lista) |
| "Jarvis, vamos jogar xadrez" | Xadrez contra o **motor próprio** do JARVIS (fácil, médio, difícil); clique no Arcade **ou** fale "cavalo f3": é a mesma partida |
| "Jarvis, vamos jogar damas" | Damas com regras brasileiras, também no Arcade |
| "Jarvis, jogo da velha" → "no centro" | Jogo da velha por voz (no difícil ele nunca perde) |
| "Jarvis, lig 4" → "coluna 4" | Lig 4 por voz |
| "Jarvis, forca de frutas" → "letra a" | Forca com palavras brasileiras por tema |
| "Jarvis, adivinha o número" | Ele pensa num número e diz "maior" ou "menor" |
| "Jarvis, pedra, papel ou tesoura" | Ele aprende os seus padrões e tenta prever a sua jogada |
| "Jarvis, meu placar" | Vitórias, derrotas e recordes de todos os jogos |

No Arcade: **xadrez**, **damas**, **jogo da velha**, **lig 4**, **campo minado**, **2048**,
**cobrinha**, **blocos** (estilo Tetris), **quebra-tijolos**, **memória**, **forca**, **genius**,
**pedra-papel-tesoura** e **reflexo**. Abre numa janela própria do Edge/Chrome (sem abas),
funciona com mouse, teclado e toque, tem som (botão 🔊) e não precisa de internet. O
servidor do Arcade só escuta no próprio PC (127.0.0.1) e pede um código de sessão.

O xadrez agora usa um motor escrito para o projeto (`plugins/_xadrez_motor.py`: roque, en
passant, promoção, xeque-mate, afogamento, busca alfa-beta). O `python-chess` não é mais
necessário.

## 📡 Novidades da 1.6

### Aparelhos da rede: ligar, desligar e controlar

| Diga | O que acontece |
|---|---|
| "Jarvis, procura os aparelhos da rede" | Varre a sua rede (portas conhecidas + SSDP + ARP) e diz o que achou: PCs, TVs, celulares, Chromecast, luzes Tuya, impressoras |
| "Jarvis, o 3 é a TV da sala" | Dá um nome ao aparelho da lista |
| "Jarvis, liga o PC do quarto" / "desliga o PC do quarto" | Liga pela rede (Wake-on-LAN) e desliga/reinicia/suspende/bloqueia pelo **agente** (desligar e reiniciar pedem CONFIRMAR) |
| "Jarvis, abre o Chrome no PC da sala" / "roda ipconfig no PC da sala" | Abre programas e sites, fecha programas, mostra mensagem, tira print e roda comandos (com CONFIRMAR e verificação recente) |
| "Jarvis, como está o PC do quarto?" | CPU, RAM, há quanto tempo está ligado, quem está usando |
| "Jarvis, desliga a TV" / "aumenta o volume da TV" / "abre o YouTube na TV" | **Roku/TCL** sem instalar nada; **Samsung** (a TV pede "Permitir" na 1ª vez); **LG** com `pywebostv`; **Android TV** pelo ADB |
| "Jarvis, instala o ADB" → "conecta o ADB no celular" | Celular Android e Android TV pelo Wi-Fi: telas, teclas, apps, digitar, print, bateria e comandos |
| "Jarvis, desliga tudo" | TVs e luzes de uma vez (os PCs ficam de fora: um por vez, com confirmação) |

**O agente dos outros PCs** está na pasta `agente_pc`: copie para o outro PC (só precisa do
Python), dê dois cliques em `instalar_agente.bat` e pareie com a chave que aparecer. Cada pedido
vai assinado com a chave (HMAC), com hora e número único, e fica anotado no `agente.log`.

### As 42 ideias

| Diga | O que acontece |
|---|---|
| (abrir o JARVIS) | **Boot teatral** agora diz a rede e as **pendências** (tarefas, aniversários, cápsulas, cuidados do dia) |
| 🥽 no painel do celular | **Realidade aumentada**: câmera do celular com marcações holográficas (o próprio celular reconhece os objetos); "Perguntar ao JARVIS" explica o que é. Precisa do painel em HTTPS |
| ⚙ ENGINE & PROVIDERS → Fish Audio | **Voz do Fish Audio** (inclusive clonada) com o avatar mexendo a boca junto |
| "Jarvis, modo armadura" / 🦾 no celular | **Status do traje**: bateria e sinal do celular, CPU, RAM, GPU, temperatura, integridade e clima |
| 🚗 no celular / "Jarvis, modo carro" | **Modo carro**: tela de um botão só, o celular lê as respostas em voz alta; com o ADB, lê suas mensagens novas e ajuda a responder |
| (de madrugada) / "como foi a noite?" | **Turno da noite**: roda os testes dos seus projetos, confere pacotes vulneráveis (OSV) e desatualizados; relatório de manhã |
| "Jarvis, me explica o repositório dono/projeto" | Baixa do GitHub (ou lê uma pasta), mapeia e **explica a arquitetura** por voz |
| "Jarvis, gera testes para C:\…\calculos.py" | **Gerador de testes**: escreve, roda numa pasta isolada e salva sem sobrescrever nada |
| "Jarvis, documenta o projeto …" / "escreve as docstrings do …" | **Documentação automática**: README_GERADO.md e docstrings (com CONFIRMAR, cópia e desfazer) |
| "Jarvis, o que mudou em você essa semana?" | **Changelog falado** |
| "Jarvis, mostra meu painel de programação" | **Painel dev**: horas codando por dia e projeto, commits e linguagens, com gráficos |
| "Jarvis, cria um projeto Flask com login chamado loja" | **Gerador de projetos**: Flask com login, FastAPI, linha de comando, PyQt, site — ou a IA monta outro tipo |
| "Jarvis, isso é golpe? …" | **Detector de golpe**: Pix, "número novo", falso banco/entrega, links disfarçados — sem abrir o link |
| "Jarvis, minha senha foi vazada?" | **Senha vazada** pelo Have I Been Pwned, digitada numa caixinha local (a senha não sai do PC) |
| "Jarvis, vigia meu VPS root@1.2.3.4" | **Guarda do VPS**: tentativas de invasão por SSH, IPs, logins de IP novo (alerta) e bloquear IP |
| "Jarvis, modo convidado" | **Modo convidado**: visita conversa, mas sem as suas memórias e sem nada pessoal; para sair, prova que é você |
| "Jarvis, aprende meu jeito de escrever com a conversa exportada" | **Responder no seu estilo**: sugestões de resposta que parecem suas |
| "Jarvis, o que rolou no grupo da família desde ontem?" | **Resumo de grupo** a partir da conversa exportada do WhatsApp |
| "Jarvis, o aniversário da minha vó é 12 de março" | **Aniversários**: avisa no dia e uma semana antes; escreve a mensagem no seu estilo |
| "Jarvis, grava a ata da reunião" → "termina a ata" | **Ata de chamadas**: grava o som do PC e o seu microfone, transcreve e lista decisões e tarefas |
| "Jarvis, simula uma entrevista para desenvolvedor Python júnior" | **Entrevista por voz**, com feedback, nota e vícios de fala |
| "Jarvis, gera meu portfólio do GitHub usuario" | **Portfólio e currículo** em HTML a partir dos seus repositórios |
| "Jarvis, procura vagas de programador júnior em Goiânia" | **Caçador de vagas**: todo dia, avisando só as novas |
| "Jarvis, vamos praticar inglês, nível iniciante" | **Professor de inglês**: conversa, corrige e transforma os erros em cartões |
| "Jarvis, me ensina errado sobre …" | **Me ensina errado**: ache o erro proposital |
| "Jarvis, rima com coração" / "analisa minha letra" | **Parceiro de rima**: rimas, métrica e esquema de rimas |
| "Jarvis, faz um beat de trap" | **Gerador de beats** (trap, boom bap, lo-fi, funk, drill) em WAV, e MIDI com o `mido` |
| "Jarvis, começa uma aventura de fantasia" | **Mestre de RPG** com dados e fichas de verdade |
| "Jarvis, faz uma thumbnail: …, estilo tech" | **Thumbnails** e capas de post e story, com foto |
| "Jarvis, conta uma história para dormir" | **Contador de histórias** com som ambiente e efeitos gerados na hora |
| "Jarvis, cápsula do tempo para daqui a 1 ano: …" | **Cápsula do tempo**, entregue na data |
| "Jarvis, me ajuda a decidir entre …" | **Conselheiro de decisão**: prós, contras, cenários "e se" e matriz com os seus pesos |
| "Jarvis, quanto XP eu tenho?" / "treinei 40 minutos" | **Gamificação**: XP, níveis e conquistas com o que você já faz |
| "Jarvis, o que eu fiz em outubro?" | **Retrospectiva** do mês, da semana ou do ano |
| "Jarvis, cuidados da vó: remédio às 8h e às 20h" | **Modo cuidador**: horários, consultas e checklist, com aviso por voz e no celular |
| (vigia de preço) | Já existia desde a 1.4: "me avisa quando a RTX baixar de R$ 1.500" |
| "Jarvis, vamos jogar damas" / "xadrez" → "c3 d4" / "cavalo f3" | **Damas** (regras brasileiras) e **xadrez** (motor próprio desde a 1.7) por voz |
| "Jarvis, quiz geek de animes" | **Quiz geek** com pontos e sequência |
| "Jarvis, modo debate: eu acho que …" | **Modo debate**: ele defende o lado oposto |
| "Jarvis, ativa o eu virtual" | **Eu virtual**: ele responde como você responderia |
| "Jarvis, narra o meu dia" | **Narrador da vida**, estilo documentário |
| "Jarvis, decide o que eu janto" | **Roleta de rolê** que aprende com "gostei" e "não gostei" |

**Opcionais da 1.6** (o JARVIS abre sem eles):

```bash
python -m pip install mido pywebostv
```

O xadrez não precisa mais de nada (motor próprio na 1.7). `mido` grava o MIDI dos beats e
`pywebostv` controla TVs LG. A ata de chamadas usa o `soundcard` (opcional da 1.4). O ADB
para Android é baixado pelo próprio JARVIS ("Jarvis, instala o ADB").

---

## 🔐 Novidades da 1.5

### Verificação sem ficar provando quem você é

O JARVIS confere quem está falando **por trás**, sem senha e sem "repita a frase":

| Quando | O que conta como "é você" |
|---|---|
| Ao abrir o JARVIS | Ele olha a câmera uma vez, em silêncio. Se você entrou no Windows há menos de 5 min, isso já basta |
| Durante o dia | **Sessão confiável de 8 h**, que acaba no Win+L, quando o PC suspende ou se a câmera vir um desconhecido sem você |
| Win+L e desbloquear | Desbloquear o Windows **conta como verificação** |
| No meio do pedido | A **voz do próprio pedido** é comparada com a sua (opcional, com o resemblyzer) |
| Celular ou pulseira | **Chave por perto**: Bluetooth (bleak) ou o celular no Wi-Fi. Você saiu com ela, a sessão fecha |

Cada comando tem um **nível**:

| Nível | Exemplos | Precisa de |
|---|---|---|
| livre | música, clima, conversa, pesquisa, "olha isso", modo professor | nada |
| sensível | mensagens, e-mail, VPS, arquivos, memória, loja, macros | sessão confiável (ou provar na hora) |
| crítico | desligar o PC, limpeza, instalar ferramenta, aplicar correção, mudar a segurança, desligar a Sentinela | uma prova forte (rosto, voz ou desbloqueio) dos últimos 15 min |

Se a prova faltar, ele tenta **na hora** (olha a câmera ou confere a voz do pedido) e só
recusa se não der, dizendo o que fazer. Sem nada cadastrado, vale o login do Windows,
como antes. Pedidos que vêm do celular pareado e do capacete já têm a chave deles.
Mensagens **de fora**, como o chat da live, **nunca viram ação**: logo depois de ler uma,
só passa o que é livre, até você falar ou digitar de novo.

| Diga | O que acontece |
|---|---|
| "Jarvis, status da verificação" | Se a sessão está aberta, por quê e até quando |
| "Jarvis, me verifica" / "encerra a sessão" | Prova agora (câmera/voz) / fecha a sessão |
| "Jarvis, quais comandos são protegidos?" / "deixa o clima só para mim" | Mostra os níveis / muda o nível de um comando |
| "Jarvis, aprende minha voz" | Cadastro **passivo**: converse normal por uns minutos (25 s de fala bastam) |
| "Jarvis, procura minha pulseira" → "usa a Mi Band como chave" | Escolhe o celular/pulseira que vira a sua chave |

### As 14 ideias

| Diga | O que acontece |
|---|---|
| "Jarvis, vigia o PC" | **Sentinela**: 30 s para você sair. Alguém mexeu ou um rosto desconhecido? Foto no seu celular (ntfy) e, se você ligar a opção, uma **ligação**. Também arma sozinha quando a chave ou o geofence dizem que você saiu (ou no Win+L, se escolher) e desarma quando reconhece você |
| "Jarvis, quais hábitos você notou?" | **Hábitos**: "todo dia útil às 8h10 você abre o WhatsApp". Na hora ele oferece abrir; "abre sozinho" deixa automático |
| "Jarvis, liga a memória de tela" → "onde eu vi aquele orçamento ontem?" | **Memória de tela**: a cada 1 min guarda o título, uma miniatura e o texto da janela ativa (o texto precisa do OCR opcional da 1.4, o `rapidocr-onnxruntime`) e busca por palavra e período. Pula janelas cujo título fala de banco, senha, Pix ou navegação privada (a lista muda em ⚙ CONFIG); "pausa" e "apaga a de hoje" |
| "Jarvis, observa como eu faço o relatório" → (você faz) → F9 → "Jarvis, faz o relatório" | **Aprende olhando**: grava cliques (com um recorte da tela para achar o botão de novo), textos e atalhos. A 1ª repetição pede CONFIRMAR; F12 para |
| "Jarvis, liga o ouvido ambiente" / "aprende esse som: campainha" | **Ouvido ambiente**: alarmes e bipes, os sons que você ensina e barulho forte quando você está fora. Com o YAMNet (opcional): campainha, fumaça, vidro, bebê, cachorro, sirene |
| "Jarvis, testa a ligação" | **Ligação de verdade** (Twilio): alertas críticos tocam o seu celular com voz em português. Máximo 1 a cada 10 min e 5 por dia |
| "Jarvis, vigia o site meusite.com.br" / "vigia a VPS 1.2.3.4 porta 22" | **Servidores**: confere a cada minuto. Três falhas seguidas, aviso urgente no celular (e ligação, se configurada). Avisa também quando volta |
| "Jarvis, liga o detector de postura" → "calibra a postura" | **Postura e cansaço**: curvado, perto demais da tela, cabeça torta, bocejos e 90 min sem pausa. Só números, nada gravado |
| "Jarvis, como você está hoje?" / "fica sempre formal" | **Humor interno**: formal de manhã, sarcástico depois de 6 h programando, animado em dia de vendas, cuidadoso com muitos erros, calmo de madrugada |
| "Jarvis, vamos programar: uma função que calcula o troco" → "adiciona: …" → "pronto" | **Ditado de código**: gera o código e os testes, roda numa pasta isolada, corrige 1 vez se falhar e salva em Documentos\JARVIS\codigo |
| "Jarvis, analisa seus erros" → "mostra a correção 1" → "aplica a correção 1" | **JARVIS que se corrige**: junta os erros reais (com traceback), propõe uma correção pequena, testa numa CÓPIA e só aplica com CONFIRMAR, guardando cópia (.bak) e com "desfaz" |
| "Jarvis, configura o geofence" | **Geofence** pelo Termux:API no celular: saiu de casa, a sessão fecha e a Sentinela arma; chegou, boas-vindas e (se quiser) um protocolo. Script em `celular/termux/` |
| "Jarvis, cria 8 cartões sobre listas em Python" → "me pergunta" | **Modo professor**: repetição espaçada (SM-2). Ele pergunta, corrige e reagenda; às 19h30 oferece a revisão do dia |
| (abrir um jogo) / "comenta minha partida" / "lê o chat da minha live, canal X" | **Companheiro de jogo**: avisa a cada hora de jogo (e no seu limite diário), comenta a partida olhando a tela e lê o chat da Twitch em voz alta (sem links, 1 a cada 8 s) |
| (pergunta importante) / "pede uma segunda opinião" | **Duas opiniões**: em saúde, dinheiro, leis, segurança, ações irreversíveis e arquitetura, um revisor cético confere a resposta antes de você ouvir |

**Começam desligados** (você liga quando quiser): memória de tela, ouvido ambiente,
postura e ligação. Os outros ficam leves em segundo plano e cada um desliga em 🧩 PLUGINS.

**Precisam da chave do Gemini:** ditado de código, as correções da auto-melhoria (sem a
chave ela só lista e explica os erros), a segunda opinião e "comenta minha partida".
O resto funciona sem IA.

**Opcionais da 1.5** (o JARVIS abre sem eles; os comandos completos estão no `INSTALAR.txt`):

```bash
python -m pip install webrtcvad-wheels librosa scipy torch   # voz do dono, parte 1
python -m pip install resemblyzer --no-deps                  # voz do dono, parte 2
python -m pip install bleak                                  # celular/pulseira como chave (Bluetooth)
python -m pip install ai-edge-litert                         # YAMNet no ouvido ambiente
```

Depois do `ai-edge-litert`, diga **"Jarvis, baixa o modelo de sons"** para buscar o YAMNet
(ou baixe à mão para `config\modelos_som\yamnet.tflite`; o comando está no `INSTALAR.txt`).
A ligação usa uma conta da Twilio, configurada em ⚙ CONFIG. DE PLUGINS → Ligação.

---

## 🧠 Novidades da 1.4

Regra de todas: **funcionam sem IA** (por regras, estatística e análise de código) e
**ficam melhores com a chave do Gemini**. Nada destrutivo acontece sem passar pelo
guardião e pelo botão CONFIRMAR.

### O cérebro (as 15 ideias)

| Diga | O que acontece |
|---|---|
| "Jarvis, se eu abrir o Valorant e gravar a tela, o PC aguenta?" | **Gêmeo digital**: prevê RAM e CPU com o que ele aprendeu do seu PC e sugere o que fechar |
| "Jarvis, por que o PC está lento?" | **Hipóteses concorrentes**: várias causas com % de confiança, o que pesa a favor e contra, e como testar |
| "Jarvis, simula a limpeza" / "simula fechar o Chrome" | **Simulador de futuros**: melhor caso, provável e pior caso — sem fazer nada |
| "Jarvis, lembra que eu prefiro tema escuro" / "o que você sabe sobre o site?" | **Memória com esquecimento inteligente**: cada lembrança perde confiança com o tempo e avisa quando pode estar velha |
| "Jarvis, convoca o conselho: quero automatizar o relatório da loja" | **Conselho de agentes**: Planejador, Programador, Pesquisador, Revisor e Gestor de Memória opinam separados; você vê onde discordam e o plano final |
| "Jarvis, testa no laboratório trocar WORKERS=4 por 8 no config.py" | **Laboratório**: roda numa cópia do projeto, antes e depois, e compara tempo e testes |
| "Jarvis, cria um plugin que me avisa quando o Free Fire atualizar" | **Criador de ferramentas**: escreve o plugin, testa numa cópia do JARVIS, mostra o código e só instala com CONFIRMAR (ativa na hora) |
| "Jarvis, que rotinas eu repito?" | Acha sequências que você faz sempre e oferece juntar numa ferramenta |
| "Jarvis, tem alguma anomalia?" / "o que é normal no meu PC às 15h?" | **Radar de anomalias**: aprende o normal do seu PC e do JARVIS (por hora do dia) e investiga o que foge |
| "Jarvis, o que você aprendeu com as últimas tarefas?" | **Memória contrafactual**: "o protocolo levou 14 s; em paralelo levaria 6 s" — e aplica a lição |
| "Jarvis, se eu mudar o _comum, o que quebra?" | **Mapa vivo de dependências**: quem usa o quê, ciclos de import e testes que cobrem; mapa visual em HTML |
| "Jarvis, quais oportunidades você viu?" / "aceita a 2" | **Detector de oportunidades**: rotina → ferramenta, pedido no mesmo horário → agenda, Downloads bagunçado, disco cheio… |
| "Jarvis, isso é seguro?" / "nunca apague nada em Documentos" | **Guardião de decisões**: risco, se dá para desfazer e o que é afetado; suas regras valem para tudo |
| "Jarvis, procura os arquivos do orçamento, resume e gera um relatório" | **Habilidades combináveis**: cada passo entrega o resultado ao próximo; "salva essa sequência como relatório semanal" |
| "Jarvis, o que aconteceu ontem à tarde?" / "por que travou às 15h?" | **Reconstrução**: linha do tempo de tudo que ficou registrado, separando FATOS de HIPÓTESES |
| "Jarvis, o que eu faço agora?" / "tenho 30 minutos" / "estou bloqueado no deploy" | **Prioridades adaptativas**: reordena pela importância, prazo, tempo livre e estado do PC, e aprende quanto você erra nas estimativas |

### O resto da 1.4

| Diga / Faça | O que acontece |
|---|---|
| "Jarvis, olha isso" ou **Ctrl+Alt+J** | Captura **só a janela ativa** (VS Code, terminal, navegador) e explica — erro, tela, código |
| (um Traceback aparece) | O rosto pergunta baixinho: "Senhor, quer que eu explique esse erro?" |
| "Jarvis, o que eu fiz hoje?" | "4h no VS Code, 1h20 no YouTube e 40 min na Cristal Malhas" |
| "Jarvis, quanto tempo gastei no projeto Jarvis essa semana?" | Total por dia + gráfico na aba **📊 MONITOR → MEU DIA** |
| (voltar depois de 1 h fora) | "Bem-vindo de volta. Dois downloads terminaram, a internet caiu 3 minutos e um aparelho novo entrou na rede." |
| (abrir o JARVIS) | **Boot cinematográfico**: som de inicialização, diagnóstico do traje e saudação pelo horário e clima |
| "Jarvis, liga a legenda" | Traduz o **áudio do PC** (vídeo, call, live) e mostra no balão do rosto |
| (soltar a foto da roupa na pasta) / "faz o post da última foto" | **Foto → post**: descrição, tamanhos do seu estoque, legenda, hashtags e roteiro de Reels |
| "Jarvis, monta o vídeo do produto" | **Montador**: corta silêncios, junta, 9:16, logo, legenda do Whisper, MP4 pronto |
| "Jarvis, quais datas comerciais estão chegando?" / "monta a campanha do Dia das Crianças" | **Calendário infantil** com aviso 3 semanas antes; "quais tamanhos estão acabando?" |
| "Jarvis, chama a Friday" / "volta o Jarvis" | **F.R.I.D.A.Y**: outra voz e outro jeito de falar (também dentro de protocolos) |
| "Jarvis, configura o capacete" | **Capacete ESP32**: o mesmo JARVIS num capacete — código e esquema em `esp32/capacete/` |
| "Jarvis, me avisa quando a RTX 3060 baixar de R$ 1.500" | **Vigia de preço**: confere 1× por dia e avisa por voz e no celular |
| "Jarvis, liga a luz do quarto" / "cena dormir" | **Casa inteligente** Tuya/Positivo pela rede local (passo 'casa' nos protocolos) |
| "Jarvis, testa a notificação no celular" | Push no celular pelo app grátis **ntfy** (para todos os avisos acima) |

**Protocolos ganharam 4 passos:** `persona`, `casa`, `energia` (com confirmação) e `ferramenta`
(qualquer ferramenta do JARVIS). Exemplo de "protocolo dormir": `casa → cena dormir`,
`mudo → sim`, `energia → desligar`.

**O que roda sozinho (tudo leve):** linha do tempo (5 s), vigia de erros (área de
transferência a cada 2 s), radar (5 min), gêmeo digital (1 min), fotos da loja (30 s),
calendário e oportunidades (1×/dia), vigia de preço (1×/dia). Cada um desliga em 🧩 PLUGINS.

**Opcionais da 1.4** (o JARVIS abre sem eles):

```bash
python -m pip install soundcard faster-whisper rapidocr-onnxruntime
winget install Gyan.FFmpeg
```

`soundcard` liga a legenda ao vivo. `faster-whisper` faz a legenda sem internet e a legenda
dos vídeos. `rapidocr-onnxruntime` deixa o vigia de erros ler a tela do terminal. O
`ffmpeg` é usado pelo montador de vídeo. A casa inteligente usa o `tinytuya`, que já vem
no `requirements.txt`.

---

## 🧑 Novidade da 1.3: rosto flutuante

O rosto animado do JARVIS numa janelinha **sempre no topo**, num canto da tela,
para ele ficar conversando com você enquanto você programa ou trabalha. A boca
acompanha a fala, a aura reage à sua voz, um pontinho mostra o estado (ouvindo,
falando, pensando, mutado) e uma bolha mostra a última frase, sua ou dele.

| Faça / Diga | O que acontece |
|---|---|
| CONTROLES → 🧑 ROSTO FLUTUANTE | Liga e desliga |
| Minimizar o JARVIS | O rosto aparece sozinho no canto; ao voltar, some |
| "Jarvis, fica no canto da tela" / "esconde o rosto" | Mesma coisa por voz |
| "Jarvis, vai para o canto esquerdo" / "fica maior" | Posição e tamanho por voz |
| Arrastar | Move (a posição fica salva) |
| Rodinha do mouse | Aumenta / diminui |
| Clique duplo | Abre a janela grande |
| Botão direito | Canto, tamanho, transparência, legenda, mutar, fechar |

Ele não escuta nada sozinho: usa o mesmo som e o mesmo estado que o HUD já
calcula, então nunca fica fora de sincronia. Parado, cai para 15 quadros por segundo.

## 🆕 Novidades da 1.2

### 📊 Monitoramento completo
Abra pela gaveta **CONTROLES → 📊 MONITOR**: abas VISÃO GERAL (cartões com mini
gráficos), PROCESSOS (tabela ordenável estilo Gerenciador de Tarefas, com
finalizar, suspender, retomar, prioridade e abrir local), REDE, DISCOS e
HISTÓRICO.

| Diga | O que acontece |
|---|---|
| "Jarvis, como está o PC?" | CPU (total, por núcleo, frequência, temperatura), RAM e swap, GPU, discos, rede, bateria |
| "Jarvis, o que está pesando?" | Quem mais usa CPU, memória e disco agora |
| "Jarvis, mostra o top de processos por memória" | Tabela dos 25 que mais usam (CPU, RAM, disco ou rede) |
| "Jarvis, como está a internet?" | IP local e público, gateway, DNS, Wi-Fi e sinal, ping no roteador, Google e Cloudflare |
| "Jarvis, quem está usando minha rede?" | Aparelhos da SUA rede local (no máximo a /24 do seu IP) |
| "Jarvis, faz um teste de velocidade" | Download, upload e ping (servidor da Cloudflare, ~15 s) |
| "Jarvis, como estão os discos?" | Espaço por partição e saúde SMART |
| "Jarvis, como foi o PC hoje?" / "essa semana?" | Médias, picos, internet usada, quedas e alertas do período |
| "Jarvis, suspende o Chrome" / "finaliza o processo 1234" | Ações em processos (finalizar pede confirmação) |

**Alertas falados**, todos configuráveis: CPU acima de 90% por 30 s, RAM acima
de 85%, disco com menos de 10% livre, temperatura acima de 85 °C, internet caiu
ou voltou, ping alto e bateria baixa. Cada alerta vai para o histórico em
`memory/monitor.db` (uma amostra por minuto, guardada por 30 dias).

**Uma fonte só de dados:** o HUD, o painel, os alertas e o `system_status` leem
o mesmo coletor (`core/telemetria.py`). Ele gastou **0,4% de um núcleo** nos
testes; as leituras caras (GPU, temperatura, ping, SMART) ficam em ciclos lentos
ou só acontecem quando você pede.

### 🖥 Controle total do PC
| Diga | O que acontece |
|---|---|
| "Jarvis, abre o zap" / "abre o vs code" / "abre o lol" | Lançador com apelidos e nome aproximado: Menu Iniciar, Área de Trabalho, Program Files, Microsoft Store, Steam e Epic |
| "Jarvis, abre o CMD como administrador" | Pede confirmação e depois o aviso do Windows (UAC) |
| "Jarvis, fecha o Spotify" / "reinicia o Discord" / "traz o Chrome para frente" | Fecha educadamente (como o X), reinicia ou foca |
| "Jarvis, o apelido do Photoshop é foto" | Cria apelido (fica em `config/apelidos_apps.json`) |
| "Jarvis, minimiza tudo" / "maximiza essa janela" | Janelas: minimizar, maximizar, restaurar, fechar |
| "Jarvis, manda o Chrome para o outro monitor" | Move a janela de monitor |
| "Jarvis, põe o VS Code e o Chrome lado a lado" | Divide a tela entre as duas |
| "Jarvis, deixa a calculadora sempre no topo" | "Sempre no topo" liga e desliga |
| "Jarvis, desliga o PC em 30 minutos" / "cancela o desligamento" | Agendamento (com confirmação) |
| "Jarvis, suspende / hiberna / bloqueia / reinicia o PC" | Energia, tudo com confirmação (bloquear é na hora) |
| "Jarvis, volume do Spotify em 30" | Volume por aplicativo |
| "Jarvis, passa o som para o fone" | Troca a saída de som (fone, caixa, TV/HDMI, Bluetooth) |
| "Jarvis, liga o modo escuro" / "brilho em 60" | Tema e brilho, com desfazer |
| "Jarvis, muda a resolução para 1920 por 1080" | Volta sozinho em 20 s se você não disser "manter resolução" |
| "Jarvis, digita: bom dia, equipe!" / "aperta ctrl shift esc" | Teclado (com acentos) e atalhos |
| "Jarvis, procura o arquivo orçamento" / "procura 'Cristal' dentro dos documentos" | Busca por nome ou por conteúdo; "abre o primeiro" |
| "Jarvis, quais os maiores arquivos dos Downloads?" / "arquivos recentes" | Maiores e mais recentes |
| "Jarvis, desliga o Bluetooth" / "conecta no Wi-Fi da loja" | Rádios e redes salvas (desligar o Wi-Fi pede confirmação) |
| "Jarvis, limpa o cache de DNS" / "renova o IP" | Rede |
| "Jarvis, o que abre com o PC?" / "tira o Discord da inicialização" | Programas de inicialização, com desfazer |
| "Jarvis, plano de energia alto desempenho" | Plano de energia, com desfazer |
| "Jarvis, o que tem na área de transferência?" | Lê, copia e limpa |

### 🎮 Modo jogo
| Diga | O que acontece |
|---|---|
| "Jarvis, modo jogo" | Fecha os apps pesados da sua lista, plano Alto desempenho, pausa as notificações e mostra o overlay (CPU, GPU, RAM, temperatura e FPS) |
| "Jarvis, modo normal" | Desfaz tudo: plano anterior, notificações de volta, apps reabertos |
| "Jarvis, esconde o overlay" | Só o overlay |

O FPS aparece se você instalar o **PresentMon** (gratuito, da Intel) e informar o
caminho nas configurações; o PresentMon pode pedir para rodar como administrador.

### 🧹 Limpeza do sistema
| Diga | O que acontece |
|---|---|
| "Jarvis, limpa o PC" | Prévia ("posso liberar 3,2 GB: temporários…, navegadores…, lixeira…") e botão CONFIRMAR |
| "Jarvis, limpa só os temporários" / "esvazia a lixeira" | Só aquela parte |

Só o **cache** dos navegadores (senhas, histórico e abas ficam). Arquivos
mexidos na última hora e travados por algum programa são pulados, e atalhos para
fora das pastas de limpeza nunca são seguidos. Nas configurações, dá para
escolher "lixeira" em vez de "apagar" (usa o send2trash).

### 🛡 Guarda de segurança
| Diga | O que acontece |
|---|---|
| (sozinho) | Avisa de programa novo na inicialização, conexão em porta suspeita (4444, IRC, Tor…), processo novo **sem assinatura** com muitas conexões e aparelho novo na sua rede |
| "Jarvis, verifica a segurança" | Faz todas as verificações agora |
| "Jarvis, isso é normal" | Aceita o estado atual |
| "Jarvis, o aparelho 192.168.0.15 é a TV" | Dá nome a um aparelho da rede |

Na primeira vez ela só **aprende** o que é normal no seu PC. Com o
reconhecimento facial ligado, um **desconhecido na câmera** faz a guarda
oferecer bloquear o PC (ou bloquear sozinho, se você configurar). Não é
antivírus: é um par de olhos a mais.

### ⌨️ Macros
| Diga | O que acontece |
|---|---|
| "Jarvis, grava a macro relatório" | Grava teclado e mouse |
| "Jarvis, para de gravar" (ou **F9**) | Salva em `config/macros/` |
| "Jarvis, roda a macro relatório duas vezes mais rápido" | Repete (velocidade de 0,25x a 4x, e repetições) |
| **F12** durante a reprodução | Para na hora |

⚠️ Não digite senhas enquanto grava: tudo o que você digita fica no arquivo.

### ⏰ Agendador de tarefas
| Diga | O que acontece |
|---|---|
| "Jarvis, todo dia às 8 abre o WhatsApp" | Tarefa diária |
| "Jarvis, toda sexta às 18h faz limpeza" | Semanal (limpeza e desligar pedem confirmação ao agendar) |
| "Jarvis, às 23h desliga o PC" | Uma vez; na hora, dá 2 minutos de aviso para cancelar |
| "Jarvis, de segunda a sexta às 9h ativa o protocolo foco" | Dias úteis |
| "Jarvis, a cada 60 minutos me lembra de beber água" | Intervalo |
| "Jarvis, quais tarefas eu agendei?" / "apaga a tarefa 2" / "pausa a tarefa da limpeza" | Gerenciar |

### 📋 Histórico da área de transferência
| Diga | O que acontece |
|---|---|
| "Jarvis, o que eu copiei?" | Os últimos itens (guarda até 50; os fixados não contam) |
| "Jarvis, cola de novo o endereço" | Acha pelo texto e cola |
| "Jarvis, fixa o segundo" / "apaga o terceiro" | Fixar e apagar |
| "Jarvis, pausa o histórico" | Para de guardar até você retomar |

Não guarda o que parece **senha** ou **chave de API**, e respeita o aviso que
gerenciadores de senha (KeePass, Bitwarden…) mandam no Windows.

### 🎥 Gravação de tela
| Diga | O que acontece |
|---|---|
| "Jarvis, grava a tela" | Tela inteira, salvo em Vídeos/JARVIS |
| "Jarvis, grava só o CapCut" | Só a janela daquele app (segue a janela se ela mudar de lugar) |
| "Jarvis, grava a tela na vertical" | Corte **9:16** para Reels/TikTok — ótimo para os vídeos da Cristal Malhas |
| "Jarvis, para a gravação" | Salva e diz o tamanho |

Usa o **ffmpeg** se estiver instalado (H.264, arquivo menor); sem ele, grava com
mss + OpenCV. Só imagem, sem som.

### 🩺 Relatório de saúde do PC
| Diga | O que acontece |
|---|---|
| "Jarvis, como está a saúde do PC?" | Nota de 0 a 100, os problemas em ordem de gravidade e o que fazer |
| "Jarvis, gera o relatório de saúde" | Também salva uma página HTML em `memory/` e abre no navegador |

Entram na nota: espaço em disco, SMART, temperatura, RAM, programas na
inicialização, dias sem reiniciar, lixo acumulado e, no Windows, dias sem
atualizar, reinício pendente, drivers com erro e o estado do Defender.

### 📥 Downloads
| Diga | O que acontece |
|---|---|
| (sozinho) | "Download concluído: catalogo.pdf" e, 2 minutos depois, move para a pasta do tipo |
| "Jarvis, organiza meus downloads" | Imagens, Vídeos, Áudios, PDFs, Documentos, Instaladores, Compactados |
| "Jarvis, abre o último download" / "o que eu baixei hoje?" | Atalhos |

Organizar só **move** (nunca apaga nem sobrescreve) e "Jarvis, desfaz" põe tudo de volta.

### 📱 Controle pelo celular
No celular (◉ CONTROLE REMOTO → QR code), toque em **📊**: status ao vivo,
discos, rede, top de processos e botões **Bloquear, Mudo, Modo jogo, Desligar,
Reiniciar, Cancelar desligamento** e **Abrir app**. Usa o mesmo login do painel.
Desligar e reiniciar dão 60 segundos para cancelar, e a página pergunta antes.

### 🍅 Foco / Pomodoro
| Diga | O que acontece |
|---|---|
| "Jarvis, começa um pomodoro" | 25 min de foco e 5 de pausa (pausa longa a cada 4); roda o protocolo Foco |
| "Jarvis, pomodoro de 50 minutos" | Foco personalizado |
| "Jarvis, quanto falta?" / "pausa o pomodoro" / "para o pomodoro" | Controle |
| "Jarvis, quantos pomodoros eu fiz hoje?" | Contagem do dia |

Durante o foco, os apps da lista (Steam, Discord, LoL…) são fechados se abrirem,
e uma janela de navegador num site da lista (YouTube, Instagram, TikTok…) é
minimizada. Sem mexer no arquivo `hosts`, então não precisa de administrador.

### 🌐 Assistente de rede
| Diga | O que acontece |
|---|---|
| "Jarvis, minha internet está lenta, por quê?" | Testa o roteador, a internet, perda de pacotes, o DNS (comparando com o 1.1.1.1), o sinal do Wi-Fi, quem está usando banda e a velocidade, e explica em português simples o que fazer |

Informe a velocidade do seu plano nas configurações para ele dizer quanto do
plano você está recebendo.

### ✨ Melhorias no que já existia
- **Protocolos** agora têm **passos em ordem**: abrir, fechar, sites, esperar,
  volume, mudo, plano de energia, modo jogo, modo escuro, macro, pomodoro,
  minimizar tudo, bloquear, mensagem e comando. "Jarvis, adiciona ao protocolo
  casa: esperar 5 segundos". Os protocolos antigos continuam funcionando.
- **Briefing** inclui uma linha sobre a saúde do PC e da internet (só fala se
  houver algo errado).
- **Reconhecimento facial**: "bloquear o PC quando eu sair da frente por X
  minutos", e integração com a guarda de segurança.
- **Painel MOTOR & PROVEDORES**, tela de login e página do celular em português.

---

## 🧭 Limites honestos
- **Uso de rede por processo**: o Windows não informa bytes por processo sem um
  driver. O monitor mostra as **conexões** de cada processo e o total por interface.
- **FPS** só com o PresentMon.
- **Sites no Pomodoro** são bloqueados minimizando o navegador, não pelo `hosts`.
- **Luz noturna** e **monitor principal** no Windows: não existe jeito oficial de
  programas mudarem isso; o JARVIS abre a tela certa das Configurações.
- **Serviços do Windows** e o cache do Windows Update precisam de administrador
  (aparece o aviso do UAC).
- **Wayland (Linux)** não deixa programas mexerem nas janelas dos outros.
- Várias partes só existem no Windows (volume por app, trocar saída de som,
  rádios, serviços, inicialização pelo registro). Nos outros sistemas, o JARVIS
  responde "não disponível neste sistema" em vez de fingir.
- **1.4 sem IA**: o conselho, o criador de plugins (só modelos VIGIA e SEQUÊNCIA),
  "olha isso" (só erros copiados) e foto → post (pelo nome do arquivo) ficam
  mais simples. Com a chave do Gemini, ficam completos.
- **Vigia de erros na tela** precisa de um leitor de texto (rapidocr ou Tesseract);
  sem ele, só percebe o erro que você copia.
- **Legenda ao vivo** tem uns 5 s de atraso (o áudio vai em pedaços).
- **Capacete ESP32**: o código não foi testado em hardware por mim; o lado do PC
  tem testes. O áudio vai sem criptografia na rede de casa (porta 8000).
- **Casa inteligente**: precisa da chave local de cada aparelho (passo a passo em
  `plugins/casa_inteligente.py`). Aparelhos que não são Tuya não funcionam.
- **Vigia de preço**: lojas mudam o site e algumas bloqueiam robôs; com o link
  da página o resultado é mais confiável.
- **FRIDAY** usa as vozes do Gemini Live (Charon, Puck, Kore, Fenrir, Aoede); trocar
  reconecta a sessão.
- **Verificação (1.5)** protege contra visita, família ou alguém que senta no seu PC;
  não é um cofre e não substitui a senha do Windows. O rosto (OpenCV) não tem "prova de
  vida": uma foto boa pode enganar. A voz é semelhança, não perícia: gripado ou com
  muito barulho, ele pode pedir outra prova.
- **Celular como chave**: muitos celulares trocam o endereço Bluetooth sozinhos.
  Pulseira ou relógio funcionam melhor; no Wi-Fi, desligue o "MAC aleatório" do
  celular para a rede de casa. O PC precisa ter Bluetooth.
- **Sentinela** vê só o que a câmera vê e não funciona com o PC suspenso ou desligado.
- **Ouvido ambiente**: o detector próprio cobre bipes agudos, barulho forte e os sons
  que você ensina; o resto depende do YAMNet e da qualidade do microfone. Com o mudo
  (F4) ligado, ele também não escuta.
- **Ligação** usa a Twilio, que é paga; na conta de teste ela só liga para números
  verificados e toca um aviso antes da mensagem.
- **Geofence** precisa do Termux, do Termux:API e do Termux:Boot (pela F-Droid). Alguns
  Android fecham apps em segundo plano: tire o Termux da economia de bateria. Para não
  disparar à toa, ele espera 10 min fora antes de dizer "saiu".
- **Memória de tela** guarda o texto do que aparece na tela, só neste PC; o texto some
  em 30 dias e as miniaturas em 7 (dá para mudar em ⚙ CONFIG).
- **Aprender olhando** acha o botão pela imagem; se a tela mudar muito (tema, zoom, outro
  monitor), ele clica na posição gravada. Por isso a 1ª repetição pede CONFIRMAR e o
  F12 para tudo.
- **Postura** precisa de luz razoável no rosto; os bocejos são uma estimativa.
- **Companheiro de jogo** lê só o chat da Twitch (só leitura, sem login).
- **Auto-melhoria** só mexe no código do próprio JARVIS, uma correção por vez, depois do
  CONFIRMAR, e ela vale quando você reiniciar o JARVIS.
- **Aparelhos (1.6)**: Wake-on-LAN precisa estar ligado na BIOS e na placa de rede e quase
  nunca funciona pelo Wi-Fi; TVs Samsung e LG só ligam pela rede se a opção "ligar pela
  rede/celular" estiver ativa nelas. O controle das TVs foi feito pelos protocolos públicos de
  cada marca e não foi testado em todos os modelos.
- **Realidade aumentada** precisa do painel do celular em HTTPS (`"dashboard_https": true`
  no `config/api_keys.json`) e de internet no celular para baixar o detector na 1ª vez.
- **Modo carro** só lê mensagens de um celular Android conectado pelo ADB; no iPhone, só o
  modo de voz do painel funciona. Não mexa no celular dirigindo.
- **Ata de chamadas** grava o som do seu PC: avise os participantes. **Senha vazada** confere
  senhas, não e-mails (a busca por e-mail do HIBP é paga).
- **Gerador de projetos, testes e documentação, explica repositório, entrevista e currículo**
  ficam muito melhores com a chave do Gemini; sem ela, entregam a estrutura/esqueleto.

---

## 🔁 Versões anteriores

### 1.1 — plugins da primeira leva
- **👤 Reconhecimento facial**: "cadastra meu rosto", "você me reconhece?",
  "liga a vigia da câmera", "esquece meu rosto". Funciona com o OpenCV (modelos
  YuNet e SFace, ~39 MB, baixados no primeiro uso). **Nenhuma foto é salva**, só
  uma assinatura numérica em `memory/rostos/`.
- **🎬 Protocolos**: "protocolo foco", "casa", "loja" e os que você criar.
- **☀ Briefing com clima e dólar**: configure sua cidade em ⚙ CONFIG. DE PLUGINS.
- **👕 Cristal Malhas**: roteiro de Reels com legenda e hashtags; "chegaram 10
  conjuntos", "vendi 2 por 89,90", "quanto a loja vendeu esse mês?". Vendas e
  estoque em CSV que abre no Excel.
- **💸 Gastos**: "gastei 40 no almoço", resumo do mês e planilha.

### 1.0 — a tradução
- Interface toda em português, atalhos da área de transferência em PT-BR,
  `iniciar.bat` / `iniciar.sh` e exemplo de configuração.

---

## 📋 Requisitos

| Item | Detalhe |
|---|---|
| Sistema | Windows 10/11 (principal), macOS ou Linux |
| Python | 3.11, 3.12 ou 3.13 |
| Microfone e alto-falantes | Para conversar por voz |
| Chave do Gemini | Grátis, só para o motor Gemini |
| Opcional | ffmpeg (gravação em H.264), PresentMon (FPS no modo jogo) |

## 🎛 Atalhos

| Tecla | O que faz |
|---|---|
| **F4** | Muta / ativa o microfone |
| **F11** | Tela cheia |
| **Esc** | Interrompe o assistente no meio da fala |
| **F9** | Para a gravação de uma macro |
| **F12** | Para uma macro que está rodando |

## 🔒 Seus dados

Tudo fica no seu computador: a chave em `config/api_keys.json`, a memória em
`memory/long_term.json`, e os dados novos (histórico do monitor, área de
transferência, tarefas, rosto, gastos, vendas, macros) em `memory/` e
`config/macros/`. Tudo isso está no `.gitignore`, então não vai parar no GitHub
por acidente. **Nunca publique sua chave da API.**

## ⚖️ Licença e créditos

Licenciado sob **[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**,
a mesma licença do projeto original (veja [LICENSE](LICENSE) e [AVISO.md](AVISO.md)).
Uso pessoal e **não comercial**.

- Projeto original: **Mark LVI** — © 2026 FatihMakes
- Fork PT-BR: **[seu nome aqui]**
