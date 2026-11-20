# Aviso de créditos e modificações

Este software é uma **obra adaptada** do **Mark LVI (MARK 56 — JARVIS)**,
Copyright © 2026 **FatihMakes**.

- Projeto original: https://github.com/FatihMakes/Mark-LVI
- Licença: Creative Commons Atribuição-NãoComercial 4.0 Internacional
  (CC BY-NC 4.0) — https://creativecommons.org/licenses/by-nc/4.0/legalcode
- O texto completo da licença está no arquivo [LICENSE](LICENSE).

## O material foi modificado

Esta versão (J.A.R.V.I.S BR) foi modificada em relação ao original:

- **1.0** — interface traduzida para o português, scripts de início, documentação
  e pequenas correções.
- **1.1** — plugins de reconhecimento facial, protocolos, briefing, Cristal
  Malhas e gastos.
- **1.2** — monitoramento completo (fonte única de métricas em
  `core/telemetria.py` e painel 📊 MONITOR), controle total do PC, 12 funções
  novas, monitor e controle pelo celular, melhorias nos plugins anteriores,
  testes e correções (medição de CPU duplicada, login do celular por chave
  digitada, janelas de console no Windows).
- **1.3** — rosto flutuante (o rosto do JARVIS num canto da tela, com legenda).
- **1.4** — "cérebro" (guardião, gêmeo digital, hipóteses, simulador, memória com
  esquecimento, conselho, laboratório, criador de plugins, radar, memória
  contrafactual, mapa de dependências, oportunidades, habilidades, reconstrução,
  prioridades), linha do tempo, "olha isso", ferramentas da loja, FRIDAY, capacete
  ESP32, vigia de preço, casa inteligente e notificações.
- **1.5** — verificação sem ficar provando quem você é (`core/verificacao.py`) e 14
  funções novas (Sentinela, hábitos, memória de tela, aprender olhando, ouvido
  ambiente, ligação, servidores, postura, humor, ditado de código, auto-melhoria,
  geofence, modo professor, companheiro de jogo e segunda opinião).
- **1.6** — controle dos aparelhos da rede (`plugins/aparelhos.py` e o agente em
  `agente_pc/`) e 42 funções novas (Iron Man, desenvolvimento, segurança, comunicação,
  carreira, criatividade, vida e diversão).
- **1.7** — Arcade J.A.R.V.I.S (`plugins/jogos.py`, `plugins/_arcade.py`,
  `dashboard/static/arcade.html`) com 14 jogos e um motor de xadrez próprio
  (`plugins/_xadrez_motor.py`), escrito para este fork.
- **1.8** — modo remoto: acesso pela internet (`plugins/acesso_remoto.py`), Central com
  câmeras e aparelhos (`dashboard/static/central.html`) e conversa pelo WhatsApp
  (`whatsapp_ponte/`, `plugins/whatsapp_jarvis.py`).
- **1.9** — 14 funções novas (gestos, memória por projeto, modo aula, snapshots, vigia de
  recursos do servidor, ditado, testes comemorados, rascunhos da loja, relatório semanal,
  holograma, DJ, títulos Stark, pausa quando sai, resumo de vídeo).
- **2.0** — música (Spotify/YouTube Music), Telegram e Discord, companheiro proativo,
  perfil de gosto, treinador de jogos e o app do JARVIS no celular.
- **2.1** — o JARVIS só no celular (`celular/app/`), sem depender do computador.
- **2.2** — tela "Tocando agora", QR do WhatsApp em janela própria, tela ao vivo, despertador
  musical, timer de sono, música por humor, rádio do gosto e orçamento de ferramentas.
- **2.3** — WhatsApp pessoal (ler, resumir, mandar, rascunho, resposta automática como
  assistente, modo ausente), secretária de ligações, recados e atendente de voz na Twilio.
- **2.4** — evolução sozinho (testes A/B do jeito de responder), memória em grafo com rede neural
  local, missões em segundo plano, estado do mundo, central de avisos, estúdio de rap, cápsula com
  áudio, diário por entrevista e segurança adaptativa.
- **2.4.1** — interrupção corrigida (resposta seguinte muda, aviso do Gemini ignorado, buffer da placa,
  detector de eco) e interrupção por voz, Ctrl+Alt+P e tecla do push-to-talk.
- **2.5** — contas a vencer (boletos do e-mail e PDF), rastreio de encomendas, garantias e manuais,
  aviso de chuva, caixinha de ideias, celular na mão e negociação no pomodoro, câmera do quarto,
  planta, painel de LED e luva com ESP32, conversa em grupo, avatar de live, holograma na mão,
  intérprete e 5 jogos novos no Arcade.
- **2.11** — nove de uma vez: renomeador de fotos, organizador de abas, modo apresentação, assistente de viagem, clone de estudo, modo faxina, palpite de humor, preenchedor de formulário e o Modo Acompanhar (olha a tela quando você pede).
- **2.10** — explica pra criança, coach de decisões (prós/contras com pesos) e detector de procrastinação.
- **2.9** — segundo cérebro por voz (guarda e acha suas notas, organizadas em pasta e tags) e biblioteca de prompts.
- **2.8.3** — o volume/medidor de som do Windows (pycaw) não derruba mais o JARVIS (access violation).
- **2.8.2** — a busca na internet (DuckDuckGo) não derruba mais o JARVIS.
- **2.8.1** — som que derrubava o programa na reconexão e "por que o JARVIS fechou?" em português.
- **2.8** — modo dormir de verdade (sem precisar da ativação por voz; acorda com palmas, Ctrl+Alt+D,
  "Jarvis, acorda" local ou na hora marcada), rotina de boa noite e bom dia, despertador com soneca, cochilo,
  diário do sono, ciclos, sons para dormir, respiração guiada e correções.
