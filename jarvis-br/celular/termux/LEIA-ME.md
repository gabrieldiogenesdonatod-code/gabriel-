# Geofence pelo celular (Android + Termux) — J.A.R.V.I.S BR 1.5

O celular avisa o JARVIS quando você **chega** e quando **sai** de casa:

- **Chegou:** o celular liga o PC pela rede (Wake-on-LAN), o JARVIS roda o protocolo de chegada e dá boas-vindas.
- **Saiu:** a sessão confiável fecha e a Sentinela liga.

O aviso passa por um tópico secreto do **ntfy**, então funciona mesmo quando você já saiu da rede de casa, sem abrir porta no roteador.

## Instalar no celular

1. **Instale os apps pelo F-Droid:** **Termux** e **Termux:API**. A versão da Play Store do Termux está desatualizada. Se quiser que o script volte sozinho quando o celular reiniciar, instale também o **Termux:Boot**.
2. **No Termux:**
   ```
   pkg update && pkg install python termux-api
   termux-setup-storage
   ```
3. **Dê ao Termux:API a permissão de Localização.** O Android exige isso até para ler o nome do Wi-Fi.
4. **Copie o script para o celular:** `jarvis_geofence.py` (desta pasta) vai para a pasta de Downloads.
5. **Pegue as configurações.** No PC, diga *"Jarvis, configura o geofence"* e copie o `TOPICO` e a `CHAVE` para o começo do script. Coloque também o nome do seu Wi-Fi em `REDE_CASA`. Se quiser que o PC ligue quando você chegar, coloque o MAC do PC em `PC_MAC`.
6. **Rode:**
   ```
   termux-wake-lock
   python ~/storage/downloads/jarvis_geofence.py
   ```
7. **(Opcional) Iniciar sozinho:**
   ```
   mkdir -p ~/.termux/boot
   echo 'termux-wake-lock; python ~/storage/downloads/jarvis_geofence.py' > ~/.termux/boot/jarvis.sh
   ```

## Ligar o PC ao chegar (Wake-on-LAN)

- **Na BIOS:** ative "Wake on LAN" (ou "Power On by PCI-E").
- **No Windows:** em Gerenciador de Dispositivos → placa de rede → Gerenciamento de Energia, marque "Permitir que este dispositivo ative o computador" e "Somente um pacote mágico". Desligue também a "Inicialização rápida" em Opções de Energia.
- **Funciona com o PC desligado ou suspenso,** desde que esteja no cabo de rede. Pelo Wi-Fi, a maioria das placas não liga.
- **Para o JARVIS abrir sozinho com o Windows,** crie um atalho do `iniciar.bat` em `shell:startup`.

## Testar

- *"Jarvis, simula que eu cheguei"* / *"simula que eu saí"*: testa o lado do PC.
- *"Jarvis, status do geofence"*: mostra se o PC está ouvindo e qual foi o último aviso.
