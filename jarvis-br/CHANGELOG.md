# Histórico de mudanças — J.A.R.V.I.S BR

Mudanças feitas neste fork em relação ao **Mark LVI** original de FatihMakes.


## [3.9.4] — 2026-11-20 — Cérebro pronto (já vem treinado)

Nada foi removido.

### Adicionado
- **`core/cerebro_base.json` — o cérebro local já vem treinado.** Antes ele nascia só com as frases de exemplo dos
  plugins, sem os parâmetros: adivinhava a ferramenta, mas não sabia o que fazer com ela. Agora traz ~4.900 frases
  (284 intenções, 40 ferramentas) com a ferramenta **e** a ação: "aumenta o som", "não tô ouvindo nada", "pula essa",
  "por que o PC tá lento?", "faz uma faxina no PC", "acende a luz do quarto", "o que tem na lista do mercado?"…
- **Padrões com lacuna** para quando o Gemini está fora: "abre <qualquer app>", "fecha <app>", "toca <música/artista>",
  "volume 40", "brilho 30", "timer de 10 minutos pro bolo", "tempo em <cidade>", "pesquisa <assunto>",
  "anota que…", "adiciona <itens> na lista", "gastei 40 no almoço".
- **`core/cerebro_treino.py`** — o "livro de estudo" e o treino: gera a base, tira as frases ambíguas, confere se
  cada ferramenta e cada ação existem no código e faz uma **prova** com frases que o cérebro nunca viu (só grava com
  nota ≥ 85%). Treinar de novo: `python -m core.cerebro_treino`.
- **Sinônimos** no modelo ("abre/inicia/executa", "aumenta/sobe", "PC/computador/notebook"…) para reconhecer frase nova,
  e um segundo modelo que escolhe a **ação** dentro da ferramenta (pausar × próxima × tocar).

### Segurança (igual à 3.4)
- Com o Gemini no ar, a base só **sugere** (e ajuda a busca de ferramentas); quem decide é o Gemini.
- Sem o Gemini, faz sozinho só o que não é crítico. Nada de desligar, reiniciar, formatar ou apagar na base.
- O que você ensina, usa ou corrige sempre vence a base; frase corrigida nunca mais é feita pela base.
- A semelhança que decide reflexo ignora os sinônimos (continua conservadora); `nao`/`nao_contem` nos padrões
  impedem "fecha o jarvis", "fecha a janela", "abre a porta"…

## [3.9.3] — 2026-11-19 — J.A.R.V.I.S na capa, painéis por cima, YouTube na tela e ★ SALVOS

Nada foi removido.

### Mudado
- **O J.A.R.V.I.S (HUD 3.9) volta a ser a capa.** Na primeira abertura da 3.9.3 a interface volta para ele uma vez;
  depois vale a escolha. O botão de ⚙ alterna J.A.R.V.I.S → SEXTA-FEIRA → rosto → núcleo.
- **Os painéis abrem por cima da interface, dentro da janela** (`hud39/sobreposto.py`): Sistema, Internet, Música,
  Vídeos, Arquivos, Jogos, Config, Processos, GPU, Discos, Diagnóstico e Sobre. Nenhum clique abre aba ou janela nova
  (os botões "abrir navegador" e "HUD em tela cheia" saíram dos painéis; o HUD em tela própria continua no
  `abrir_hud.bat` e em "Jarvis, abre o HUD").

### Adicionado
- **Barra de botões na tela**, no J.A.R.V.I.S e na SEXTA-FEIRA: anterior, tocar/pausar, próxima, volume −, volume +,
  ▶ YouTube e ★ Salvos.
- **Botão ⇄ TROCAR PARA SEXTA-FEIRA / J.A.R.V.I.S** na própria interface.
- **Pesquisa no YouTube sem abrir o YouTube** (`hud39/youtube.py`): escreva `youtube: o que quiser` na caixa (ou use
  🔎 nos painéis). Os resultados aparecem por cima da interface, com miniatura, título, canal e duração; clicar toca o
  vídeo na tela do JARVIS, no player do HUD (QtMultimedia + yt-dlp), já com som. A ★ de cada resultado salva o vídeo.
