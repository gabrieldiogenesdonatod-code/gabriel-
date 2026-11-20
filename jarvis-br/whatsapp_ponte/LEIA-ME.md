# WhatsApp do J.A.R.V.I.S (ponte)

Esta pasta liga o JARVIS ao WhatsApp. **Você não precisa rodar nada daqui à mão.**
Diga "Jarvis, liga o WhatsApp" e ele faz o resto.

## Primeira vez

1. Instale o **Node.js LTS** (https://nodejs.org).
   - Se você não instalar, o JARVIS tenta pelo `winget`.
   - Depois, feche e abra o JARVIS.
2. Diga "Jarvis, liga o WhatsApp".
   - Na primeira vez ele roda `npm install` nesta pasta.
   - Isso baixa o `whatsapp-web.js` e um navegador escondido de uns 150 MB, então demora alguns minutos.
3. Um QR code abre na tela. No celular do número que o JARVIS vai usar:
   - WhatsApp → ⋮ → **Aparelhos conectados** → **Conectar um aparelho**
   - leia o QR code.
4. Pronto. O login fica salvo em `memory/whatsapp_sessao`. Para sair, use "Aparelhos conectados" no celular.

## Qual número usar

**Recomendado: um chip só para o JARVIS.**
- Você conversa com ele como com um contato.
- Para ele aceitar os seus pedidos, faça uma destas duas coisas:
  - coloque o seu número em ⚙ CONFIG. DE PLUGINS → *WhatsApp do JARVIS* → *Números do dono*;
  - ou diga "Jarvis, autoriza meu WhatsApp" e mande o código que aparecer.

**Com o seu próprio número:**
- Converse com ele no chat **"Você"** (mensagem para mim).
- As suas outras conversas **não** são lidas pelo JARVIS: a ponte joga fora tudo que não é do dono antes de passar adiante.

## O que dá para fazer

Fale normalmente, como na voz. Alguns exemplos:
- "liga a TV da sala"
- "como está o PC?"
- "me lembra às 18h de pagar a conta de luz"

Atalhos que respondem na hora:

| Atalho | O que faz |
|---|---|
| foto, foto 2 | foto da câmera (a 2ª, a 3ª… são as câmeras IP) |
| tela | print da tela do PC |
| status | CPU, RAM, internet e o que está pesando |
| link | link de uso único para a Central remota (câmeras ao vivo e aparelhos) |
| câmeras | lista as câmeras |
| confirmar / cancelar | responde a uma confirmação pendente (desligar o PC, por exemplo) |
| ajuda | mostra a lista de atalhos |

Áudio também funciona:
- **Áudio** é transcrito (pelo `faster-whisper` ou pela chave do Gemini).
- **Foto com pergunta** na legenda é explicada.

Os avisos do JARVIS (Sentinela, alertas) também chegam no WhatsApp.

## Modo loja (1.9)

Para usar com o **WhatsApp da loja**. Ligue em ⚙ → *WhatsApp do JARVIS* → *Modo loja*.

- Quando um cliente pergunta, por exemplo "tem tamanho 4?", o JARVIS consulta o estoque do Cristal Malhas e escreve um **rascunho** de resposta.
- O rascunho chega para você, no chat de dono, assim: *Rascunho #3*.
- Para responder ao rascunho, mande:
  - **aprovar 3**: envia o rascunho para o cliente, sem o 🤖;
  - **editar 3 seu texto**: envia o seu texto no lugar do rascunho;
  - **ignorar 3**: descarta o rascunho;
  - **rascunhos**: lista os que estão pendentes.
- **Ele nunca responde ao cliente sozinho.**
- Com o modo loja ligado, as conversas particulares do número viram rascunhos. Por isso, ligue esse modo só no número da loja.

## Aviso importante

Isto usa o **WhatsApp Web** (biblioteca `whatsapp-web.js`), não a API oficial da Meta. Os termos do WhatsApp não permitem automação, e a Meta pode limitar ou banir o número.

Para diminuir o risco:
- use um chip separado;
- não mande mensagens em massa nem para quem não pediu.

O JARVIS só responde ao dono e não manda mensagens para outras pessoas por conta própria.

## Arquivos

- `ponte.js`: a ponte. Escuta só em `127.0.0.1` e exige um token novo a cada vez que liga, que só o JARVIS conhece.
- `package.json`: as dependências, instaladas pelo `npm install`.
- `memory/whatsapp_sessao/ponte.log`: o registro da ponte, para quando algo der errado.
