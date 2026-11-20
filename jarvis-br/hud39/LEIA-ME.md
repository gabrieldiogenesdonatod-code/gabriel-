# 🛰 HUD 3.9

O painel J.A.R.V.I.S 3.9 vivo: a arte do HUD com os números reais do seu PC, animações e tudo clicável.

## 3.9.3 — J.A.R.V.I.S na capa, YouTube na tela e ★ SALVOS

- A capa é o **J.A.R.V.I.S**. O botão **⇄ TROCAR PARA SEXTA-FEIRA** fica na própria tela (e volta com ⇄ J.A.R.V.I.S).
- **Barra de botões** na tela: ⏮ ⏯ ⏭, volume − e +, **▶ YouTube** e **★ Salvos**.
- **Tudo abre por cima da interface**, dentro da janela: nenhum clique abre aba ou janela nova. Clique fora do painel
  ou no ✕ para fechar.
- **YouTube sem abrir o YouTube**: escreva na caixa `youtube: receita de bolo` e aperte Enter. Aparecem os vídeos com
  miniatura; clique num para ele tocar aqui, na tela do JARVIS. A ★ salva o vídeo.
- **★ SALVOS**: escreva `salvar: comprar tecido amanhã` (ou fale "Jarvis, salva que…"). No painel ★ SALVOS, clique
  num item para usar (texto vai para a caixa, vídeo toca na tela) e no ✕ para apagar. Fica em `memory/salvos.json`.

## F.R.I.D.A.Y / SEXTA-FEIRA (3.9.2)

O centro da janela do JARVIS agora é a F.R.I.D.A.Y: a imagem dela com os hologramas, o menu clicável à
esquerda e os números do PC à direita. O orbe do dedo e a plataforma de baixo reagem à voz; no mudo, tudo
apaga e o aviso fica vermelho. Clique no orbe ou na plataforma para escrever; no menu, nos painéis da imagem
ou nos cartões da direita para abrir o painel deles. A caixa de escrever, o mudo, o falar e os botões do
microfone continuam iguais. Para trocar: ⚙ → **HUD:** (F.R.I.D.A.Y → HUD 3.9 → rosto → núcleo reator).

## HUD 3.9 na tela principal

O HUD 3.9 é o centro da janela do JARVIS, no lugar do rosto. A caixa de escrever, o mudo, o falar e os botões
do microfone continuam onde sempre estiveram. Clique no círculo JARVIS para escrever; nas outras partes, para
abrir o painel delas. Para voltar ao rosto: ⚙ → botão **HUD:** (alterna HUD 3.9 → rosto → núcleo reator).

## Como abrir em tela própria

- **Voz:** "Jarvis, abre o HUD" (tela cheia) ou "Jarvis, abre o HUD em janela".
- **Botão:** gaveta de controles → **🛰 HUD 3.9**.
- **Sem o JARVIS:** dois cliques em **`abrir_hud.bat`** (Windows) ou `./abrir_hud.sh` (Linux/macOS), ou `python -m hud39`.
  Só o painel: os comandos de voz pedem o JARVIS aberto. Para abrir em janela, sem tela cheia: `abrir_hud.bat --sem-tela-cheia`.

Abre no Edge ou no Chrome em modo aplicativo (sem barra de endereço). Sem eles, no navegador padrão.
O endereço é http://127.0.0.1:18091/.

## O que cada parte faz

| Onde clicar | O que acontece |
|---|---|
| SISTEMA, logo, quadro SISTEMA/REDE | Sobre o sistema · Sobre o J.A.R.V.I.S · Discos |
| INTERNET, globo, radar | IP, Wi-Fi, ping na hora, uso de hoje, abrir navegador, pesquisar pelo JARVIS |
| ARQUIVOS | Documentos, Downloads, Imagens, Área de trabalho, pasta pessoal |
| MÚSICA | Tocar/pausar, anterior, próxima, volume e mudo (teclas de mídia do Windows) |
| VÍDEOS | Pasta de vídeos, YouTube e busca pelo JARVIS |
| JOGOS | Steam, modo jogo, arcade e o desempenho agora |
| CONFIG, reator do canto | Cor do HUD, sons, animações, varredura, partículas, abertura |
| Círculo JARVIS (ou espaço) | Falar ou digitar um comando para o JARVIS |
| Reator do peito, temperatura | Diagnóstico animado |
| PROCESSOS, GPU, RAM/DISCO/REDE | Detalhes |
| Relógio de baixo (ou F) | Tela cheia |

Atalhos: **espaço** fala com o JARVIS · **F** tela cheia · **Esc** fecha o painel · **1–7** botões do menu.

## Observações

- A temperatura da CPU só aparece quando o Windows informa (em muitos PCs, só como administrador). Uso e
  temperatura da GPU aparecem em placas NVIDIA.
- O microfone do HUD usa o reconhecimento de voz do Edge/Chrome. Na primeira vez, o navegador pede permissão.
- Segurança: só 127.0.0.1, conferência do Host e token em toda ação. Nada é apagado, instalado ou finalizado.