- **★ SALVOS** (`hud39/salvos.py`, `memory/salvos.json`): `salvar: o que quiser` na caixa, ou por voz ("Jarvis, salva
  que…", "o que eu salvei?", plugin `salvos`). No painel ★ SALVOS: clicar num texto põe ele na caixa, clicar num vídeo
  toca na tela, ✕ apaga.
- `youtube:` e `salvar:` são resolvidos na hora, sem passar pela IA.

### Corrigido
- `iniciar.bat` tinha perdido as quebras de linha do Windows (CRLF) na 3.9.2; voltou ao normal.

## [3.9.2] — 2026-11-19 — Interface F.R.I.D.A.Y

Nada foi removido: o HUD 3.9, o rosto animado e o núcleo reator continuam no botão **HUD:** em ⚙.

### Adicionado
- **Interface F.R.I.D.A.Y** no centro da janela principal (`hud39/friday_qt.py`), agora a interface padrão.
  - A imagem da assistente com os hologramas (`hud39/static/friday.jpg`): só ela, sem o texto e sem nada embaixo,
    ampliada e com as bordas fundidas no fundo.
  - Viva: o orbe do dedo pulsa e cresce com a voz, a imagem acende quando ela fala, o painel da cabeça faz
    varredura, os painéis pequenos brilham, os hologramas tremulam quando ela pensa e tudo fica apagado no mudo.
  - Menu clicável à esquerda (sistema, internet, arquivos, música, vídeos, jogos, config), relógio e saudação.
  - À direita, os números reais do PC: CPU e RAM em anéis, disco, rede, GPU, temperatura, processos e internet.
  - Embaixo, a plataforma holográfica com a onda da voz e o estado do microfone ("Microfone mudo • toque em
    ATIVAR MICROFONE…").
  - Partes da própria imagem são clicáveis: o orbe (falar/escrever), o painel da cabeça (diagnóstico), o painel
    grande (sistema), os painéis pequenos (internet, música, config) e o rosto (sobre a assistente).
- As janelas de painel abertas pela F.R.I.D.A.Y vêm no tema dela (rosa, com a imagem ao fundo e um menu ao lado).

### Melhorado (interações, também no HUD 3.9)
- Todo clique responde na hora: um anel que se expande no ponto clicado e um aviso do que está abrindo.
- O destaque do mouse vale para o menu e para as áreas da imagem, com dica.

### Mudado
- `memory/config_manager.py`: estilos `friday → hud39 → face → core`; na primeira abertura da 3.9.2 a interface
  vira a F.R.I.D.A.Y uma vez, e depois vale o que for escolhido em ⚙.

## [3.9.1] — 2026-11-18 — HUD 3.9 animado e interativo

Nada foi removido.

### Adicionado
- Pacote `hud39/`: a arte do HUD J.A.R.V.I.S 3.9 virou um painel vivo, numa janela própria (Edge ou Chrome em modo
  aplicativo, tela cheia), servido só em 127.0.0.1.
  - **Números reais** no lugar dos textos fixos da arte, lidos de `core/telemetria.py`: relógio, CPU (com anel de uso),
    RAM, disco, rede, ping, GPU, temperaturas, os 8 processos que mais gastam e o sistema (SO, build, arquitetura).
  - **Animações**: anéis girando, radar varrendo, satélites em órbita no globo, reatores pulsando, olhos acesos,
    linha de varredura, partículas, gráficos ao vivo, fluxo de dados e abertura animada. Tudo desligável.
  - **Tudo clicável**: SISTEMA e o logo abrem "Sobre o sistema" e "Sobre o J.A.R.V.I.S"; INTERNET e o globo, a rede
    (IP, Wi-Fi, ping na hora, pesquisa); ARQUIVOS abre as pastas; MÚSICA aperta as teclas de mídia (tocar, pausar,
    próxima, volume); VÍDEOS e JOGOS (Steam); CONFIG muda a cor, sons e efeitos; o círculo JARVIS recebe um comando
    falado (reconhecimento de voz do navegador) ou digitado e manda ao JARVIS como no chat; o reator do peito roda um
    diagnóstico; processos, GPU e discos têm detalhes. Atalhos: espaço, F, Esc, 1–7.
  - O estado do JARVIS aparece no HUD (ouvindo, falando, pensando) e o círculo reage à fala.
  - Também roda sozinho: `abrir_hud.bat` (dois cliques), `./abrir_hud.sh` ou `python -m hud39`.
- `iniciar.bat` com o título da 3.9.1; `instalar.bat` confere se a pasta `hud39` veio no ZIP e diz como abrir o HUD.
- Plugin `hud39` ("Jarvis, abre o HUD", "fecha o HUD") e o botão **🛰 HUD 3.9** na gaveta de controles.
- **O HUD 3.9 na tela principal, no lugar do rosto** (`hud39/qt_hud.py`): a arte com os números e as animações
  pintada direto pelo Qt, sem navegador. A caixa de escrever, o mudo, o falar e os botões do microfone continuam
  iguais. O círculo JARVIS reage à voz (ouvindo, falando, pensando) e fica cinza no mudo; o texto de baixo mostra
  o estado do microfone. Passar o mouse destaca as partes clicáveis; o círculo JARVIS leva à caixa de texto e as
  outras partes abrem o painel delas (Sobre o sistema, Música, Internet…) numa janela do HUD 3.9.
  Na primeira abertura o estilo "rosto" salvo vira o HUD 3.9 (o rosto era só o padrão antigo); o botão
  **HUD:** em ⚙ alterna HUD 3.9 → rosto animado → núcleo reator, e a escolha fica salva.

### Segurança
- Só 127.0.0.1, com conferência do cabeçalho Host (outro site não lê nem manda nada) e token em toda ação.
  Nenhuma ação apaga, instala ou finaliza nada.

## [3.9] — 2026-11-18 — MINER AI

Nada foi removido.

### Adicionado
- Pacote `miner_ai/`: um sistema de mineração modular, que também roda sem o JARVIS (`python -m miner_ai`).
  - **Motor Bitcoin em Python puro:** protocolo Stratum e SHA-256d com meio-estado. Processos de prioridade mínima,
    um por núcleo, com ciclo de descanso que respeita o limite de CPU. A conta foi conferida com o bloco gênese, e o
    motor foi testado contra uma pool de mentira que confere cada share de forma independente.
  - **Motor Monero:** controla o XMRig do usuário, com janela visível, API local com senha e pausa/retomada.
  - **Economia de energia:** limite de CPU, pausa por temperatura e redução 5 °C antes, watts e kWh estimados
    (ou medidos), modo econômico (1 núcleo, 30%, só com o PC parado), horários, bateria e limite de horas.
  - **Cérebro:** rentabilidade com preço e dificuldade de agora, veredito honesto ("loteria", "não compensa"),
    recomendações e aprendizado com o histórico real do PC (hashrate e eficiência por configuração).
  - **Painel** em http://127.0.0.1:18090: cada número com rótulo (REAL, CONFIRMADO, PENDENTE, SIMULAÇÃO,
    CUSTO), gráfico do hashrate e sessões.
  - **Segurança:** endereço Bitcoin com soma de verificação (base58 e bech32/bech32m). Recusa chave privada, xprv e
    frase de recuperação. Nunca no celular, nunca escondido, nunca liga sozinho, não instala nada.
- Plugin `miner_ai` no JARVIS: confirmação na tela mostrando a simulação, e registro no livro-razão.

## [3.8] — 2026-11-18 — modo mineração, garagem e mapa mental

Nada foi removido. Os nomes de modo que já existiam continuam ativando os mesmos modos: conferi 11.792 frases.

### Adicionado
- 3 modos (categoria "dinheiro e garagem"):
  - **Mineração:** ao entrar, faz a conta e mostra o status. Nunca liga o minerador sozinho: ligar continua pedindo
    confirmação na tela. Ao sair, desliga a mineração.
  - **Cripto** ("modo bitcoin"): carteira e cotações, sem dizer para comprar ou vender.
  - **Garagem** ("modo oficina"). Total: 158 modos.
- `veiculo` — manutenção do carro e da moto por km e por data. Usa o km dos abastecimentos do plugin `combustivel`,
  mostra histórico e gastos e avisa uma vez por dia. Item sem registro não vira alarme falso: o JARVIS pergunta
  quando foi feito.
- `mapa_mental` — mapa mental interativo sem internet. Se você der só o assunto, o Gemini sugere os ramos.
  Fica guardado para abrir e aumentar depois, e no celular em pé o mapa fica alto.

## [3.7] — 2026-11-17 — mineração e carteira de cripto

Nada foi removido.

### Adicionado
- `mineracao` — **calculadora honesta**: usa a dificuldade da rede e o preço de agora para mostrar quanto o PC
  ganharia por dia em Monero e em Bitcoin, quanto gasta de luz (tarifa e watts ajustáveis) e se paga a conta.
  Bitcoin no processador mostra quantos anos levaria para achar um bloco. Diz por que LTC, DOGE e BCH são de
  máquina ASIC, ETC é de placa de vídeo e ETH não se minera mais.
  **Controle do XMRig** (o minerador oficial, que o usuário baixa) com a carteira do usuário: só liga com
  confirmação na tela mostrando ganho e custo, roda numa janela visível com prioridade baixa e metade dos núcleos,
  e para sozinho se sair da tomada, no limite de horas ou se esquentar (quando o Windows informa a temperatura).
  Nunca roda no celular, nunca baixa nada, nunca mexe no antivírus e nunca liga sozinho. Liga e desliga ficam
  no livro-razão. Depois da primeira sessão, os cálculos usam a velocidade medida de verdade.
- `carteira_cripto` — compras e vendas em reais, custo médio, valor de hoje (CoinGecko), lucro realizado e não
  realizado, e o que foi minerado. Recusa frase de recuperação e chave privada.

## [3.6.1] — 2026-11-16 — app para Android (APK)

Nada foi removido nem mudou no PC. Tudo novo fica em `android/` e `.github/`.

### Adicionado
- **App Android (APK)** em `android/`. Ele roda dentro do app (Chaquopy) o mesmo `celular/jarvis_celular.py` da
  versão Termux, com a mesma interface, os mesmos plugins e modos, o cérebro local, o organismo e o OMEGA.
  Cérebro "both": Gemini com internet e cérebro local sem internet.
- **Voz do Android na página**: o WebView não tem a voz do Chrome. Um trecho de JavaScript entra no topo da
  página e usa o reconhecimento e o TTS do Android, sem mudar a interface.
- **Ponte com o Android** para o plugin `celular_android` (bateria, lanterna, vibrar, notificação, aviso, copiar,
  colar, abrir, volume, falar, discar, compartilhar). O plugin não mudou: só quem responde os comandos `termux-*`.
- Relatórios e painel OMEGA abrem dentro do app. Um serviço em primeiro plano mantém timers e lembretes vivos.
- `.github/workflows/apk-android.yml`: o GitHub monta o APK de graça. Assinatura fixa, para atualizar por cima sem
  perder dados. Como usar: `android/LEIA-ME-ANDROID.md`.

### Corrigido
- O organismo tratava "falta o pacote X" (mensagem do carregador de plugins) como erro de código e mandava
  "analisar seus erros". Agora entende que é pacote. No app do Android, onde não há pip, fica quieto.

## [3.6] — 2026-11-16 — OMEGA: os 8 sistemas funcionando como um só

Nada foi removido: tudo da 3.5.2 continua igual. Os 8 sistemas da imagem OMEGA (BRAIN, HEART, IMMUNE, MEMORY,
COUNCIL, EVOLUTION, DREAM, LAB) já existiam separados; agora eles se enxergam e trabalham juntos.

### Adicionado
- `omega` — painel OMEGA (anel com os 8 sistemas, cada um verde/amarelo/cinza a partir de dados reais, sem
  fingir), e um **ciclo diário** que liga tudo: DREAM acha padrões → BRAIN confere o cérebro → LAB vira proposta de
  experimento → EVOLUTION avalia → IMMUNE confere o livro-razão → MEMORY → COUNCIL (12 conselheiros que existem no
  código). O ciclo **só propõe**: não começa experimento nem liga evolução sozinho. "Abre o painel omega",
  "roda o ciclo omega", "como está o omega?".
- `livro_razao` — prova à prova de adulteração do que o JARVIS fez: cada ação vira um bloco ligado ao anterior por
  hash e assinado com uma chave do seu PC. Mudou, apagou ou cortou um registro: ele aponta o bloco. Selos com código
  curto para guardar fora do PC. "Prova o que você fez ontem às 15h", "verifica o livro", "sela o livro",
  "demonstra uma adulteração" (mexe numa cópia). O texto dos resultados não é guardado (só a impressão digital);
  senha, token, chave, pin, cpf viram "***"; dos cofres só entra a ação; no modo anônimo nada entra.
- `experimento_vida` — experimentos sorteados na sua vida (N-de-1): "cria um experimento: postar no status, medindo
  as vendas, por 14 dias". Ele sorteia os dias COM e SEM equilibrados por dia da semana, sela o plano no livro
  ANTES dos dados, avisa todo dia e no fim diz se funcionou, com a chance de ser acaso. Mínimo de 8 dias.
  "Que experimentos você sugere?" usa os padrões do DREAM.
- `metacognicao` — o JARVIS mede o quanto acerta: placar do cérebro local, do oráculo, do eu do futuro, do gêmeo
  da loja e das probabilidades. O cérebro local só **propõe** evoluir (fazer sozinho frases parecidas) com prova
  (limite inferior de Wilson ≥ 85%, ≥ 20 casos) e só liga com o seu SIM; depois de ligado continua vigiado e
  **volta atrás sozinho** com 3 erros. Só vale para ferramentas livres. "O quanto posso confiar em você?",
  "aprova a evolução", "desliga a evolução".
- 10 modos novos (categoria "impossíveis"): OMEGA, Bunker (IA local), Cartório, Bastidores, Eu do futuro, Cobaia,
  Autópsia sem culpa, Tira-teima ("modo impossível"), Só fatos, Fortaleza. Total: 155 modos.

### Corrigido (varredura)
- Cérebro local: frase em que você já o corrigiu não é mais feita "por parecer" (antes repetia o mesmo engano).
- `laboratorio`: o parâmetro `regex` era lido no código mas não declarado ao Gemini.
- `sqlite_ajuda`: deixava o arquivo .db aberto (no Windows ficava travado).
- Modos novos nunca tomam o nome de um modo antigo: "modo sem internet" continua sendo o apagão, "missão
  impossível" continua o controle de missão (busca primeiro só nos antigos; os novos entram onde não havia resposta).
- Dois testes da 3.3 dependiam da data de hoje.

## [3.5.2] — 2026-11-15 — instalador da IA local não achava o llama.cpp no GitHub

### Corrigido
- O instalador perguntava só a "última versão" pela API do GitHub. Quando a API recusa (limite de pedidos, rede
  bloqueada, antivírus) ou a versão mais nova ainda está subindo os arquivos, ele desistia. Agora tenta três
  caminhos: (1) as 15 últimas versões pela API, pegando a primeira que tem o zip para Windows; (2) sem a API, a
  página da última versão, montando o endereço do zip direto; (3) um zip que você mesmo baixou e pôs em
  `ia_local\download`. Se tudo falhar, a mensagem diz o motivo e o passo a passo para baixar à mão.

## [3.5.1] — 2026-11-15 — "instala a IA local" abria a pesquisa no Chrome

### Corrigido
- Pedir "instala a IA local" fazia o Gemini pesquisar "como instalar" no navegador: o `ia_local` (e o `cerebro`)
  entravam só pelo nome na lista de ferramentas extras. Agora os dois são ferramentas fixas, com a descrição
  completa, como música e WhatsApp.

### Adicionado
- `instalar_ia_local.bat`: dois cliques e escolher 1 (leve) ou 2 (esperto) — instala a IA local sem depender do
  Gemini, mostra o progresso e no fim liga o servidor e faz um teste ("A IA local respondeu: …").

## [3.5] — 2026-11-15 — IA local: o JARVIS funcionando sem internet

Nada foi removido: tudo da 3.4 continua igual. Com internet, nada muda: o Gemini conversa como sempre.

### Adicionado
- `core/ia_local.py` + plugin `ia_local`: **instala e roda uma IA no seu PC** para quando a internet cair.
  - "Jarvis, instala a IA local" (pede o seu SIM na tela): baixa UMA vez o servidor oficial do llama.cpp (GitHub),
    o modelo (Llama 3.2 1B "leve", ≈ 0,8 GB, ou 3B "esperto", ≈ 2 GB, do Hugging Face) e o faster-whisper (pip)
    com o modelo "base" para ouvir. Confere o espaço no disco antes; se a internet cair no meio, continua de onde
    parou. Sem Ollama, sem Qwen, sem nada pago. Fica na pasta `ia_local/`.
  - **Troca automática:** antes de cada conexão o JARVIS confere a internet. Sem rede e com a IA local instalada, ele
    liga o servidor sozinho e conversa no modo local — ouve com o Whisper, pensa com o modelo no llama.cpp e fala
    com a voz do Windows. Confere a rede a cada 20 s e volta sozinho para o Gemini quando ela volta. As suas
    configurações salvas não mudam (o modo local é temporário, só na memória).
  - **Atalho do cérebro:** no modo local, comando que o cérebro local já conhece vira a ferramenta na hora, sem
    esperar o modelo (que é lento na CPU), e a resposta sai pronta.
  - "Como está a IA local?", "testa a IA local: …", "liga/desliga a IA local", "desliga a troca automática",
    "apaga o modelo esperto".
  - Segurança: instalar, ligar e apagar são só do dono; ver o estado e testar são livres.
- `.gitignore`: `ia_local/` (modelos grandes não vão para o git).

### Limites (honestos)
- Na CPU, o modelo pequeno leva alguns segundos para começar a responder e erra mais que o Gemini.
- O instalador automático do servidor é para Windows (é o que o JARVIS usa).

### Testes
- 804 (novo `tests/test_54_v35.py`, com 16 testes, sem baixar nada: downloads, servidor e rede simulados).

## [3.4] — 2026-11-15 — cérebro local de comandos

Nada foi removido: tudo da 3.3 continua igual.

### Adicionado
- `core/cerebro.py` + plugin `cerebro`: **uma IA pequena, no seu PC, que aprende como VOCÊ fala.** O Gemini continua
  conversando; o cérebro cuida dos comandos do dia a dia.
  - Já nasce com ~830 frases de exemplo tiradas dos próprios plugins.
  - Aprende sozinho: cada pedido que terminou em UMA ferramenta que deu certo vira exemplo ("abre a loja" →
    cristal_malhas, abrir). Correção sua ("não, não foi isso") marca aquele aprendizado como errado. Você também
    ensina direto: "quando eu disser 'boa noite, chefe', liga o protocolo dormir".
  - Reflexo: frase que você já usou do mesmo jeito 2 vezes (ou ensinou) roda na hora, sem o Gemini — no celular
    (mais rápido e sem gastar cota) e no PC sem internet (comando digitado).
  - Sem o Gemini (sem chave, sem rede ou fora do ar): ainda faz o que já aprendeu e frases bem parecidas, desde que
    a ação não dependa de texto livre seu ("liga o modo leitura" não vira "modo estudo" por engano). Se não tiver
    certeza, não faz: avisa e sugere.
  - Busca de ferramentas: as que ele aprendeu com você para aquela frase vêm primeiro (PC e celular).
  - Modelo: Naive Bayes sobre raízes e pares de palavras + vizinho mais parecido; treina em milissegundos, sem
    baixar nada, sem Ollama, sem Qwen, sem API paga. Arquivo: memory/cerebro.json.
  - Segurança: ferramenta CRÍTICA nunca vira reflexo; tudo passa pelo mesmo caminho de sempre (verificação do dono,
    sistema imune, diário); no modo anônimo e no convidado ele não aprende; ensinar/esquecer é só do dono.
  - "O que o seu cérebro já aprendeu?", "quais são os seus reflexos?", "o que você faria se eu dissesse …?",
    "esquece o comando …", "desliga os reflexos".

### Testes
- 788 (novo `tests/test_53_v34.py`, com 17 testes).

## [3.3] — 2026-11-15 — caixa-preta, eu do futuro, gêmeo da loja, código em rap + varredura de bugs

Nada foi removido: tudo da 3.2 continua igual (conferido arquivo por arquivo contra a 2.17, 3.0, 3.1 e 3.2).

### Corrigido (varredura automática do projeto inteiro)
- Três varreduras estáticas, testadas antes com bugs plantados para provar que acham: **nomes indefinidos**
  (symtable, todos os .py: 0 encontrados), **imports e atributos de módulos do projeto** (1 encontrado) e **chamadas
  entre módulos com número/nome de argumento errado** (4.548 funções: 0 encontradas).
- **Mensagem de WhatsApp por voz era digitada às cegas.** `actions/send_message.py` tentava usar
  `plugins._whatsapp_core`, que nunca existiu (nem na 2.17), então sempre caía no modo de digitar na janela do
  WhatsApp sem conferir nada. Agora usa a ponte do WhatsApp do fork: acha o contato pelo nome (contatos e conversas),
  pergunta quando há mais de um, manda e só diz "enviado" quando a ponte confirma. Sem a ponte ligada, o caminho
  antigo continua igual.
- **Oráculo inventava venda no dia em que a loja fecha.** `prever_semana` agora pula o dia da semana que nunca teve
  caixa em 3+ semanas de histórico (ex.: domingo), então o total previsto da semana não fica inflado.
- `promocoes_loja`: "desconto" e "leve_pague" sem o preço davam divisão por zero; agora perguntam o preço.

### Adicionado
- `caixa_preta` + `core/caixa_preta.py`: **os erros que o JARVIS já cometeu com você, para não repetir.** Quando
  você corrige ("não, não foi isso", "tá errado"), ele guarda o que você pediu, o que ele respondeu e a correção;
  erro parecido soma no mesmo registro (2×, 3×). Os mais repetidos e recentes entram nas instruções de cada sessão,
  no PC e no celular ("não repita: …"). "Mostra a caixa-preta", "você já errou algo sobre a loja?", "anota na
  caixa-preta: quando eu disser 'a loja' é a Cristal Malhas", "esquece o erro 3". Desligada no modo anônimo e no modo
  convidado.
- `eu_do_futuro`: **conversa com você daqui a alguns meses, feita com os SEUS números** (caixa da loja, água, ponto,
  corridas, treino, hábitos, modos de foco e as sessões do quadro de estudos). Cada assunto vira um total por semana
  e a projeção usa tendência amortecida (Holt, φ = 0,9) com faixa provável: o ritmo continua, mas a subida ou a
  queda perde força com o tempo, sem prometer milagre. "Como eu vou estar daqui a 6 meses?", "fala com o meu eu do
  futuro" (mensagem pelo Gemini, ou montada só com as contas sem ele), "e se eu vender 15% a mais?", "e se eu
  estudar 4 horas por semana?", gráfico (passado, projeção e faixa), "sela a carta" (vira cápsula do tempo que abre
  na data) e "confere o eu do futuro" (o quanto acertou).
- **Gêmeo digital da loja** (novas ações do `promocoes_loja`; as antigas não mudaram): antes de fazer a promoção, ele
  simula o período com o histórico do caixa (a previsão do oráculo) e mostra vendas e lucro bruto com e sem a
  promoção, quanto as peças precisam subir só para o lucro empatar (ex.: 20% de desconto com margem de 50% → +67%),
  o que ele espera e o desconto que deixa mais lucro. "Registra a promoção" e, quando ela acaba, ele confere com o
  caixa sozinho e **aprende como os seus clientes respondem a desconto** (começa num chute conservador e troca pelo
  que acontece na sua loja). Dias de promoção ficam fora do "normal" das próximas simulações. Guarda a margem média
  da loja quando você diz.
- `codigo_rap`: **explica código como um rap geek ORIGINAL** — de um arquivo, de uma função (acha no projeto pelo
  nome), do código colado ou copiado, ou do último commit. Com o Gemini as rimas são livres; sem ele, as rimas saem da
  estrutura do código (parâmetros, imports, if, loops, try, chamadas, return). Pode ir para o quadro de estudos.
  "Me desafia": ele rima uma função do próprio JARVIS sem dizer o nome e você adivinha (dica a cada erro, revela no
  3º). Antes de mandar código para a IA, tira chaves e senhas do texto e se recusa a ler arquivos de chave/senha.
  Salvo em Documentos/JARVIS/Rap.
- Segurança: caixa-preta, eu do futuro, as ações novas do gêmeo da loja e o rap de arquivo/commit são "só do dono"
  (no modo convidado não rodam e, com a verificação ligada, pedem que seja você); o desafio de rap é livre.

### Testes
- 771 (novo `tests/test_52_v33.py`, com 38 testes: caixa-preta, eu do futuro, gêmeo da loja, código em rap, WhatsApp
  pela ponte, quem pode usar e busca das novas ferramentas).

## [3.2] — 2026-11-14 — anti-eco, modo anônimo e estudos com quadro

### Corrigido
- **O JARVIS ouvia a própria voz e respondia a si mesmo.** O microfone voltava a mandar áudio 0,25 s depois da fala,
  mas caixa Bluetooth, TV/HDMI e os efeitos de som do Windows atrasam o áudio além do que a placa informa; a interrupção
  por voz piorava numa sala com eco; e o som tocado pelos plugins não tinha proteção. Novo `core/anti_eco.py`:
  - eco pego pelo TEXTO: se o que o modelo "ouviu" é, em boa parte, o que o JARVIS acabou de falar (últimos 25 s),
    a resposta a isso é cortada e descartada e não vai para o registro como fala sua;
  - aprende a sala: cada eco aumenta a espera depois da fala (+0,35 s, até +1,5 s), salva em memory/anti_eco.json;
    dois ecos em 10 min suspendem a interrupção por voz por 24 h (ESC, botão e Ctrl+Alt+P continuam);
  - espera mínima de 0,6 s ("eco_cauda_minima_ms") e o som de `sd.play` dos plugins também fecha o microfone.
  - Plugin `anti_eco`: "como está o anti-eco?" / "zera o anti-eco".