- **2.7** — JARVIS + FRIDAY juntos (conversa, turno, revisão, competição, reunião, modo Ultron), sessão de
  cinema, radionovela, talk show, "neste dia" e campanha de herói.
- **2.6.1** — o JARVIS não fecha mais sozinho (shutdown só com pedido claro; erros anotados em memory/erros.log).
- **2.6** — modo vitrine ("Jarvis, se apresenta") para gravar o vídeo de divulgação.

A lista completa, arquivo por arquivo, está em [CHANGELOG.md](CHANGELOG.md).

## Sem garantias

Assim como o original, este software é fornecido "no estado em que se
encontra", sem garantias de qualquer tipo (Seção 5 da licença).

## Uso não comercial

A licença **não permite uso comercial**, e isso vale para este fork também.
Usar o assistente para ganhar dinheiro (por exemplo, como ferramenta de
trabalho de uma empresa) pode ser considerado uso comercial. Na dúvida, peça
permissão ao autor original. (Isto não é aconselhamento jurídico.)

## Ativos e serviços de terceiros

- `core/face_model.obj` vem do modelo facial canônico do
  [MediaPipe](https://github.com/google-ai-edge/mediapipe), licença Apache 2.0.
- Reconhecimento facial: modelos YuNet e SFace do
  [OpenCV Zoo](https://github.com/opencv/opencv_zoo) (licença Apache 2.0),
  baixados no primeiro uso, não incluídos aqui.
- Serviços consultados pela internet, só quando a função é usada:
  [Open-Meteo](https://open-meteo.com) (clima), [AwesomeAPI](https://docs.awesomeapi.com.br)
  (câmbio), [ipify](https://www.ipify.org) (IP público) e o
  [teste de velocidade da Cloudflare](https://speed.cloudflare.com).
- Ferramentas opcionais, não incluídas: ffmpeg (gravação de tela) e PresentMon
  da Intel (FPS no modo jogo).
- Bibliotecas Python instaladas pelo `setup.py` têm as próprias licenças; o
  pynput (macros) é LGPL-3.0.
- A troca da saída de som no Windows usa a interface `IPolicyConfig`, que o
  próprio painel de som do Windows usa, mas que a Microsoft não documenta.
- 1.5, opcionais e não incluídos: [Resemblyzer](https://github.com/resemble-ai/Resemblyzer)
  (Apache 2.0) para a voz do dono; o modelo YAMNet do Google (Apache 2.0), baixado
  só se você pedir; [bleak](https://github.com/hbldh/bleak) (MIT) para a chave por
  Bluetooth.
- 1.5, serviços usados só quando a função é ligada: [ntfy](https://ntfy.sh) (avisos e
  fotos no celular, também na 1.4), [Twilio](https://www.twilio.com) (ligação, com a
  sua conta) e o chat da [Twitch](https://www.twitch.tv) (leitura anônima).
- 1.6, opcionais e não incluídos: [mido](https://github.com/mido/mido) (MIT),
  [pywebostv](https://github.com/supersaiyanmode/PyWebOSTV) (MIT) e o Android platform-tools
  (ADB), baixado do Google só quando você pede, com a licença do próprio Google.
- 1.8, instalados por você/pelo JARVIS quando pedidos, não incluídos no ZIP:
  [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js) (Apache 2.0; não é afiliado
  ao WhatsApp nem à Meta, e usar automação no WhatsApp pode violar os termos dele),
  [node-qrcode](https://github.com/soldair/node-qrcode) (MIT), [Node.js](https://nodejs.org),
  [Tailscale](https://tailscale.com) e o [cloudflared](https://github.com/cloudflare/cloudflared)
  (Apache 2.0) da Cloudflare.
- 2.0, serviços usados só quando você liga: [Spotify Web API](https://developer.spotify.com)
  (com o seu app e a sua conta), [Telegram Bot API](https://core.telegram.org/bots/api),
  [Discord API](https://discord.com/developers/docs) (com os seus bots) e o Gemini direto do
  celular no app (com a sua chave). Opcional: [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense).
  Repetir rotinas em jogos online pode violar os termos do jogo (ex.: Roblox) e levar a banimento.
- 1.9, opcionais e não incluídos: [MediaPipe](https://github.com/google-ai-edge/mediapipe)
  (Apache 2.0; o modelo hand_landmarker é baixado do Google quando preciso) e o
  [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) (MIT). "Homem de Ferro",
  "Stark" e "J.A.R.V.I.S" são referências de fã; este projeto não tem ligação com a Marvel.
- 1.6, no celular: a página de realidade aumentada carrega o
  [TensorFlow.js](https://github.com/tensorflow/tfjs) e o modelo COCO-SSD (Apache 2.0) pelo jsDelivr.
- 1.6, serviços usados só quando a função é chamada: [Have I Been Pwned — Pwned Passwords](https://haveibeenpwned.com/Passwords)
  (só os 5 primeiros caracteres do hash saem do PC), [OSV](https://osv.dev) (vulnerabilidades),
  a API pública do GitHub, [Fish Audio](https://fish.audio) (com a sua chave) e a busca do
  DuckDuckGo (caçador de vagas).
