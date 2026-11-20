# J.A.R.V.I.S BR — app para Android (APK)

O app roda **o mesmo JARVIS da versão do celular** (os plugins, os 155 modos, o cérebro local, o organismo,
o OMEGA, o livro-razão…) **dentro dele mesmo**. Não precisa de Termux nem do PC ligado.

- **Cérebro "both":** com internet e a chave grátis do Gemini, o Gemini pensa. Sem internet (ou sem chave), o
  **cérebro local** faz sozinho os comandos que já aprendeu com você.
- **Voz:** toque no reator e fale. O app usa o reconhecimento de voz e a voz do próprio Android.
- **Celular:** bateria, lanterna, vibrar, notificação, aviso na tela, copiar e colar, abrir link e app,
  volume, falar pelo alto-falante, discar e compartilhar.
- Relatórios e o **painel OMEGA** abrem dentro do app. Para voltar, use o botão voltar.
- O app continua rodando minimizado, com uma notificação "J.A.R.V.I.S". Assim timers e lembretes funcionam.

## Como gerar o APK (de graça, sem instalar nada no PC)

1. Crie um repositório **privado** no GitHub e envie a pasta `jarvis-br` inteira. Os arquivos `readme.md`,
   `android/` e `.github/` têm que ficar na raiz do repositório.
   - Pelo site: **Add file → Upload files** e arraste o conteúdo da pasta. A pasta `.github` é oculta: no
     Windows, ative "Itens ocultos" no Explorador antes de arrastar.
   - Pelo Git: `git init`, `git add .`, `git commit -m "jarvis"`, `git remote add origin …` e `git push`.
2. Abra a aba **Actions**. A montagem "APK do JARVIS (Android)" começa sozinha e leva uns 10 minutos.
   Também dá para clicar em **Run workflow**.
3. Quando ficar verde, abra a execução e baixe **JARVIS-BR-apk** em **Artifacts**. Vem um .zip com o APK dentro.
4. No celular, abra o APK. O Android vai pedir para **permitir instalar de fontes desconhecidas** para o app de
   arquivos ou para o navegador. Permita e instale.
5. Abra o **J.A.R.V.I.S**, permita o microfone e as notificações e espere carregar. A primeira vez demora mais.
   Depois vá em **Ajustes**, cole a chave do Gemini (https://aistudio.google.com/app/apikey) e salve.

**Atualizar:** gere um APK novo e instale por cima. A assinatura do app é sempre a mesma (`android/app/jarvis.keystore`),
então as suas memórias, listas, chave e livro-razão continuam. **Não desinstale**, senão os dados são apagados.

Também dá para abrir a pasta `android/` no Android Studio, com Python 3.11 instalado no PC, e usar
**Build → Build APK**.

## O que ainda não está no app

- **Do celular_android:** localização, contatos, foto, Wi-Fi e brilho. Esses comandos respondem
  "ainda não está no app". Na versão Termux eles funcionam.
- **Do PC:** teclado, mouse, janelas, webcam e winget. Como na versão Termux, esses plugins dizem que precisam do computador.
- **Alguns plugins de monitorar PC** precisam do pacote `psutil` e ficam desligados no app, sem aviso.
- **IA local que conversa (llama.cpp):** fica só no PC. No celular, sem internet, quem trabalha é o cérebro local de comandos.
- **Usar de outro aparelho da casa** (`--rede`): só na versão Termux.

Se aparecer "O JARVIS não conseguiu ligar", tire uma foto da tela: o erro aparece inteiro ali.