### Adicionado
- `modo_anonimo` (+ `core/anonimo.py`): "Jarvis, modo anônimo". Recomeça a sessão sem as suas memórias (no PC e no
  celular) e não grava nada da conversa: memória de longo prazo, resumo da sessão, diário de uso, ganchos de fim de
  turno e parâmetros nos incidentes do organismo. O que você pede de propósito (lista, lembrete) continua valendo.
- `estudos` + `plugins/_quadro.py`: **sistema de estudos com quadro**. Uma lousa no navegador (http://127.0.0.1:8770,
  só no seu aparelho) onde o JARVIS escreve enquanto explica: título, texto, fórmula, passos, lista, código, tabela,
  destaque, exercícios com resposta escondida e **gráfico de função** (calculadora segura, sem eval). Você desenha por
  cima (cores, borracha), troca lousa ↔ quadro branco e salva em Documentos/JARVIS/Estudos com o desenho. Aula pronta
  e exercícios pelo Gemini; tempo de estudo com o `pomodoro` (aparece no quadro); ao terminar, marca as revisões no
  `revisao_espacada`; "quanto eu estudei essa semana?". Prova simulada continua no `clone_estudo`.

### Testes
- 733 (novo `tests/test_51_v32.py`).

## [3.1] — 2026-11-14 — JARVIS BIOLOGICAL CORE: o organismo digital

### Adicionado
- `biological_core/` (pacote novo, ~30 módulos): o JARVIS ganhou um corpo que vigia a si mesmo, se defende e se
  conserta. Sistemas computacionais concretos inspirados na biologia, 100% locais (sem API paga, sem Ollama/Qwen).
  Guia completo: `biological_core/LEIA-ME.md`.
  - **Cérebro com IA básica local:** classificador Naive Bayes de erros que aprende com cada cura; motor de
    hipóteses bayesiano que dá a probabilidade de cada causa e as evidências; decisão por regras + permissões +
    amostragem de Thompson sobre o placar de cada reparo. Sempre explica por que decidiu.
  - **Coração:** batimento numa thread própria (sinais vitais, órgãos vivos, partes travadas, reflexos, febre que
    pausa as rotinas não essenciais), ciclo de inicialização e encerramento seguro.
  - **Sistema nervoso e circulação:** eventos com prioridade, histórico e pedido de ajuda entre órgãos; fila sem
    duplicar evento, com alívio de congestionamento.
  - **DNA digital:** genoma assinado (HMAC-SHA256) com o SHA-256 de cada arquivo; banco de células-tronco (cópia
    confiável do código); só muda com a sua autorização.
  - **Sistema imunológico de 8 camadas:** detecção, identificação, defesa (desligar antivírus/firewall e destruir o
    disco: bloqueado sempre; anti-laço), isolamento (quarentena só da parte doente e disjuntor com teste automático),
    reparação, memória (incidentes, anticorpos, ameaças, decisões em SQLite), prevenção (pontos de restauração dos
    dados) e evolução (7 vacinas, recomendações, limites que se adaptam aos alarmes falsos).
  - **Regeneração:** o protocolo de 10 passos, gravado passo a passo no incidente. Nunca apaga arquivo: guarda a
    versão anterior do lado e entra no "Jarvis, desfaz".
  - **Seis tipos de células:** sentinelas, detectoras, defensoras, reparadoras, de memória e analistas.
  - **Sono de manutenção** (4h–6h) e boletim de saúde da manhã.
  - **Painel futurista** (página HTML que se atualiza sozinha) com o organismo desenhado nas cores azul / amarelo /
    vermelho / verde.
