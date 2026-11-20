# Agente do J.A.R.V.I.S BR (para os outros PCs da casa)

Com o agente, o JARVIS do seu PC principal controla os outros PCs da mesma rede:
status, desligar, reiniciar, suspender, bloquear, abrir e fechar programas,
volume, mensagem na tela, print e comandos de terminal.

## Instalar (no OUTRO PC)

1. Instale o Python (marque "Add Python to PATH").
2. Copie esta pasta `agente_pc` para o outro PC (pendrive, rede…).
3. Dê dois cliques em `instalar_agente.bat`
   (ou, no PowerShell da pasta: `python jarvis_agente.py --instalar`).
4. Anote a **CHAVE** que aparece. Opcional: `python -m pip install psutil`
   para o status mostrar CPU e RAM.

O instalador pede para liberar a porta 47777 no firewall. Se não tiver
administrador, ele mostra o comando para rodar no PowerShell **como
administrador**.

## Parear (no PC do JARVIS)

    "Jarvis, procura os aparelhos da rede"
    "Jarvis, o 4 é o PC do quarto"
    "Jarvis, pareia o PC do quarto"     → diga ou digite a chave

## Ligar o PC pela rede (Wake-on-LAN)

Para "Jarvis, liga o PC do quarto" funcionar com ele desligado:

- na BIOS: ative "Wake on LAN" / "Power On by PCI-E";
- no Windows: Gerenciador de Dispositivos → placa de rede → Gerenciamento de
  energia → "Permitir que este dispositivo ative o computador" e, em Avançado,
  "Wake on Magic Packet" = Ativado;
- desligue a "Inicialização rápida" (Opções de energia), que atrapalha o WoL;
- funciona melhor com cabo. Pelo Wi-Fi, quase nenhum PC liga.

## Segurança

Cada pedido vem assinado com a chave (HMAC-SHA256), com a hora (vale 60 s) e um
número que não pode se repetir. Tudo fica em `agente.log`. Para não aceitar
comandos de terminal, ponha `"permitir_comandos": false` no `agente.json`.
Troque a chave com `python jarvis_agente.py --nova-chave` (e pareie de novo).
Para tirar da inicialização: `python jarvis_agente.py --remover`.
