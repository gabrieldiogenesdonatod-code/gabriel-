# J.A.R.V.I.S BR completo no celular (Android)

> **Novo na 3.6.1:** também existe um **app (APK)** que dispensa o Termux. Veja `android/LEIA-ME-ANDROID.md`.

O JARVIS inteiro roda **dentro do seu celular** pelo Termux: **todos os plugins** (os 356), **todos os modos**
(os 145 e os que você criar) e uma **interface própria** no Chrome, com o reator no meio, voz e mãos livres.
Não precisa do PC ligado.

## Instalar (uma vez, uns 10 minutos)

1. **Instale pelo F-Droid** (https://f-droid.org): **Termux** e **Termux:API**. Se quiser que ele abra sozinho
   quando o celular ligar, instale também o **Termux:Boot**. Não use o Termux da Play Store, porque está desatualizado.
2. **Baixe o zip do JARVIS** no celular e extraia na pasta **Download** (o app Arquivos do Android extrai).
   Fica `Download/jarvis-br/`.
3. **Abra o Termux** e cole:
   ```
   termux-setup-storage
   ```
   Aceite a permissão. Depois cole:
   ```
   bash ~/storage/downloads/jarvis-br/celular/termux/instalar_jarvis.sh
   ```
4. **Pronto.** Agora é só digitar `jarvis` no Termux. O Chrome abre sozinho em `http://localhost:8765`.
5. Na primeira vez: **Ajustes → cole a chave grátis do Gemini → Salvar**. A chave é de graça em
   https://aistudio.google.com/app/apikey.
6. No Chrome, menu ⋮ → **Adicionar à tela inicial**. Assim vira um ícone do JARVIS.

## Usar

| Tela | O que tem |
|---|---|
| **Conversa** | Toque no reator e fale. Em **mãos livres**, ele volta a ouvir depois de responder; diga "pode parar" para desligar. Com **só se eu disser "Jarvis"** ligado, ele ignora a conversa em volta e só atende frases com o nome dele. Também dá para digitar. |
| **Modos** | Os 145 modos (loja, treino, debug, festa, Sherlock…). Toque para ligar e toque de novo para sair. Dá para criar o seu. |
| **Plugins** | Os 356 plugins com busca. Liga e desliga cada um, e "usar" já escreve o pedido para você. |
| **Corpo** | O organismo do JARVIS (3.1): nota de saúde, órgãos, sistema imunológico, o que está isolado e os reparos esperando o seu sim — com os botões Autorizar, Negar e Liberar. |
| **Avisos** | Timers, lembretes e resultados longos (tabelas, receitas, relatórios). |
| **Ajustes** | Chave, modelo, seu nome, voz e velocidade da fala. |

Exemplos: "modo treino", "põe um timer de 10 minutos pro bolo", "liga a lanterna", "quanto tá minha bateria?",
"anota na lista leite e ovos", "qual a fase da lua?", "calcula o preço de venda de uma peça de 25 reais com 40% de margem".

## O que funciona no celular

- **Funciona:** tudo que é conversa, conta, lista, memória, loja (clientes, fiado, metas, precificação),
  timers, hábitos, jogos de voz, pesquisas na internet, e o próprio celular pelo plugin `celular_android`
  (bateria, lanterna, vibrar, notificação, copiar, abrir app, localização, volume e foto).
- **Não funciona:** o que mexe no **PC** (teclado, mouse, janelas, webcam do PC, gravar a tela, winget).
  Esses plugins carregam, mas respondem que precisam do computador.
- Os plugins que usam a IA do Gemini funcionam com texto. Os que mandam imagem ou áudio precisam do
  pacote `google-genai`, que costuma não instalar no Termux.

## Dicas

- **Para não fechar sozinho:** o comando `jarvis` segura o celular acordado (`termux-wake-lock`). Em Configurações
  do Android → Apps → Termux → Bateria, escolha **Sem restrições**.
- **Usar de outro aparelho da casa:** `jarvis --rede`. Ele mostra um endereço com senha.
- **Arquivos** (recibos, fotos, dados de teste) vão para `Documentos/JARVIS` no celular.
- **Atualizar:** extraia o zip novo em Download e rode o instalador de novo. As suas memórias e listas ficam.
