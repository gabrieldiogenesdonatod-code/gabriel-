# J.A.R.V.I.S só no celular

Esta pasta é o JARVIS que roda **inteiro no celular**, sem precisar do computador. São só 4 arquivos (`index.html`, `manifest.webmanifest`, `sw.js` e `icone.svg`) que você hospeda de graça uma vez. Depois disso, o app fica instalado no celular.

## Publicar de graça (uma vez, uns 5 minutos)

O navegador só deixa usar o microfone e instalar o app se a página estiver em **HTTPS**. O jeito mais fácil de conseguir isso de graça é o GitHub Pages:

1. Entre em https://github.com e crie um repositório **público** chamado `jarvis-celular`.
2. Clique em **Add file → Upload files** e arraste os 4 arquivos desta pasta. Depois clique em **Commit changes**.
3. Vá em **Settings → Pages**:
   - em **Source**, escolha **Deploy from a branch**;
   - em branch, escolha `main` e a pasta `/ (root)`;
   - clique em **Save**.
4. Em 1 ou 2 minutos, o app fica no ar em: `https://SEU-USUARIO.github.io/jarvis-celular/`

O repositório pode ser público sem problema: a sua chave **não** fica nos arquivos, só no celular.

Outros lugares grátis que também funcionam: Netlify, Cloudflare Pages ou Vercel. Basta arrastar a pasta.

## Instalar no celular

1. Abra o endereço no **Chrome** do Android.
2. Toque em ⚙ e cole a sua chave **grátis** do Gemini (pegue em https://aistudio.google.com/app/apikey).
3. No menu ⋮, toque em **Instalar app** (ou **Adicionar à tela inicial**).
4. Abra pelo ícone, toque no círculo e fale.

No iPhone, use o Safari: Compartilhar → **Adicionar à Tela de Início**. Lá, o reconhecimento de voz depende da versão do iOS; se não funcionar, digite.

## O que ele faz sozinho no celular

| Diga | O que faz |
|---|---|
| "lembra que eu gosto de rap geek" | guarda na memória dele, neste celular (🧠 mostra tudo) |
| "anota: comprar leite" / "o que eu anotei?" | notas e listas |
| "qual o placar do jogo?" / "vai chover hoje?" | pesquisa na internet |
| "toca Kaiser" | abre a música no Spotify ou no YouTube Music |
| "manda no WhatsApp que eu chego às 8" | prepara a mensagem; você escolhe o contato e confirma |
| "liga para 62 9…" | abre o discador; você confirma |
| "rota para o shopping" | abre a rota no Google Maps |
| "marca dentista amanhã às 15h" | cria o evento no Google Agenda; você confirma |
| "me lembra daqui a 20 minutos de tirar o bolo" | lembrete com notificação |
| 🎙 **Mãos livres** | depois de cada resposta, ele volta a ouvir; para desligar, diga "pode parar" |

Ele **não** controla o PC nem a casa. Para isso, ponha o endereço do JARVIS do PC em ⚙. Aí ele abre o modo completo quando o PC estiver ligado.

## Limites (para não ter surpresa)

- **Para pensar, precisa de internet.** O app abre sem internet, mas as respostas vêm do Gemini, na nuvem do Google.
- **O uso da chave grátis do Gemini tem limite diário.** Se passar do limite, ele avisa.
- **A memória e as notas ficam só neste celular.** Use 🧠 → "Copiar backup" para guardar ou levar para outro aparelho.
- **Lembretes longos podem atrasar.** Se o app ficar fechado muito tempo, o Android pode atrasar o aviso. Para coisas importantes, peça para pôr na agenda.