- `plugins/organismo.py`: converse com o organismo ("como está a sua saúde?", "mostra os incidentes", "libera o
  rastreio", "faz um exame completo", "reconhece as mudanças no DNA"…). Ele pede, mas nunca aprova sozinho.
- Celular: aba **Corpo** com o organismo, os pedidos (Autorizar / Negar), as partes isoladas (Liberar) e as decisões.

### Integração (nada foi substituído)
- `core/plugin_loader.py`: portão do sistema imune antes de cada plugin e o resultado depois (custa zero com o
  organismo desligado; ~7 µs ligado). Pedido perigoso que precisa do seu sim vai para o banner do `core/confirm.py`.
- `core/vigia.py`: avisa o organismo de ferramenta travada ou atrasada; limite de tempo próprio por ferramenta.
- `core/relogio.py`: rotina com erro ou travada vira sintoma; febre pausa as rotinas não essenciais.
- Usa o que já existia em vez de duplicar: `core/telemetria.py`, `core/central_avisos.py`, `core/undo.py`,
  `core/protecao_falhas.py` e o agente `plugins/auto_melhoria.py`.

### Testes
- 721 (novos `tests/test_50_bio_brain.py`, `test_50_bio_heart.py`, `test_50_bio_immune.py`,
  `test_50_bio_recovery.py`: os 10 testes obrigatórios do pedido e mais).

## [3.0] — 2026-11-13 — mais leve, mais rápido, sem travar + 20 ideias "impossíveis"

### Mais rápido e sem travar
- `core/vigia.py` (novo): **vigia de travamento.** Antes, o JARVIS esperava cada ferramenta terminar, sem limite, e
  usava as mesmas threads do áudio: um plugin pendurado na internet deixava a conversa muda. Agora as ferramentas
  rodam num grupo próprio de threads; passou de 30 s (`"limite_ferramenta_s"` em config/api_keys.json), o JARVIS diz
  na hora que continua trabalhando, a conversa segue, e quando a ferramenta termina ele mostra o resultado e conta.
  Com tudo ocupado, ele avisa em vez de enfileirar e travar. Vale no PC (`main.py`) e no celular.
- `core/relogio.py` (novo): **relógio central.** As rotinas de fundo da 2.20 em diante (sonhos, sentido de aranha,
  eu do passado e as da 3.0) dividem UMA thread, em vez de uma cada. Rotina com erro não derruba as outras.
- `catalogo`: a busca agora entende português: plural, acento, raízes ("sorteia" = "sorteio"), peso para palavra rara
  e para o nome do plugin, e lê também o texto de ajuda de cada plugin. Com 50 pedidos de teste, acha o plugin certo
  entre os 3 primeiros em 50 (antes, 37) e em 1º lugar em 46.
- `autodiagnostico`: ações `lentos` (ferramentas mais lentas, pelo diário de uso) e `fundo` (threads, rotinas do
  relógio e tarefas que passaram do limite). "Jarvis, o que está lento em você?"
- Medido nesta versão (sem a interface): carrega os 338 plugins em ~0,2 s (~1 s na primeira vez); parado, 57 threads
  (eram 58 na 2.21, mesmo com 19 plugins novos), 0,3% de CPU e 97 MB de memória. Por sessão vão 80 ferramentas,
  ~20 mil tokens (mandar todas seria ~61 mil); os 19 plugins novos só acrescentam o nome no catálogo.

### Adicionado — 20 ideias
- `oraculo`: prevê a venda da loja em cada dia da próxima semana (pelo caixa e pela tendência de cada dia da semana)
  e, quando a semana acaba, confere o erro e guarda o placar. Faz sozinho no domingo à noite.
- `antecipacao`: aprende o que você pede em cada horário (o mesmo horário em 4+ dias) e deixa PRONTO antes. Só
  antecipa o que é de leitura (resumo, meta, status…); o resto ele só sugere. No máximo 2 por hora.
- `pre_mortem`: "o projeto deu errado daqui a um mês: por quê?" — os riscos e como evitar, antes de começar. Depois
  você marca o que aconteceu de verdade e ele aprende os seus tropeços. Funciona sem internet com uma lista comum.
- `detector_cansaco`: soma madrugada, horas sem pausa e pedidos repetidos ou correções. Cansado: sugere pausa (no
  máximo a cada 2 h) e passa a responder mais curto.
- `cofre_condicional`: mensagem para o futuro que abre quando algo ACONTECER (vendas do mês, hábito, cofrinho, km
  corridos ou data), não numa data marcada.
- `cacador_promessas`: acha as promessas no que você fala ("amanhã eu mando o orçamento para a Ana") e cobra no dia.
- `serendipidade`: junta duas ideias ou anotações antigas que nunca se encontraram numa ideia nova.
- `e_se`: o universo paralelo em números — "e se eu tivesse guardado 200 por mês desde 2022?", assinaturas, gastos,
  corrida, vendas — com os seus dados quando existem.
- `crescimento_criancas` (Cristal Malhas): avisa quando cada criança cliente provavelmente já pulou de tamanho, com a
  mensagem pronta para os pais, e os aniversários do mês.
- `clientes_loja`, ação `ritmo`: cliente fora do SEU ritmo de compra (compra a cada 2 semanas e sumiu há 5), com
  rascunho de mensagem. A ação `sumidos` (dias fixos) continua.
- `conferir_pagamento`: antes de pagar, mostra para quem vai um Pix copia e cola (nome, cidade, chave e valor; acha o
  código mesmo no meio de uma mensagem), confere dígitos, valor e vencimento do boleto e o CNPJ, e passa a mensagem
  pelo `detector_golpe` da 1.6, que continua igual.
- `commit_mentiroso`: compara a mensagem do commit com o que o código mudou de verdade.
- `arqueologo_codigo`: "por que essa linha existe?" — escava o Git (blame e histórico da função) e conta a história.
- `dojo_debug`: planta bugs de propósito numa CÓPIA do seu código (o original não é tocado), marca o tempo, dá dica e
  guarda o placar.
- `livro_vo`: uma pergunta por semana para fazer à vó, em 8 capítulos; as respostas viram um livro para imprimir.
- `jornal_vida`: capa de jornal com o seu dia — vendas, sonho, hábitos, tempo em Goiânia, promessas. A edição
  automática das 7h vem desligada ("assina o jornal" liga).
- `rap_semana`: todo domingo, um verso de rap geek original sobre a sua semana, salvo em Documentos/JARVIS/Rap.
- `mapa_calor`: os quadradinhos do GitHub para a sua vida — vendas, uso do JARVIS, água, corrida, treino, hábitos e
  commits.
- `trilha_produtiva`: descobre quais músicas tocavam nas suas horas mais produtivas.
- `duelo_ia`: JARVIS × FRIDAY respondem à mesma pergunta às cegas; você escolhe e o placar (Elo) evolui por assunto.

### Testes
- 668 (novo `tests/test_49_v3.py`). Os recursos com IA foram testados com um Gemini falso, sem a chave real.

## [2.21] — 2026-11-13 — ideias de cientista maluco

### Adicionado
- `multiverso`: **Conselho do multiverso.** Numa decisão difícil, cinco versões do JARVIS (Stark, Empresário, Sábio,
  Rapper e Cientista) discutem em duas rodadas, respondem umas às outras e votam (sim, não ou testar antes). O debate
  completo vai para a tela; o JARVIS narra o veredito e o primeiro passo. Guarda o histórico das reuniões.
  (O plugin `conselho`, que divide uma TAREFA entre especialistas, continua igual.)
- `eu_do_passado`: **Converse com quem você era.** Uma fotografia por mês do que estava nas memórias, metas, ideias,
  segundo cérebro, hábitos, cofrinho, livros, modos e sonhos. Depois: "fala com o eu de 6 meses atrás" (responde em
  primeira pessoa, só com o que estava na fotografia, sem inventar lembrança) e "o que mudou em mim desde março?".
- `palavras_secretas`: **Ele inventa palavras.** Lê o diário de uso, acha sequências de 2 a 4 ferramentas que você
  repete em 3+ dias diferentes, dá um nome ("Protocolo Pequi", "Vibranium"…) e, se você aceitar, cria o protocolo.
- `sentido_aranha`: **Percebe antes de acontecer.** Disco que vai encher (dias restantes pela tendência), vendas
  caindo semanas seguidas, menos água, corrida ou treino, hábito escapando, horas de trabalho demais. Avisa no máximo
  uma vez por dia.

### Melhorado
- JARVIS Darwin (`core/evolucao.py`, desde a 2.4): dois genes novos que evoluem com você — humor (com tirada × sem
  tirada; aprende quando você ri) e fechamento (sugerir o próximo passo × só a resposta; aprende quando você aceita).
- Celular: sonhos, sentido de aranha e a fotografia do mês também rodam no Termux.

### Testes
- 649 (novo `tests/test_48_impossiveis.py`).

## [2.20] — 2026-11-13 — o JARVIS sonha

### Adicionado
- `plugins/sonhos.py`: de madrugada (3h, com o PC parado) o JARVIS cruza os dados de todos os plugins — vendas do
  caixa da loja, água, hábitos, ponto, corrida, treino e modos usados — e procura padrões que ninguém pediu:
  dia da semana que destoa ("Nas sextas há 40% a mais de vendas da loja"), uma coisa que anda junto com outra no
  mesmo dia ou no dia seguinte ("Nos dias com mais horas trabalhadas, há 30% a mais de água bebida") e dia fora da
  curva ("Ontem houve 290% a mais de vendas"). De manhã, quando você volta ao PC, ele conta o que "sonhou".
- Ações: `sonhar` (agora), `ultimo`, `diario`, `dados` (o que ele consegue ver).
- Para não inventar coisa: só conta um padrão que aparece na primeira E na segunda metade dos dias, que passa num
  teste de permutação por postos (um dia absurdo não distorce) e com correção de Bonferroni pelo número de
  hipóteses da noite. Medido: com 6 semanas de dados acha um padrão real em 30 de 30 casos; com dados 100%
  aleatórios inventa algo em ~5% das noites. Sempre avisa que é padrão, não prova de causa.
- Roda offline, sem gastar token, em ~0,02 s. Entra no `resumo_do_dia` e também sonha no celular.
- Testes: `tests/test_47_sonhos.py` (639 no total).

## [2.19] — 2026-11-13 — lote 3: 59 plugins, 81 modos e catálogo sob demanda

### Economia de token (o que define o limite de plugins)
- **Catálogo sob demanda** (`core/orcamento_ferramentas.py`): a ferramenta `outras_ferramentas` levava a descrição de
  TODAS as extras em toda sessão (~45 tokens por plugin: 8,3 mil tokens na 2.18; seriam 11,3 mil agora). Agora só as
  24 extras mais usadas levam a descrição; as outras entram pelo nome e o modelo consulta quando precisa
  (`parametros="?"` mostra como usar, `buscar="…"` procura pela necessidade). Resultado: ~2,1 mil tokens com 314
  plugins. Cada plugin novo custa ~4 tokens em vez de ~45. Volta ao jeito antigo com `"catalogo_completas": -1` em
  `config/api_keys.json`.
- Novo plugin `catalogo` (buscar, ajuda, contar): é quem responde essas consultas, e também "quantos plugins você tem?".

### Melhorias que valem para todos os plugins dos lotes 2 e 3 (`plugins/_lote2.py`)
- Ação por sinônimo ("add" → adicionar/salvar/criar, "delete" → apagar), por começo ("lista" → listar) e com erro de
  digitação; `ajuda` funciona em qualquer plugin.
- Nome aproximado nas listas ("hobbit" acha "O Hobbit"; a voz erra nomes).
- Tudo que é apagado vai para a **lixeira** (plugin `lixeira`: listar, restaurar, esvaziar).
- `backup_dados` (zip das memórias em Documentos/JARVIS/Backups, com restauração segura), `resumo_do_dia` (um relato
  do que está pendente em todos os plugins) e `autodiagnostico` (plugins com problema, pacotes faltando, dados).
- 11 plugins da 2.18 liam a pasta de dados na importação; agora leem na hora do uso.

### Adicionado — plugins (59)
- Loja: `caixa_loja`, `lista_espera`, `fornecedores`, `cupons_loja`, `cartao_fidelidade`, `metricas_marketing`, `etiquetas`.
- Dinheiro e trabalho: `investimentos`, `quitar_dividas`, `precos_mercado`, `ponto`, `calculos_trabalhistas`,
  `vencimentos`, `despensa`.
- Casa e vida: `onde_guardei`, `calculadora_obra`, `churrascometro`, `festa`, `metas_pessoais`, `corrida`,
  `telefones_uteis`, `bingo`.
- Estudo e ensino: `revisao_espacada`, `notas_escola`, `abnt`, `diario_classe`, `algebra`, `geometria`.
- Dev: `diff_texto`, `jwt_decodificar`, `timestamp`, `http_teste`, `sqlite_ajuda`, `env_arquivo`, `segredos_codigo`,
  `qualidade_codigo`, `log_analisador`, `explorar_json`, `calculadora_ip`, `bits_bytes`, `analise_csv`.
- Maker e IA: `eletronica_pro`, `impressao_3d`, `calculadora_ia` (parâmetros de um GPT, memória, ETA, taxa de
  aprendizado, perplexidade), `diario_treino_ia` (loss por experimento, estagnação e overfitting).
- Texto: `banner_ascii`, `texto_estilizado`.
- Diversão: `forca`, `mini_jogos`, `jogos_de_festa`, `caca_palavras`, `trava_linguas`, `curiosidades`, `frase_do_dia`.
- Meta: `catalogo`, `lixeira`, `backup_dados`, `resumo_do_dia`, `autodiagnostico`.

### Adicionado — modos (81, total 145) e sistema de modos melhor
- `plugins/_modos_lote3.py`: programação (par, refatoração, TDD, arquitetura, segurança, treino de IA…), loja
  (abertura, fechamento, reposição, fotos), estudo (vestibular, redação, espanhol, TCC…), casa e vida (mercado, obra,
  domingo, corrida, dever de casa, consulta, dia difícil…), criação, 20 jeitos de falar e jogos.
- `modos`: **modo por tempo** ("modo foco por 50 minutos" sai sozinho), **sugerir** (pelo horário e pelo hábito),
  **buscar**, **listar por categoria** (10 categorias), **histórico** (mais usados) e **nome aproximado**
  ("modo refatorar", "modo cozinhar bolo").

### Melhorado — plugins da 2.18
- `juros` (+ tabela SAC x Price), `sorteio` (amigo secreto guarda segredo: cada um pergunta o seu), `cronometros`
  (timers voltam a contar depois de reiniciar), `astronomia` (+ hora dourada para gravar e estação do ano),
  `conversor_unidades` (+ pressão, energia, potência, km/l ↔ l/100 km), `colinha_dev` (+ docker, npm, linux),
  `celular_android` (+ brilho, falar, discar, compartilhar, contato), `hidratacao` (+ semana),
  `validador_documentos` (+ formatar), `modelos_dev` (+ CI de testes), mais piadas e enigmas.

### Celular
- Busca de ferramentas igual à do PC (plugin `catalogo`), opção **só se eu disser "Jarvis"** no modo mãos livres,
  3 ferramentas diretas a mais (resumo do dia, onde guardei, preços de mercado) e descrições mais curtas.

### Testes
- 635 (novo `tests/test_46_lote3.py`: catálogo, base comum, toda ação de todo plugin novo, modos e upgrades).
- Os arquivos novos também compilam no Python 3.11.

## [2.18] — 2026-11-09 — lote 2: 58 modos e 53 plugins

### Economia de token
- Todos os plugins novos declaram `tier: "extra"` e um `brief` curto: ficam atrás de `outras_ferramentas` e não
  pesam no começo da sessão. Os 58 modos ficam em `plugins/_modos_extras.py` (não viram ferramenta): custo zero.
- Ajudante comum `plugins/_lote2.py` (PLUGIN compacto, despacho de ações, coleção em `memory/lote2/`).

### Adicionado — modos (58)
- Estudo/foco: estudo, prova, leitura, foco_profundo, biblioteca, brainstorm, escrita, pesquisa, tutorial.
- Programação: debug, deploy, revisao, hackathon, laboratorio_stark.
- Loja/trabalho: black_friday, inventario, cliente, freela, financas, planejamento, retro_semana.
- Criação: live, edicao, design, beat, rap, podcast.
- Casa/vida: cozinha, treino, meditacao, relax, madrugada, bom_dia, festa, churrasco, aniversario, familia, crianca,
  faxina_casa, viagem, repouso, detox, emergencia, suporte_parente, economia.
- Jogos: minecraft, competitivo. Jeitos de falar: turbo, detalhado, ingles, classico, sarcastico, pirata, sherlock,
  narrador_futebol, coach, poeta, anime. Apelidos por voz ("modo academia" → treino, "modo bug" → debug…).

### Adicionado — plugins (53)
- Contas: `calculadora` (sem eval), `conversor_unidades`, `juros`, `calculadora_datas` (+ contagens regressivas).
- Loja: `precificacao`, `promocoes_loja`, `tabela_tamanhos`, `trocas_loja`, `recibos` (valor por extenso, recibo e
  orçamento em HTML), `horas_freela`.
- Dinheiro/casa: `cofrinho`, `assinaturas`, `emprestimos`, `presentes`, `cardapio`, `receitas`, `pets`,
  `combustivel`, `conta_luz`, `checklists`, `rodizio_tarefas`.
- Saúde/hábitos: `hidratacao`, `treino`, `sequencias`, `respiracao` (+ alongamento guiado), `leitura_livros`,
  `watchlist`.
- Dev: `regex_ajuda`, `conversor_dados`, `codigos_hash`, `cores`, `dados_falsos`, `snippets`, `portas_locais`,
  `requisitos_python`, `raio_x_projeto`, `cron_explica`, `colinha_dev`, `semver`, `modelos_dev`,
  `validador_documentos`.
- Maker/música/céu: `eletronica` (resistor, LED, ESP32), `calculadora_musical`, `astronomia` (lua, sol offline).
- Diversão: `sorteio`, `cronometros`, `codificador`, `ferramentas_texto`, `piadas`, `anagramas`,
  `matematica_rapida`, `enigmas`, `placar`.
- `ui.py`: versão 2.18. Testes: 618 (novo `tests/test_44_lote2.py` roda toda ação de todo plugin novo).

### Adicionado — JARVIS completo no celular (Android/Termux)
- `celular/jarvis_celular.py`: roda TODOS os plugins e TODOS os modos no celular, só com o Python do Termux
  (sem PyQt, FastAPI ou google-genai). Cérebro: Gemini por REST com ~20 ferramentas diretas + buscar/usar/pesquisar
  (as outras ~230 ficam a uma busca de distância, para gastar pouco token). Plugins que usam a IA também passam a
  usar REST quando o google-genai não está instalado.
- `celular/jarvis_celular.html`: interface HUD com reator, voz e mãos livres, abas Modos, Plugins, Avisos e Ajustes.
- `plugins/celular_android`: bateria, lanterna, vibrar, notificação, copiar/colar, abrir app, localização, volume e
  foto pelo Termux:API.
- `celular/termux/instalar_jarvis.sh` (comando `jarvis` e início no boot) e `celular/LEIA-ME-CELULAR.md`.
- Testes: `tests/test_45_celular.py`.

## [2.17] — 2026-11-09 — lote 1 de 5 (plugins) e de 5 (modos)

### Adicionado
- `modos`: motor único de modos (passos ao entrar/sair, cara do rosto e jeito de falar; um modo por vez; você cria
  os seus). Modos: loja, gravação, roblox, programador, vó e reunião.
- Loja: `clientes_loja` (cadastro, compras, sumidos com mensagem de reconquista, aniversários), `fiado`,
  `meta_vendas`. Diversão: `torneio` (mata-mata ou pontos), `adivinha` (jogo de dicas, offline).
  PC: `git_assistente` (pendências, commit com mensagem da IA e confirmação, pull seguro), `apps_winget`.
  Casa: `lista_compras` (por seção do mercado, manda no WhatsApp), `manutencao_casa`.
- `ui.py`: versão 2.17. Testes: 602.

## [2.16] — 2026-11-09

### Adicionado — Brasil e dinheiro
- `consulta_brasil`: CNPJ (com conferência dos dígitos), CEP, DDD e banco pela BrasilAPI; tabela FIPE pelo nome
  (API Parallelum) ou pelo código; frete pelo Melhor Envio (token grátis) com a resposta pronta para o cliente.
- `feriados`: feriados de qualquer ano calculados aqui (Páscoa, Carnaval, Corpus Christi, 20 de novembro),
  feriados locais, e as emendas que mais rendem (quantos dias tirar e quantos dias de folga ganha).
- `alerta_cotacao`: dólar, euro, bitcoin (AwesomeAPI) e ações da B3 (brapi.dev); avisa uma vez ao passar do valor.
- `cupom_fiscal`: foto da nota → estabelecimento, total, itens e categoria, registrado nos gastos (sem repetir).
- `racha_conta`: quem deve quanto a quem com o mínimo de transferências e o Pix copia e cola de cada uma.
- `controle_mei`: soma o faturamento (vendas da loja + o que você anotar) contra o limite de R$ 81 mil (2026),
  com limite proporcional no ano de abertura e avisos em 70/85/95%.
- `planilha_viva`: escreve na linha certa de qualquer .xlsx/.csv, achando as colunas pelo nome; total de coluna;
  cópia de segurança e "desfaz".

### Adicionado — agenda, comunicação, escrita, PC
- `agenda`: Google Agenda (iCal secreto para ler, OAuth opcional para escrever) e agenda local .ics; horários
  livres; hora de sair pela rota (OpenStreetMap) e trânsito estimado (ou Google Routes), com aviso automático.
- `alerta_nome`: na reunião, avisa se falarem seu nome enquanto você está em outra janela, com a última frase.
- `fila_leitura`, `corretor_atalho` (Ctrl+Alt+C/F/R/A), `atalhos_texto` (//end, //pix…), `pesquisa_profunda`
  (várias fontes, citação em cada afirmação, salva em Documentos/JARVIS/Pesquisas).
- `duplicados` (idênticos byte a byte e fotos borradas; só apaga para a lixeira e com confirmação),
  `cofre_senhas` (AES + scrypt, nunca fala senha, copia por 20 s), `verificador_link` (VirusTotal; arquivo só
  pelo SHA-256).
- `jogar_junto`: copiloto que olha o jogo e dá dicas, controle por voz ("pula", "anda pra frente 3 segundos",
  "escreve no chat") e piloto automático de até 2 minutos; perfis Roblox, Minecraft e WASD; Ctrl+Alt+X para tudo.

### Melhorado — mensagens
- WhatsApp: áudios recebidos são transcritos e ganham resumo de uma linha; fotos são descritas (e o texto nelas
  copiado); tudo fica anotado ("quais áudios eu recebi?"). Novas ações: ouvir o último áudio de alguém, ver a
  última foto, ler mensagens em voz alta, aviso por voz das mensagens que chegam, mandar nota para você mesmo e
  mandar um arquivo do PC (para você direto; para outra pessoa, com confirmação), também pedindo pelo celular.
- `whatsapp_ponte/ponte.js`: rota `/midia` (baixa áudio/foto de uma mensagem antiga). Reinicie o WhatsApp do JARVIS.
- `legenda_ao_vivo`: "ouvintes" e modo silencioso (o alerta de nome usa a mesma captura).
- `_comum.pasta_jarvis()`; `_web.py` (internet só com a biblioteca padrão); `_atalhos_globais.py`.
- `ui.py`: versão 2.16. Testes: 597. Nada foi removido.

## [2.15] — 2026-11-08

### Adicionado
- Emoções no rosto 3D do HUD e no rosto flutuante: feliz, animado, triste, surpresa, sério, bravo,
  desconfiado, pensativo e envergonhado. A boca sorri ou cai nos cantos, as sobrancelhas sobem, franzem
  ou ficam tortas, os olhos arregalam ou apertam, o olhar e a cabeça acompanham e a aura pega a cor da
  emoção. Depois de alguns segundos o rosto volta sozinho ao neutro.
- O rosto muda sozinho conforme o que ele está falando ("infelizmente…" → triste, "uau" → surpresa,
  "as chances de sucesso são de 92%" → feliz). Dá para desligar ("para de mudar de cara sozinho").
- Rosto próprio da SEXTA (F.R.I.D.A.Y), na mesma cabeça holográfica: rosto mais fino, queixo delicado,
  lábios mais cheios com batom, sobrancelha arqueada, cílios, cabelo chanel com franja de lado que
  balança, e cor rosa. Aparece quando ela é a persona ativa (troca na hora).
- Palco das cenas a dois: cada personagem mostra a emoção da própria fala, e a FRIDAY tem rosto próprio
  (cabelo, franja, cílios, batom). Na balança, o JARVIS fica feliz ao pesar a favor, a FRIDAY fica
  desconfiada ao pesar contra, e o veredito sai com a cara certa.
- `core/emocoes.py` (o estado das emoções), `core/avatar_expressoes.py` (deformações e o rosto da SEXTA,
  só numpy) e o plugin `expressoes` ("Jarvis, fica feliz", "faz cara de surpresa").

### Alterado
- `core/avatar.py`: só acréscimos; as pálpebras do modo dormir, que eram calculadas e não desenhadas,
  agora aparecem.
- `main.py`: o texto da fala vai também para as emoções (uma linha, comentada).
- `plugins/_dupla.py`: `falar()` aceita a emoção da fala; `/api/palco` manda emoção e rosto de cada um.
- `plugins/personas.py`: ao trocar para a SEXTA (ou voltar ao JARVIS), o rosto muda na hora.
- `ui.py`: versão 2.15. Testes: 581.

## [2.14] — 2026-11-08

### Adicionado
- `plugins/probabilidades.py` — motor de probabilidades: para qualquer tarefa calcula a chance de
  sucesso em %, o tempo (provável, melhor e pior caso, por Monte Carlo), se é possível ou não (e por
  quê: sem internet, sem espaço, bloqueado pelo guardião, PC sem RAM) e o perigo, com a chance de algo
  grave. Usa o histórico do diário, o guardião, o gêmeo digital e o estado do PC; aprende com
  "deu certo" / "deu errado, levou 10 minutos" e mede a própria precisão.
- Balança JARVIS × FRIDAY (`jarvis_friday`, action `pesar`): o JARVIS pesa a favor, a FRIDAY pesa
  contra, cada argumento move a balança na tela e os dois fecham na chance real, com veredito.
  Funciona sem IA; com IA as falas ficam naturais e os números não mudam.
- Gesto "abrir e fechar a mão" (`gestos`): abre o Chrome por padrão; o comando pode ser trocado por voz
  ("quando eu abrir e fechar a mão, abre o Spotify") ou armado só para a próxima vez ("abre o chrome
  quando eu fechar a mão"). Passa pelo guardião: gesto só faz o que é seguro fazer sozinho.

### Alterado
- `simulador`: toda simulação agora mostra também chance %, tempo, viabilidade e perigo; tarefas que
  ele não sabia simular vão para o motor de probabilidades em vez de "não sei simular isso".
- `jarvis_friday` (`conversar`): quando o tema é uma tarefa ou decisão, a conversa recebe os números
  calculados; sem IA, cai na balança local em vez de falhar.
- `gestos`: a pausa com a mão aberta espera 0,7 s (era 0,45 s) para não brigar com o gesto novo. Os
  outros gestos (deslizar, pinça, paz e amor) não mudaram.
- `ui.py`: versão 2.14. Nenhuma função foi removida.

## [2.11] — 2026-11-07

### Adicionado — nove plugins (todos no PC do usuário, com permissão)
- **Renomeador de fotos** (`plugins/renomear_fotos.py`): renomeia fotos de nome genérico pelo CONTEÚDO + o ano
  (EXIF ou data do arquivo) → `praia_2026_amigos.jpg`. Mostra o antes→depois e só aplica com confirmação; nunca
  apaga nem troca a extensão. Precisa da visão (Gemini).
- **Organizador de abas** (`plugins/organizador_abas.py`): salva grupos de links por assunto (sessões) em
  `memory/sessoes_abas.json` e reabre tudo de uma vez; "capturar" lê, por melhor-esforço, a aba da frente de cada
  janela de navegador aberta.
- **Modo apresentação** (`plugins/modo_apresentacao.py`): não perturbe + tela sempre acesa
  (SetThreadExecutionState) + slides por voz (setas, F5, Esc, B).
- **Assistente de viagem** (`plugins/assistente_viagem.py`): lista do que levar pelo tipo e pelos dias, fuso
  horário (tabela offline), câmbio aproximado (usa a cotação real do briefing quando há) e roteiro dia a dia (IA).
- **Clone de estudo** (`plugins/clone_estudo.py`): monta prova de múltipla escolha (IA), corrige, guarda acertos
  e erros por matéria em `memory/estudo.json` e aponta o ponto fraco.
- **Modo faxina / anônimo** (`plugins/modo_faxina.py`): limpa temporários, lixeira, recentes e — no modo anônimo —
  cache e histórico do navegador. Só pastas de descarte (trava `_seguro`), nunca documentos/fotos/sistema, sempre
  com confirmação. Nível `modo_faxina.limpar` = sensível.
- **Palpite de humor** (`plugins/palpite_humor.py`): palpite leve de energia pelo HORÁRIO e pelo tempo de tela —
  NÃO grava nem lê o que o usuário digita — com uma sugestão de pausa.
- **Preenchedor de formulário** (`plugins/preencher_form.py`): guarda dados comuns (nome, email, telefone, CPF,
  endereço…) em `memory/meus_dados.json` e digita no campo em foco (colando, pra aguentar acento). Recusa senha e
  cartão. CPF/RG aparecem mascarados ao listar.
- **Modo Acompanhar** (`plugins/acompanhar.py`): olha a tela ou a câmera SOB DEMANDA (uma captura por vez, nada
  salvo) e ajuda com o que vê; usa o `actions/screen_processor.py`. O modo de observar sozinho o tempo todo NÃO
  está ligado aqui — fica como ajuste à parte.
- Níveis de segurança e perfis do guardião para os nove; `tests/test_37_extras.py` (25 testes).

## [2.10] — 2026-11-07

### Adicionado
- **Explica pra uma criança** (`plugins/explica_crianca.py`): "me explica X como se eu tivesse 8 anos". Reescreve
  o pedido pro cérebro explicar com palavras simples, uma comparação do dia a dia e um exemplo. A idade (5, 8, 12
  ou adulto leigo) muda o tom; "mais simples ainda" baixa o nível. Sem Gemini, avisa que precisa da chave.
- **Coach de decisões** (`plugins/coach_decisao.py`): "me ajuda a decidir entre X e Y". Você joga prós e contras
  por opção, cada um com peso de 1 a 5 que você ajusta; ele soma (Σprós − Σcontras), mostra o ranking e o ponto
  mais forte de cada lado, mas NUNCA decide por você. Em `memory/decisoes.json`.
- **Detector de procrastinação** (`plugins/procrastinacao.py`): usando a linha do tempo que já existe, percebe
  quando você ENTRA numa distração (YouTube, Instagram…) várias vezes num intervalo curto e cutuca de leve, uma
  vez só, com descanso entre os toques. Fica quieto se você está jogando/em chamada/cinema/dormindo (estado do
  mundo) ou ocioso. "foca" silencia por um tempo; "tô procrastinando?" dá o status e o tempo de distração do dia.
- Os três são de nível livre. `tests/test_36_coach.py` (17 testes). (Correção de brinde: `deve_cutucar` tratava
  "nunca cutucou" como "cutucou no instante 0"; agora é sempre liberado, sem depender do relógio.)

## [2.9] — 2026-11-07

### Adicionado
- **Segundo cérebro por voz** (`plugins/segundo_cerebro.py`): "guarda no meu cérebro: ...". Guarda qualquer nota,
  lembrete ou informação solta e organiza SOZINHO em pasta + tags (por regras; melhor com o Gemini). Cada nota
  também vira um `.md` com as tags no topo, em `Documentos\\JARVIS\\segundo_cerebro\\<pasta>\\` — ou direto no seu
  cofre do Obsidian, se você apontar o caminho em ⚙. "O que eu falei sobre X?" acha pela tag, pela pasta e pelo
  texto. Índice em `memory/segundo_cerebro.json`. É diferente da caixinha de ideias (ideia → projeto).
- **Biblioteca de prompts** (`plugins/biblioteca_prompts.py`): "salva esse prompt como X" e depois "usa o prompt
  do X" — ele devolve o texto pronto. Lista, busca por nome/tag, conta quantas vezes cada um foi usado e atualiza
  quando você salva com o mesmo nome. Em `memory/prompts.json`.
- Os dois são de nível livre (são as suas notas e os seus prompts). `tests/test_35_cerebro.py` (17 testes).

## [2.8.3] — 2026-11-07

### Corrigido — a queda do seu erros.log
- "Windows fatal exception: access violation" na thread da janela, em `comtypes … Release` durante a coleta de
  lixo (Garbage-collecting) enquanto o rosto era desenhado. Os objetos COM do pycaw (volume, medidor "tem som
  tocando?", saídas de som, volume por app) eram criados em várias threads e soltos depois na thread da janela.
  Agora tudo isso roda numa thread fixa só para o COM (`core/com_unico.py`), com coleta de lixo ali mesmo; para
  fora só saem números. `_midia.pico`, `computer_settings.volume_get/set`, `audio_devices.get/set_output_volume`,
  `controle_audio_video` (volume, mudo, volume por app, saídas) e o `jarvis_dj` (abaixa a música pelo PID).
  O "desfazer" do mudo e do volume por app não guarda mais o objeto COM.
- `core/por_que_fechou.py`: achava a thread errada quando a lista de threads era longa; agora aponta a que caiu
  e reconhece o COM do Windows e a coleta de lixo.
- `tests/test_34_quedas.py`: +3 testes.

## [2.8.2] — 2026-11-07

### Corrigido
- O JARVIS fechava sem mensagem logo depois de "[WebSearch] DDG news exceeded 5s" (no resumo de notícias da
  abertura e em qualquer pesquisa). O pacote `ddgs` usa uma biblioteca nativa (primp) que cai no Python 3.14 e
  leva o processo inteiro junto; e a busca que passava do tempo continuava rodando numa thread. Agora toda busca
  do DuckDuckGo roda num processo separado (`actions/ddg_isolado.py`), encerrado no tempo limite: se cair, só ele
  cai. Vale para web_search, monitor de notícias, garantias, vigia de preço e caçador de vagas.
- `tests/test_34_quedas.py`: +2 testes.

## [2.8.1] — 2026-11-07

### Corrigido — o JARVIS fechando sozinho
- `core/placa_som.py`: o PortAudio (por trás do sounddevice) não aguenta duas threads abrindo/fechando a placa
  de som ao mesmo tempo; no Windows isso derruba o Python sem mensagem. Acontecia na reconexão com o Gemini (a
  saída antiga fechando numa thread enquanto a sessão nova abria microfone e saída) e com plugins tocando sons
  de outras threads. Agora abrir/ligar/parar/fechar de TODOS os streams passa por uma trava só.
- `main.py`: a sessão nova espera a saída de som antiga terminar de fechar (até 3 s) antes de abrir outra; o
  microfone abre e fecha pela mesma trava.
- `ui.py`: o aviso "celular conectado" mexia na janela pela thread do painel (fora do Qt) — vai pela ponte.

### Adicionado — por que fechou
- `core/por_que_fechou.py`: junta o erros.log (motivo, pilha da queda, linha do tempo), o sinal de vida e o
  registro de erros do Windows (Application Error/Hang, falta de memória) e explica em português: QUAL parte caiu
  (som, driver de vídeo, janela, câmera, Python…), o código do erro e o que fazer.
- Na abertura, se da última vez ele fechou sem motivo ou caiu, o JARVIS mostra o motivo no console e no registro;
  o `iniciar.bat` mostra "POR QUE O JARVIS FECHOU" logo depois de fechar; "Jarvis, por que você fechou?"
  (`plugins/por_que_fechou.py`, também com o histórico das últimas aberturas).
- `core/protecao_falhas.py`: pid na marca de abertura, linha do tempo (conectou, a sessão caiu, reconectando) e
  sinal de vida em `memory/ultimo_sinal.json` a cada 15 s (hora, RAM do PC e do JARVIS, o que fazia).
- `tests/test_34_quedas.py` (13 testes).

## [2.8] — 2026-11-07

### Corrigido
- `dashboard/server.py`: a liberação do firewall no Linux (ufw, firewalld e iptables) usava `port`, uma variável que
  não existia (a função recebe `*ports`). Com firewall ligado dava `NameError` e a porta do painel nunca era aberta.
- `plugins/olha_isso.py`: uma f-string com barra invertida é erro de sintaxe no Python 3.11 (o mínimo do `setup.py`);
  o plugin nem carregava nele. Um teste agora confere as f-strings de todos os arquivos.
- `main.py`: qualquer erro com o código 1007 pedia a chave da API de novo ("Chave da API inválida"), mas o servidor
  usa o mesmo código para "argumento inválido". Agora só pede a chave quando a mensagem fala da chave. O tempo de
  espera depois de trocar a chave era uma variável local e não valia.
- O botão ACORDAR do painel do celular (`/api/wake`) não estava ligado a nada; agora acorda o JARVIS.
- O botão 😴 DORMIR AGORA só aparecia com a ativação por voz instalada (e sem ela não fazia nada).
- Pedido digitado com o JARVIS dormindo era jogado fora; agora acorda e responde.
- Depois de uma ferramenta ou de uma fala com o JARVIS dormindo, o rosto voltava para OUVINDO.

### Adicionado — modo dormir (`core/sono.py`)
- O JARVIS dorme de verdade, com ou sem a palavra de ativação: "vai dormir", "dorme 30 minutos", "fica quieto até
  as 15h", o botão, ou **Ctrl+Alt+D** em qualquer janela (Windows). Dormindo, o microfone não vai para o Gemini e
  a sessão continua aberta (o silêncio da 2.7.4).
- Acorda com **duas palmas** (detector próprio: subida brusca, queda rápida, som agudo, grupo de 2 ou 3 isolado;
  ignora fala, música, batida na porta, aplauso e digitação), "Hey Jarvis" (se o modelo estiver baixado),
  **"Jarvis, acorda"** reconhecido no próprio PC (faster-whisper opcional, modelo tiny, só enquanto dorme), o botão
  👂 ACORDAR AGORA, qualquer coisa digitada, a tecla do push-to-talk, o celular (botão, comando ou microfone),
  o WhatsApp, ou sozinho na hora marcada.
- O que os plugins falariam fica guardado e vira "Enquanto eu dormia…" (depois da resposta do pedido que acordou
  o JARVIS). Só o urgente passa (sentinela, alarme, despertador, crítico, fumaça/invasão) — e acorda.
- `core/estado_mundo.py`: atividade "dormindo" (não perturbe); `core/central_avisos.py` resume "Enquanto o senhor
  dormia"; `plugins/_dupla.py` não começa cena sozinha com o JARVIS dormindo; a tela ao vivo desliga ao dormir.
- Se o JARVIS ou o PC reiniciar dormindo, ele volta dormindo (`memory/sono_estado.json`); a reconexão com o
  Gemini não acorda nem dá bom dia no meio da noite. Acordou de madrugada (um aviso urgente, uma pergunta)? Volta
  a dormir sozinho depois de 2 minutos sem conversa.
- `core/hotkey.py`: tecla D (Ctrl+Alt+D). `ui.py`: o botão DORMIR/ACORDAR fica sempre na gaveta e muda na hora.

### Adicionado — sono (`plugins/modo_dormir.py`)
- **Boa noite** ("Jarvis, vou dormir, me acorda às 6h30"): não perturbe até de manhã, som para dormir, cena da casa,
  tela apagada, a música abaixando sozinha (timer de sono), PC suspenso/hibernado quando ficar parado (opcional;
  com despertador ele não suspende), o que vence/acontece amanhã (contas, aniversários).
- **Bom dia** ao acordar: quanto dormiu, média da semana, o clima e o dólar (briefing_br), o que vence hoje e o que
  chegou durante a noite.
- **Despertador** (sino sintetizado com volume subindo, ou música), **soneca** ("mais 10 minutos" reabre a noite),
  **cochilo** com despertador, despertador padrão do ⚙ (com "só dias úteis"). Toca uma vez só, mesmo com duas
  threads chegando juntas; não toca atrasado mais de 3 h.
- **Ciclos de sono** de 90 min ("que horas eu acordo se dormir agora?" / "que horas durmo para acordar às 6?").
- **Diário do sono**: última noite, média, menor/maior, regularidade do horário de deitar e dívida de sono; anotar à
  mão ("dormi das 23h às 7h").
- **Sons para dormir** gerados no PC: chuva, mar, lareira, floresta, noite, vento e os novos ruído branco, rosa,
  marrom e ventilador (`plugins/_som.py`), sumindo devagar nos últimos 3 minutos.
- **Respiração guiada** 4-7-8 ou caixa, por sons (sobe = inspira, fica = segura, desce = solta), com o microfone
  reservado; pode entrar no modo dormir no fim.
- **Lembrete da hora de dormir** (uma vez por noite, pela central de avisos).
- Níveis: `modo_dormir` livre; boa noite e o diário do sono só do dono (`core/verificacao.py`, `_guardiao.py`).
  `modo_dormir` é ferramenta fixa (`core/orcamento_ferramentas.py`).
- `tests/test_33_sono.py` (41 testes).

## [2.7.4] — 2026-11-07

### Corrigido — fechava ao reconectar ("1008 client inactivity")
- Quando a sessão do Gemini caía e o JARVIS reconectava, a tarefa do som era cancelada mas a thread que
  escrevia na placa de som continuava escrevendo, e o `finally` fechava a placa ao mesmo tempo. Escrever e
  fechar juntos derruba o Python no Windows sem mensagem (voltava direto para o PowerShell logo depois de
  "Ferramentas …"). Agora a escrita e o fechamento passam pela mesma trava, e o fechamento roda numa thread
  própria depois que a escrita termina.
- A sessão caía por "inatividade" quando nada era enviado (microfone mudo, reservado por uma cena, push-to-talk
  ou esperando a palavra de ativação). A cada 15 s parado vai 0,1 s de silêncio (zeros), e a sessão não cai.

## [2.7.3] — 2026-11-07

### Corrigido — fechava ao apertar INTERROMPER
- A função que fazia `abort()` + `start()` na placa de som (a causa do fechamento no botão INTERROMPER até a
  2.6.1) foi apagada de `core/interrupcao.py`. Um teste confere que nenhum arquivo volta a chamar `abort()` num
  stream de áudio.
- Ao abrir, o console e o memory/erros.log mostram a versão e a PASTA que está rodando (para não abrir sem
  querer uma pasta antiga, como a da 2.6.1).

## [2.7.2] — 2026-11-07

### Corrigido — "abre e fecha do nada"
- O detector de "pedido para fechar" (2.6.1) contava o próprio nome: "Jarvis, fecha o Discord", "Jarvis, fecha
  essa pasta", "Jarvis, sai do jogo" ou "Jarvis, fecha tudo" eram aceitos como "fecha o Jarvis" quando o modelo
  chamava a ferramenta de desligar por engano. Agora o alvo tem que vir logo depois do verbo ("fecha o Jarvis",
  "desliga você", "encerra o programa") ou a fala tem que ser só o pedido ("pode fechar", "Jarvis, desliga").
- Toda saída deixa o motivo em memory/erros.log: pedido de fechar (com a frase), janela fechada, queda do
  Windows/driver ou "sem registro" (processo encerrado de fora: antivírus, Gerenciador de Tarefas, memória).
  Na abertura seguinte o console mostra como ele fechou da última vez.
- iniciar.bat mostra as últimas linhas de memory/erros.log quando o JARVIS fecha (e agora usa CRLF).

## [2.7.1] — 2026-11-07

### Corrigido
- Voz do Windows (plano B das cenas): os acentos chegavam trocados ("A��o"). O texto agora vai num arquivo
  UTF-8; cada fala usa arquivos temporários próprios e eles sempre são apagados; caminho com apóstrofo funciona.
- Sessão de cinema: a abertura e o fim do intervalo falavam sem pausar o microfone, e o JARVIS ouvia a FRIDAY
  pela caixa de som e respondia no meio da contagem. Agora passam pelo palco (microfone pausado).
- Intervalo: pedir um intervalo novo cancela o anterior (antes os dois davam play e o filme voltava a pausar).
- Se o JARVIS fechasse no meio do filme, o "não perturbe" do cinema ficava ligado para sempre. A sessão
  expira sozinha depois de 6 horas.
- Narração do jogo pausa o microfone enquanto JARVIS e FRIDAY comentam.
- "Quem ganhou?" sem nome dava ponto para o JARVIS; agora pergunta.
- "Neste dia" com data impossível (31/02) e a vida do vilão com valor inválido nas configurações não dão mais erro.

## [2.7] — 2026-11-07

### Adicionado — JARVIS + FRIDAY
- `plugins/_dupla.py`: motor de cenas com vários personagens, cada um com a sua voz (Edge TTS; sem ele, as
  vozes do Windows) e o seu rosto no palco (`dashboard/static/palco.html`, /palco). Personagens: JARVIS,
  FRIDAY, FRIDAY da noite, ULTRON, ENGENHEIRO, CRÍTICO, NARRADOR, VILÃO e os que o usuário criar
  (memory/personagens.json). Efeitos gerados na hora (porta, trovão, suspense, vinheta, whoosh). O microfone
  pausa durante a cena; Esc no palco ou "para a cena" encerra.
- `plugins/jarvis_friday.py`: os dois conversam entre si, divisão de tarefas em voz alta, passagem de turno
  (relatório do dia; automática às 19h/8h se ligada), a FRIDAY revisa a última resposta do JARVIS, competição
  com placar e provocações, reunião de equipe com debate e votação, personagens novos, modo Ultron (persona
  nova em `_personas.py`), e três extras: podcast da manhã, trailer do seu dia e narração do jogo na tela.

### Adicionado — sessão de filme
- `plugins/cinema.py`: sessão de cinema (minimiza as janelas, não perturbe — atividade "cinema" em
  `core/estado_mundo.py` —, brilho, vinheta e contagem), intervalo com tempo e play/pause, "o que eu perdi?"
  sem spoiler (anota o filme a cada 2 min ouvindo o som do PC com `soundcard`, ou olhando a tela), pergunta
  sobre a cena pausada, conversa depois do filme com JARVIS e FRIDAY, catálogo de filmes e séries com nota e
  "onde parei", recomendação, maratona planejada (tempo total e intervalos) e quiz de 5 perguntas contra a FRIDAY.
- `plugins/_ia.py`: `ouvir_audio(prompt, wav)`.

### Adicionado — diversão
- `plugins/radionovela.py`: capítulos com narrador, JARVIS e FRIDAY, efeitos e escolhas no fim; aviso do
  capítulo do dia.
- `plugins/talk_show.py`: o JARVIS apresenta um talk show e te entrevista; grava o microfone e o som do PC e
  salva o episódio (episodio.wav + episodio.md) em Documentos\JARVIS\talk_show.
- `plugins/neste_dia.py`: "há um mês o senhor lançou a versão 1.0…" — diário, linha do tempo, CHANGELOG,
  conquistas e filmes da mesma data; comenta uma vez por dia.
- `plugins/campanha_heroi.py`: o uso real do JARVIS vira missões (limpeza = "derrotar o vírus Hydra",
  pomodoro = "recarregar o reator"…), vilão da semana com vida e capítulo semanal encenado.
- `setup.py` tenta instalar `edge-tts`, `miniaudio` e `soundcard` (opcionais).
- `tests/test_32_dupla_cinema.py`.

## [2.6.2] — 2026-11-06

### Corrigido
- O programa fechava sem mensagem logo depois de "Interrompido": o `abort()` + `start()` na placa de som
  (2.4.1) derruba o Python em algumas placas no Windows. Removido; o pouco que está no buffer termina de tocar.
- Se o JARVIS cair por um erro do Windows/driver, na próxima vez ele mostra no console o trecho de
  memory/erros.log.

## [2.6.1] — 2026-11-06

### Corrigido
- O JARVIS fechava sozinho: a ferramenta `shutdown_jarvis` era chamada com "tchau", "para" ou quando o
  modelo confundia "desliga o intérprete/avatar/vitrine" com fechar o programa. Agora só fecha com pedido
  claro ("fecha o Jarvis"); a descrição da ferramenta também foi restrita.
- Erro do Python dentro de um evento da janela (PyQt6) fechava o programa sem mensagem. `core/protecao_falhas.py`
  instala sys.excepthook, threading.excepthook, unraisablehook e faulthandler: o erro vai para
  memory/erros.log e o JARVIS continua aberto. Se a sessão cair com erro, ela sobe de novo.
- `tests/test_31_falhas.py`.

## [2.6] — 2026-11-06

### Adicionado
- Modo vitrine: `plugins/vitrine.py` + `dashboard/static/vitrine.html` — "Jarvis, se apresenta": palco de
  cinema com 15 cenas animadas (dados de exemplo), narração na voz do JARVIS, legenda, efeitos (WebAudio),
  versão curta, formato vertical 9:16, roteiro editável em memory/vitrine_roteiro.json, Esc pula a cena.
- `plugins/_arcade.py`: páginas /vitrine e /avatar_demo; `abrir_pagina(..., extras=[...])`.
- `tests/test_30_vitrine.py`.

## [2.5] — 2026-11-06

### Adicionado — casa e contas
- `plugins/_boleto.py`: linha digitável e código de barras de boleto de banco (fator de vencimento nos
  dois ciclos, inclusive o que recomeçou em 22/02/2025) e de conta de consumo/arrecadação (luz, água,
  telefone), conferindo os dígitos verificadores; leitura do texto do PDF; "A conta de luz vence sexta, R$ 142."
- `plugins/contas.py`: contas a vencer (PDF, pasta, Downloads, e-mail por IMAP com senha de app, foto com
  o Gemini, linha ditada); avisos 3 dias antes, no dia e atrasada; pagar, copiar o código, listar.
- `plugins/_rastreio.py` + `plugins/rastreio.py` + `dashboard/static/encomendas.html`: rastreio pelo 17TRACK
  (API v2.2, chave sua), dígito verificador dos Correios, avisos de mudança (saiu pra entrega, entregue,
  retirada, taxa de importação, problema), lista da loja (pedidos de fornecedor), tela ENCOMENDAS.
- `plugins/garantias.py`: garantia pela foto/PDF da nota (webcam, celular ou arquivo), avisos 30 e 7 dias
  antes; manual em PDF achado na internet e respostas pelo texto dele (com página).
- `plugins/chuva.py`: radar (RainViewer) com cálculo de chegada da chuva + previsão de 15 min (Open-Meteo);
  modo varal.
- `plugins/ideias.py`: caixinha de ideias por tema, revisão de domingo, "vira projeto".
- `plugins/_ia.py`: `ver_imagem` e `ver_imagem_json` (o Gemini olhando uma imagem).

### Adicionado — foco, câmera e ESP32
- `plugins/pomodoro.py` (mudanças comentadas "Fork PT-BR 2.5"): celular na mão durante o foco (webcam) e
  negociação de distração (`plugins/_negociacao.py`: proposta, cumprir, fiado cobrado no fim do foco).
- `plugins/_visao_local.py`: detector de objetos e de mãos do MediaPipe no próprio PC.
- `plugins/objetos_quarto.py`: câmera do quarto que anota onde ficam os objetos ("onde está o meu fone?").
- `plugins/_esp32.py`: servidor dos aparelhos (porta 8765, chave em config/esp32.json);
  `plugins/plantas.py`, `plugins/painel_led.py`, `plugins/luva_repulsor.py` (som do repulsor gerado).
- Sketches com LEIA-ME: `esp32/planta`, `esp32/painel_led` (MD_Parola), `esp32/luva` (MPU6050 + flexão).

### Adicionado — lives, visitas e diversão
- `plugins/_vozes.py` + `plugins/conversa_grupo.py`: quem está falando (resemblyzer ou timbre), notas na
  conversa e respostas pelo nome. `main.py`: `JarvisLive.nota_contexto` (nota sem pedir resposta).
- `plugins/avatar_live.py` + `dashboard/static/avatar.html`: avatar para o OBS (127.0.0.1:8766), boca
  sincronizada, expressões (rir, surpresa, comemorar, pensar, triste), vendas e chat da Twitch.
- `plugins/holograma_mao.py` + `dashboard/static/mao.html`: holograma preso na palma da mão (MediaPipe no
  navegador); `plugins/_camera_remota.liberar`.
- `plugins/interprete.py`: intérprete presencial com sessão própria do Gemini Live e duas saídas de
  áudio (caixa para o convidado, fone para você).
- Arcade: caça-palavras, meteoros, labirinto do Bitinho (personagem original), sudoku e pong;
  `plugins/_arcade.py` aceita rotas dos plugins (`ROTAS_GET`/`ROTAS_POST`).
- `plugins/_notificar.recentes` (os últimos avisos, para o painel de LED).
- Testes: `tests/test_26_casa.py`, `test_27_foco.py`, `test_28_live.py`, `test_29_arcade.py`.

## [2.4.1] — 2026-11-05

### Corrigido
- Interromper (ESC/botão) depois que a resposta já tinha chegado inteira fazia a **próxima resposta
  sair muda**: o descarte só acabava no fim de turno seguinte. Agora o descarte só liga se o servidor
  ainda está mandando a resposta cortada (`core/interrupcao.EstadoInterrupcao`), com uma trava de 4 s.
- O aviso `interrupted` do Gemini Live era ignorado: o áudio que já tinha chegado continuava tocando.
  Agora corta na hora e libera a próxima resposta.
- Depois do ESC ainda saía até ~0,2 s do lote + o buffer da placa de som (até 0,5 s no Windows): a
  escrita é feita em pedaços de 40 ms que param na interrupção, e o buffer é descartado
  (`abort()`/`start()`). Cada pedaço de áudio leva a "época" em que chegou.
- `core/echo.py`: o bloco do microfone chega como `(1024, 1)`; `band_energies` não achatava, dava
  `IndexError` e `is_user_speech()` devolvia sempre `False` — a cauda do eco jogava fora até a sua voz
  logo depois que o JARVIS parava de falar. Um som muito mais alto que o eco de sempre não ensina
  mais o ganho do eco.
- `interrupt()` mexia na fila do asyncio a partir da thread do Qt; agora agenda na thread do loop.

### Adicionado
- Interrupção por voz (estava desligada): `core/interrupcao.eh_voz` + `DetectorVoz` (fone ou caixa de
  som, barulho de fundo, estalos de teclado, começo da sua fala enviado junto ao modelo).
- Ctrl+Alt+P interrompe em qualquer janela (Windows, `core/hotkey.py`); a tecla do push-to-talk também.
- `plugins/interrupcao.py` (⚙ Interrupção: por voz e atalho; "Jarvis, desliga a interrupção por voz").
- `tests/test_25_interrupcao.py`.

### Alterado
- `iniciar.bat` (a sua versão, com console e o código de saída) e `instalar.bat`: acham o Python 3.14
  do seu usuário pelo `%LOCALAPPDATA%`, senão o `py`, senão o `python` do PATH.
- `main.py`: só espaços de continuação de linha diferiam da 2.4 (sem efeito); as mudanças acima
  estão comentadas com "Fork PT-BR 2.4.1".

## [2.4] — 2026-11-05

### Adicionado
- `core/estado_mundo.py` (atividade, presença, música, quando falar) + ferramenta `estado_mundo`.
- `core/central_avisos.py`: urgente / normal (espera brecha) / baixa (resumo "Enquanto você jogava…");
  `plugins/_notificar.notificar` e `plugins/_comum.avisar` falam por ela.
- `core/evolucao.py` + `core/ganchos_turno.py` + ferramenta `evolucao`: testes A/B de tamanho, tom e
  ordem com amostragem de Thompson; recompensa por interrupção, correção, repetição, "resume",
  "explica melhor" e elogio. `main.py` chama os ganchos no fim de cada turno e põe o estilo e o
  estado nas instruções da sessão.
- `core/rede_neural.py` (skip-gram com subpalavras em numpy) e `core/memoria_grafo.py` (SQLite:
  nós, ligações e vetores; busca por significado + palavras + grafo; embeddings do Gemini quando há
  chave) + ferramenta `memoria_grafo` + página `dashboard/static/grafo.html`. A memória inteligente
  e o diário também alimentam o grafo.
- `core/missoes.py` + ferramenta `missoes` + página `dashboard/static/missoes.html`: organizar fotos,
  monitorar preço, converter vídeos; checkpoint, retomada após reinício, pausar/continuar/cancelar.
- `core/microfone.py` (reserva do microfone; `main.py` respeita) e `plugins/estudio_rap.py`.
- `plugins/capsula_tempo.py`: `gravar` (recado em áudio, tocado no dia).
- `plugins/diario.py` (entrevista à noite, consulta por período) e `plugins/seguranca_adaptativa.py`.
- `tests/test_24_evolucao.py`.

## [2.3] — 2026-11-04

### Adicionado
- WhatsApp pessoal: `plugins/whatsapp_conversas.py` (novas, ler, mandar com confirmação e sem 🤖,
  rascunho, modo ausente, liberar/bloquear resposta automática, secretária, modo pessoal, recados,
  status) e `plugins/_whatsapp_pessoal.py` (rascunho no modo pessoal, resposta automática que se
  identifica como assistente, com freio e sem responder robôs; secretária de ligações).
- `plugins/_recados.py` (memory/recados.json): recados do WhatsApp e do telefone.
- Atendente de voz: `plugins/_atendente_voz.py` + rotas `POST /twilio/{voz,pin,fala,aguardar,fim}`
  em `plugins/_painel_remoto.py` (assinatura X-Twilio-Signature, PIN do dono, secretária para os
  outros, resposta do JARVIS pela sessão de voz; se demorar, vai por mensagem). `ligacao` ganhou
  `atender` / `parar_atender`, PIN e "Atender quem liga"; o número é reapontado sozinho quando o
  endereço da Cloudflare muda (`plugins/_tunel.py`).
- Ponte (`whatsapp_ponte/ponte.js`): modo pessoal (nome do contato, áudio e foto), evento `call`
  com recusa pela secretária, `GET /chats`, `/mensagens`, `/contatos`.
- `tests/test_23_conversas.py`.

### Alterado
- `plugins/_whatsapp.py`: novas opções (modo pessoal, rascunho, resposta automática, secretária,
  seu nome); `decidir` reconhece ligação e conversa pessoal; rascunhos servem para a loja e para
  você. `core/verificacao.py`, `plugins/_guardiao.py` e `core/orcamento_ferramentas.py`
  (`whatsapp_conversas` fixa).

## [2.2] — 2026-11-04

### Corrigido
- WhatsApp: "liga o WhatsApp" não trava mais a conversa durante a instalação (segundo plano), usa o
  Edge/Chrome do PC (sem baixar o Chromium) e abre `dashboard/static/whatsapp.html`, que mostra o
  andamento, o QR code ao vivo, o erro e o registro.
- Excesso de ferramentas: `core/orcamento_ferramentas.py` manda ao Gemini Live só as 80 principais
  (núcleo, fixas e mais usadas); as outras por `outras_ferramentas`. `main.py` desembrulha o nome
  verdadeiro antes da verificação e da execução.

### Adicionado
- Tela "Tocando agora" (`dashboard/static/player.html`) servida pelo servidor local
  (`plugins/_arcade.py`, que agora também serve `/whatsapp` e `/player`); abre ao tocar no Spotify.
- `plugins/musica.py`: player, timer de sono, despertador musical, música por humor/atividade e
  rádio do gosto.
- `plugins/tela_ao_vivo.py` + `JarvisLive.tela_ao_vivo()` no `main.py`: a tela em tempo real pelo canal
  de vídeo do Gemini Live.
- `tests/test_22_correcoes.py`.

## [2.1] — 2026-11-04

### Adicionado
- `celular/app/` (index.html, manifest.webmanifest, sw.js, icone.svg, LEIA-ME.md): o JARVIS só no
  celular, sem depender do PC. Gemini direto do aparelho com a chave do usuário, voz do navegador,
  modo mãos livres, memória e notas no celular (com backup), pesquisa, música, WhatsApp, discador,
  rota, Google Agenda e lembretes; abre sem internet (service worker); caminhos relativos para
  hospedar de graça no GitHub Pages.
- `tests/test_21_celular.py`.

## [2.0] — 2026-11-03

### Adicionado
- Música: `plugins/musica.py` + `plugins/_spotify.py` (Web API com login PKCE, sem segredo; tocar,
  pausar, pular, volume, fila, curtir, o que está tocando, lançamentos de quem você ouve; sem
  Premium abre no app) e YouTube Music (yt-dlp opcional para achar o vídeo exato).
- Perfil de gosto: `plugins/_gosto.py` (músicas pedidas/curtidas/puladas, o que toca no DJ, vídeos
  resumidos, jogos, ofertas aceitas/recusadas; pesos com meia-vida de 60 dias).
- Companheiro: `plugins/companheiro.py` (bom dia, música, projeto, vídeo, pausa, conversa; limite por
  dia, intervalo, horário de silêncio, "fica quieto"; fala no PC ou manda pelos canais; aprende com as
  respostas; ligação agendada).
- Canais: `plugins/_telegram.py` e `plugins/_discord.py` (só biblioteca padrão; Telegram com long
  polling e botões; Discord por DM via REST), `plugins/_canais.py`, `plugins/mensageiros.py` e
  `plugins/_conversa_remota.py` (o mesmo atendimento do WhatsApp nos três).
- Jogos: treinador no `companheiro_jogo` (dicas olhando a tela, aprendizado salvo por jogo) e macros
  em modo jogo (repetir até F12 por até 8 h, só com a janela do jogo em frente).
- App do celular: `dashboard/static/movel.html`, `movel.webmanifest`, `sw-movel.js`,
  `icone-jarvis.svg`, rotas `/movel` e `/api/movel/chave`, ferramenta `app_celular`; HTTPS do
  Tailscale (`tailscale serve`) no acesso remoto.
- `tests/test_20_conversa.py`.

### Alterado
- `plugins/_whatsapp.py` usa o atendimento comum (`_conversa_remota`).
- `jarvis_dj`, `resumo_video` e `companheiro_jogo` alimentam o perfil de gosto.
- `core/verificacao.py`, `plugins/_guardiao.py`, botão 📱 no painel, `ui.py` (2.0).

## [1.9] — 2026-11-02

### Adicionado — 14 ideias
- `plugins/gestos.py`: MediaPipe Hands (API antiga ou nova, com download do modelo) e um intérprete
  puro de gestos (pausa, trocar janela, volume na pinça, chamar o JARVIS).
- `plugins/pausa_ausente.py`: pausa/retoma a mídia quando você sai/volta (detector de rosto do opencv).
- `plugins/_midia.py`: teclas de mídia, Alt+Tab, "tem som tocando?" e a faixa atual.
- `plugins/memoria_projeto.py`: projeto aberto no VS Code/Cursor, sessões, git, notas e "onde eu parei?".
- `plugins/snapshots.py`: snapshot por hora em `refs/jarvis/snapshots` (índice temporário, sem tocar
  branch nem stage) ou .zip; backup para pendrive/nuvem; voltar para uma hora com confirmação e desfazer.
- `plugins/modo_aula.py` (+ `ata_chamada` aceita `tipo="aula"`): resumo, tópicos, conceitos, tarefas e quiz.
- `plugins/guarda_vps.py`: ação `recursos` e alerta de CPU, memória e disco do servidor.
- `plugins/ditado.py`: escreve e-mail, mensagem ou código no app aberto; ditado literal com pontuação falada.
- `plugins/testes_vivos.py`: roda unittest/pytest, comemora ou lê o teste que quebrou; modo vigia.
- WhatsApp **modo loja** (`_whatsapp.py`, `ponte.js`): mensagens de clientes viram rascunhos com o
  estoque; o dono aprova/edita/ignora. Nada é enviado sem aprovação. Números do dono passam a ser
  reconhecidos já na ponte (antes só pelo código de pareamento).
- `plugins/relatorio_loja.py`: relatório semanal falado (segunda de manhã) e no WhatsApp.
- `dashboard/static/holograma.html` (+ rota `/holograma` e botão 🔺): holograma de pirâmide.
- `plugins/jarvis_dj.py`: locutor entre as músicas, abaixando só os outros apps.
- `plugins/gamificacao.py`: títulos estilo Stark e XP de vídeos da loja, aulas e testes.
- `plugins/resumo_video.py`: resumo do vídeo do YouTube aberto (histórico do navegador, legenda ou Gemini).
- `plugins/_camera_remota.py`: `quadro()` para a Central, os gestos e a presença dividirem a câmera.
- `tests/test_19_ideias.py`.

## [1.8] — 2026-11-02

### Adicionado — modo remoto
- `plugins/acesso_remoto.py` + `plugins/_tunel.py`: acesso pela internet com Tailscale (status pelo
  `tailscale status --json`, instalação pelo winget) e/ou túnel rápido da Cloudflare (`cloudflared`
  baixado do GitHub oficial para `ferramentas/`); link de entrada de uso único; opção de ligar ao abrir.
- Central remota: `dashboard/static/central.html` (🛰 no painel do celular) e rotas em
  `plugins/_painel_remoto.py` — câmeras ao vivo, tela do PC e controle dos aparelhos (sem `rodar` e
  sem `remover`). Câmeras em `plugins/_camera_remota.py` (webcam + câmeras IP RTSP/HTTP; a câmera
  fecha 20 s depois do último pedido).
- WhatsApp: `whatsapp_ponte/` (ponte Node com `whatsapp-web.js`, só em 127.0.0.1 e com token),
  `plugins/_whatsapp.py` (donos por número, chat "Você" ou código de pareamento; atalhos; áudio e foto)
  e `plugins/whatsapp_jarvis.py` (ligar, QR code, autorizar, mandar para você).
- `core/resposta_remota.py`: o pedido do WhatsApp entra na sessão e a resposta volta por texto.
- `tests/test_18_remoto.py` (inclui a ponte Node com um `whatsapp-web.js` falso).

### Alterado
- `main.py`: `comando_remoto()` e três ganchos comentados (publicar a resposta, não tocar o áudio de
  pedido remoto, encerrar quando alguém fala no PC).
- `dashboard/server.py`: pelo túnel, o limite de tentativas usa o `cf-connecting-ip`.
- `dashboard/static/app.html`: botão 🛰 Central.
- `plugins/_notificar.py`: avisos também no WhatsApp do dono.
- `core/verificacao.py` e `plugins/_guardiao.py`: níveis de `acesso_remoto` e `whatsapp_jarvis`.

## [1.7] — 2026-11-02

### Adicionado — modo diversão
- `plugins/_xadrez_motor.py`: motor de xadrez próprio (regras completas, FEN, perft conferido
  com as posições de referência, busca alfa-beta com quiescência e tabelas de posição,
  leitura de lances falados em português).
- `plugins/jogos.py` (ferramenta `jogos`): abre o Arcade e tem jogos por voz — jogo da velha
  (minimax), lig 4 (alfa-beta), forca por tema, adivinhe o número, pedra-papel-tesoura que
  aprende os seus padrões — e o placar. Lógica pura em `plugins/_jogos.py`.
- `plugins/_arcade.py`: servidor local só com a biblioteca padrão (127.0.0.1, porta livre,
  código de sessão) que entrega `dashboard/static/arcade.html` e a API de xadrez, damas e
  placar (`memory/jogos_placar.json`).
- `dashboard/static/arcade.html`: Arcade J.A.R.V.I.S com 14 jogos — xadrez, damas, velha,
  lig 4, campo minado, 2048, cobrinha, blocos, quebra-tijolos, memória, forca, genius,
  pedra-papel-tesoura e reflexo.
- `tests/test_17_jogos.py`.

### Alterado
- `plugins/xadrez.py`: o xadrez usa o motor próprio (sai a dependência do `python-chess`);
  `novo_xadrez`, `jogada_xadrez`, `novo_damas` e `jogada_damas` são usados pela voz e pelo
  Arcade, então os dois mexem na mesma partida (`memory/xadrez.json`).
- `core/verificacao.py` e `plugins/_guardiao.py`: `jogos` é livre; `xadrez` e `jogos` só
  mexem na partida e no placar.
- `requirements.txt`, `INSTALAR.txt`, `AVISO.md`, `capabilities.txt`, `ui.py` (versão 1.7).

## [1.6] — 2026-11-02

### Adicionado — aparelhos da rede
- `plugins/_rede.py` (varredura da rede /24 por portas conhecidas, SSDP e ARP; tipo de cada
  aparelho; Wake-on-LAN; pedidos assinados com HMAC) e `plugins/aparelhos.py` (PCs pelo agente,
  TV Roku/TCL por ECP, Samsung pelo WebSocket da TV, LG com `pywebostv`, Android TV e celular
  pelo ADB por Wi-Fi com instalação do platform-tools, luzes/tomadas da casa inteligente).
- `agente_pc/` (novo): agente para os outros PCs, só com a biblioteca padrão do Python —
  status, desligar, reiniciar, suspender, bloquear, abrir/fechar, volume, mensagem, print e
  comandos; chave HMAC, janela de 60 s, número único contra repetição, registro em agente.log.

### Adicionado — as 42 ideias
- Iron Man: `armadura` (+ página 🦾 no celular), `realidade_aumentada` (+ página 🥽 com
  TensorFlow.js/COCO-SSD no celular), `modo_carro` (+ botão 🚗: o celular lê as respostas),
  voz do Fish Audio (`providers/tts_fishaudio.py`), boot com rede e pendências.
- Desenvolvimento: `turno_noite` (testes + OSV + pip), `explica_repo`, `gerador_testes`,
  `documentacao`, `changelog_falado`, `painel_dev`, `gerador_projetos` (+ `_projetos.py`,
  `_analise_codigo.py`).
- Segurança: `detector_golpe`, `senha_vazada` (HIBP k-anonimato, caixinha local),
  `guarda_vps`, `modo_convidado`.
- Comunicação e carreira: `estilo_escrita`, `resumo_grupo`, `aniversarios`, `ata_chamada`,
  `entrevista`, `portfolio`, `cacador_vagas`, `professor_ingles`, `ensina_errado`.
- Criatividade, vida e diversão: `parceiro_rima`, `gerador_beats` e `contador_historias`
  (+ `_som.py`: bateria, ambientes e efeitos sintetizados), `mestre_rpg`, `thumbnails`,
  `capsula_tempo`, `conselheiro_decisao`, `gamificacao`, `retrospectiva`, `cuidador`,
  `xadrez` (xadrez com `chess` + damas brasileiras próprias; motor próprio na 1.7), `quiz_geek`, `modo_debate`,
  `eu_virtual`, `narrador`, `roleta`.

### Alterado
- `main.py`: modo convidado tira as memórias da sessão e põe a instrução de visita
  (mudança pequena e comentada).
- `core/verificacao.py`: portão do modo convidado; níveis das ferramentas novas
  (`aparelhos.rodar`, `guarda_vps.bloquear` e `modo_convidado.desligar` são críticos).
- `dashboard/static/app.html`: botões 🦾 🥽 🚗 e o modo carro; `_painel_remoto.py`: rotas
  `/armadura`, `/ar`, `/api/armadura` e `/api/ar/perguntar` (com o mesmo login).
- `providers/registry.py`: Fish Audio na lista de vozes. `_guardiao.py`: perfis de risco novos.
- `ui.py`: versão 1.6. Testes: 195 (eram 157).

## [1.5] — 2026-11-02

### Adicionado — verificação sem ficar provando quem você é
- `core/verificacao.py`: níveis livre / sensível / crítico (padrões + os seus em
  `config/verificacao.json`), sessão confiável de 8 h (`memory/verificacao_sessao.json`,
  sobrevive a reiniciar o app no mesmo boot), fecha no Win+L, na suspensão, no fim do prazo
  ou com desconhecido na câmera; desbloquear o Windows conta como prova; críticos pedem
  prova forte dos últimos 15 min; `autorizar()` é o portão chamado antes de cada ferramenta.
  Texto de fora (chat da live) nunca vira ação: nos segundos seguintes só passa o que é
  livre, até o usuário falar, digitar ou mandar pelo celular.
- `core/escuta.py`: cópia em memória dos últimos 30 s do microfone, trechos de fala do
  usuário e assinantes (ouvido ambiente). Nada vai para o disco.
- Plugins `verificacao`, `voz_dono` (+ `_voz.py`, resemblyzer opcional, cadastro passivo) e
  `chave_celular` (Bluetooth com bleak ou Wi-Fi pela tabela ARP).

### Adicionado — as 14 ideias
- `sentinela` (foto no celular, ligação opcional, arma com a chave/geofence/Win+L,
  30 s para sair, desarma ao reconhecer você), `habitos`, `memoria_tela` (SQLite FTS5),
  `demonstracao` (aprende olhando: cliques com recorte da tela, textos, atalhos; F9/F12),
  `ouvido_ambiente` (bipes, sons ensinados, barulho forte; YAMNet opcional, baixado por voz),
  `ligacao` (Twilio) e `servidores` (sites e portas TCP), `postura`, `humor`,
  `ditado_codigo`, `auto_melhoria`, `geofence` (+ `celular/termux/`), `modo_professor`
  (SM-2), `companheiro_jogo` (tempo de jogo, comentário da partida, chat da Twitch) e
  `segunda_opiniao`.

### Alterado
- `main.py`: o portão da verificação antes de cada ferramenta; pedidos do painel do
  celular e do áudio do celular marcam "origem remota"; o microfone alimenta o
  `core/escuta.py`; pedido digitado conta como "o usuário pediu"; o humor do dia entra na
  identidade (mudanças pequenas e comentadas).
- `core/registro_uso.py`: tabela `erros` com o traceback e o arquivo/linha dentro do
  projeto; `plugin_loader` e `action_loader` registram as exceções das ferramentas.
- `reconhecimento_facial`: ver você renova a sessão confiável; desconhecido sem você a fecha.
- `_notificar.py`: `enviar_arquivo()` (foto no ntfy), parâmetro `foto` e prioridade urgente
  vira ligação (se configurada). `_capacete.py`: áudio do capacete marca origem remota.
- `olha_isso._ler_tela()` aceita o recorte (a memória de tela lê a janela inteira).
- `_guardiao.py`: perfil de risco das ferramentas novas. `ui.py`: versão 1.5.
- Testes: 157 (eram 108).

## [1.4] — 2026-10-31

### Adicionado — infraestrutura
- `core/registro_uso.py`: diário de uso do JARVIS (`memory/uso.db`): cada chamada de
  ferramenta com tempo e resultado, as linhas do registro e cada protocolo/cadeia passo a
  passo. Segredos nos parâmetros viram `***`; 60 dias de retenção.
- `core/registro_ferramentas.py`: catálogo central, para um plugin usar outro pelo nome;
  carregar/descarregar plugin com o app aberto; reconectar a sessão; mandar linha ao celular.
- `core/plugin_loader.py`: `carregar_um()` (ativa um plugin aprovado sem reiniciar) e o
  registro de cada chamada no diário.
- `plugins/_ia.py` (IA opcional), `_guardiao.py`, `_notificar.py` (voz + registro + painel do
  celular + push ntfy), `_rosto_ui.py`, `_personas.py`, `_capacete.py`.

### Adicionado — as 15 ideias
- `guardiao_decisoes`, `gemeo_digital`, `hipoteses`, `simulador`, `memoria_inteligente`,
  `conselho`, `laboratorio`, `criador_ferramentas`, `radar_anomalias`, `memoria_contrafactual`,
  `mapa_dependencias`, `oportunidades`, `habilidades`, `reconstrucao`, `prioridades`.

### Adicionado — a segunda lista
- `olha_isso` (janela ativa + Ctrl+Alt+J + vigia de Traceback), `linha_do_tempo`
  (tabela `foco` no monitor.db + aba MEU DIA no 📊 MONITOR), `quando_voltar`,
  `boot_cinematico`, `legenda_ao_vivo`, `cristal_fotos`, `cristal_video`,
  `cristal_calendario`, `personas` (F.R.I.D.A.Y), `capacete` + `esp32/capacete/`,
  `vigia_preco`, `casa_inteligente`, `notificacoes`.
- Protocolos: passos `persona`, `casa`, `energia` e `ferramenta`; modo `paralelo`
  (ligado pela memória contrafactual).

### Alterado
- `main.py`: entrega o app ao catálogo central, junta o estilo da persona ativa à
  identidade e manda a voz também para o capacete (mudanças pequenas e comentadas).
- `ui.py`: versão 1.4; cada linha do registro vai para o diário; `abrir_meu_dia()`.
- `dashboard/server.py`: rota `/ws/capacete` (HTTP e HTTPS).
- `reconhecimento_facial`: ao reconhecer você depois de muito tempo fora, chama o
  relatório de "quando voltar".
- Testes: 108 (eram 68); bancos de dados dos testes vão para uma pasta temporária.

## [1.3] — 2026-10-30

### Adicionado
- `core/rosto_flutuante.py`: o rosto animado do JARVIS numa janela pequena, sem
  borda, sempre no topo, com bolha de legenda, indicador de estado, arrastar,
  rodinha para o tamanho, clique duplo para abrir o JARVIS e menu (canto,
  tamanho, transparência, legenda, mutar, aparecer ao minimizar). Lê o nível de
  som, a fala (visemas) e o estado do próprio HUD, sem outro caminho de áudio.
- `plugins/rosto_flutuante.py`: mostrar, esconder, mudar de canto e de tamanho por voz.
- `instalar.bat` e `INSTALAR.txt`; o ZIP passa a ser o projeto completo.

### Alterado
- `ui.py`: botão 🧑 ROSTO FLUTUANTE na gaveta CONTROLES; o rosto aparece sozinho
  quando a janela é minimizada (configurável); as falas do registro vão para a
  bolha do rosto; versão 1.3.

## [1.2] — 2026-10-29

### Adicionado — base
- `core/telemetria.py`: a **fonte única** de métricas (CPU total e por núcleo,
  frequência, temperatura, RAM, swap, GPU via NVML, discos e E/S, rede por
  interface e total do dia, ping, Wi-Fi, gateway, DNS, IP público, bateria,
  ventoinhas e tabela de processos). Ciclos de 2 s / 6 s / 30 s / 5 min; mediu
  0,4% de um núcleo nos testes. Mais: SMART, teste de velocidade, dispositivos
  da rede local e conexões estilo netstat, sob demanda.
- `core/painel_monitor.py`: o painel **📊 MONITOR** (visão geral com mini
  gráficos, processos com ações, rede, discos e histórico).
- `core/qt_bridge.py`: plugins pedem coisas à thread da interface sem travá-la.
- `plugins/_protecao.py`: lista de proteção de processos **compartilhada**.
- `plugins/_comum.py`: configuração com padrões, subprocess sem console,
  PowerShell em UTF-8, confirmação, desfazer, formatos brasileiros.
- `plugins/_processos.py`, `_monitor_db.py` (SQLite), `_indice_apps.py`
  (lançador com apelidos e busca aproximada), `_janelas.py` (ctypes, sem
  dependência nova), `_painel_remoto.py` (rotas do celular).
- `dashboard/static/monitor.html`: monitor e controle pelo celular.
- `tests/`: 68 testes (proteção de processos, agendador, nota de saúde,
  interpretadores de comando, alertas, diagnóstico de rede, limpeza segura,
  downloads com desfazer, carregamento de todos os plugins sem dependências
  opcionais e validade das declarações para o Gemini).

### Adicionado — plugins
- `monitor_sistema`: status, "o que está pesando", top de processos, internet,
  rede local, teste de velocidade, discos, relatório do dia/semana, ações em
  processos, alertas falados configuráveis e histórico em `memory/monitor.db`.
- `controle_pc`: apps (abrir com apelido/fuzzy/admin, fechar, reiniciar, focar),
  janelas (minimizar, maximizar, outro monitor, lado a lado, sempre no topo,
  minimizar tudo), energia (desligar, reiniciar, suspender, hibernar, bloquear,
  sair, agendar, cancelar) e teclado/mouse.
- `controle_audio_video`: volume geral e por app, mudo explícito, listar e
  trocar a saída de som (IPolicyConfig no Windows), brilho, modo escuro
  explícito, luz noturna, resolução com volta automática em 20 s.
- `controle_sistema`: busca de arquivos por nome e conteúdo, recentes, maiores,
  Wi-Fi/Bluetooth/modo avião (rádios do Windows, sem administrador), redes
  salvas, renovar IP, limpar DNS, serviços, programas de inicialização (do
  mesmo jeito que o Gerenciador de Tarefas), plano de energia e área de
  transferência.
- `modo_jogo`, `limpeza`, `guarda_seguranca`, `macros` (pynput), `agendador`,
  `historico_clipboard`, `gravador_tela` (ffmpeg ou mss+OpenCV, com 9:16),
  `saude_pc` (nota 0–100 e HTML), `downloads`, `pomodoro` e `assistente_rede`.

### Alterado
- `ui.py`: a classe de métricas do HUD virou um adaptador da telemetria (mesma
  API); botão 📊 MONITOR na gaveta de controles; ponte Qt instalada na abertura;
  painel MOTOR & PROVEDORES traduzido; mensagens do registro traduzidas.
- `actions/system_monitor.py`: lê a telemetria; os alertas antigos ficam quietos
  quando o `monitor_sistema` está ligado (sem aviso duplicado); as sondas
  repetidas de NVML/WMI foram removidas.
- `actions/open_app.py`: apelidos e índice de apps antes dos caminhos antigos
  (sem mudar quem já chamava); registro em português.
- `plugins/protocolos.py`: passos em ordem (15 tipos), progresso no registro,
  resumo falado, migração automática do formato antigo, proteção compartilhada.
- `plugins/briefing_br.py`: linha sobre a saúde do PC e da internet.
- `plugins/reconhecimento_facial.py`: bloquear o PC após X minutos sem o dono;
  desconhecido na câmera passa pela guarda de segurança.
- `dashboard/server.py`: registra as rotas do celular (mesmo login).
- `dashboard/static/app.html` e `login.html`: em português e com o atalho 📊.
- `providers/*.py`: rótulos e notas em português.
- `requirements.txt` (+ pynput), `setup.py`, `capabilities.txt`, `.gitignore`.

### Corrigido
- **CPU medida em dobro**: HUD e alerta chamavam `psutil.cpu_percent(interval=None)`,
  que mede "desde a última chamada" para o processo inteiro; um zerava a medição
  do outro e o alerta de CPU lia valores errados. Agora há um coletor só.
- **Login do celular por chave digitada nunca funcionava**: o servidor gera
  chaves de 8 caracteres e a página aceitava só 6 (e enviava ao chegar no 6º).
- **Janelas de console piscando no Windows**: `shutdown` (desligar),
  `cmd /c start` (abrir vídeo do YouTube), instalações pelo pip (painel de
  provedores, ativação por voz, voz Kokoro, instalador), ffmpeg do processamento
  de arquivos, regras de firewall do painel remoto e execução de código.
- Busca de apps: "vs code", "ms teams" (antes podia escolher o Steam) e plural
  ("estudos" → "estudo").
- Partições somente leitura (snaps, ISOs) não geram mais alerta de "disco cheio".

## [1.1] — 2026-10-28

### Adicionado
- `plugins/reconhecimento_facial.py`: cadastro do rosto do dono, identificação,
  vigia em segundo plano com boas-vindas e aviso de desconhecidos. Usa YuNet +
  SFace do OpenCV, sem dlib. Guarda só a assinatura numérica, nunca fotos.
- `plugins/protocolos.py`: rotinas nomeadas (Foco, Casa, Loja) que abrem e
  fecham apps e sites com uma frase. Lista de proteção para processos do sistema.
- `plugins/briefing_br.py`: clima (Open-Meteo) e cotação do dólar e do euro
  (AwesomeAPI), por voz e dentro do resumo matinal.
- `plugins/cristal_malhas.py`: roteiro, legenda e hashtags para vídeos de
  produto; vendas e estoque com aviso de estoque baixo.
- `plugins/gastos.py`: gastos por voz, resumo mensal por categoria e exportação
  para Excel.
- `plugins/_dados_br.py`: CSV no formato do Excel brasileiro (`;`, vírgula
  decimal, acentos), compartilhado pelos plugins de dados.

### Alterado
- `main.py`: o resumo matinal inclui clima e dólar quando o briefing_br está
  ligado; plugins podem definir `on_session_start(player)` para começar sozinhos.
- `.gitignore`: rosto, gastos, vendas e os modelos baixados nunca vão para o Git.

## [1.0] — 2026-10-28

### Adicionado
- `iniciar.bat` e `iniciar.sh`: abrem o assistente com um clique, sem precisar
  digitar comandos no terminal.
- `config/exemplo_api_keys.json`: modelo de configuração com todos os campos
  que o app lê (nome, voz, cor, etc.).
- `AVISO.md`: créditos ao projeto original e lista das modificações, como a
  licença CC BY-NC 4.0 pede.
- Tabela `_STATE_PT` em `ui.py`, que traduz os estados do HUD
  (DORMINDO, INICIANDO…) sem mexer na lógica interna.

### Alterado
- Toda a interface (`ui.py`) traduzida para português: gavetas de
  configuração e controles, painéis de áudio, memória, plugins, acesso remoto,
  personalização, primeira configuração, quiz e vídeo.
- Mensagens do registro de atividade (`main.py`) em português.
- Instalador (`setup.py`) com mensagens em português.
- Ações da área de transferência: "Traduzir" agora traduz **para o português**.
- O registro passa a mostrar `Você:` no lugar de `You:` (o colorido continua
  funcionando para os dois).
- Nome da versão: `MARK LVI` → `J.A.R.V.I.S BR 1.0`.
- Rodapé mostra "Fork PT-BR · base: Mark LVI de FatihMakes".

### Corrigido
- `main.py`: o nome padrão do assistente estava escrito `"JARVI    S"`
  (com espaços no meio). Agora é `"JARVIS"`.
- `setup.py`: o instalador se chamava "MARK LIV" em vez de "LVI".

### Ainda em inglês
- O painel MOTOR & PROVEDORES (só título e botão principal foram traduzidos).
- Comentários do código-fonte.
