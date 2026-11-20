# Modo capacete (ESP32) — J.A.R.V.I.S BR 1.4

O capacete vira mais um terminal do **mesmo** JARVIS que roda no PC. Você aperta o botão e fala; a resposta sai no alto-falante do capacete. O áudio entra pela mesma fila do microfone do celular. Não roda um segundo assistente.

## Peças (total aproximado de R$ 60 a R$ 90)

| Peça | Para quê |
|---|---|
| ESP32 DevKit (ESP32-WROOM-32) | Wi-Fi e processamento |
| Microfone I2S **INMP441** | Ouvir você |
| Amplificador I2S **MAX98357A** e alto-falante de 3 W, 4–8 Ω | A voz do JARVIS |
| Botão (push button) | Apertar para falar |
| Power bank USB | Alimentar o capacete |

## Ligações

| Módulo | Pino do módulo | ESP32 |
|---|---|---|
| INMP441 | VDD / GND / L/R | 3V3 / GND / GND |
| INMP441 | SCK / WS / SD | GPIO 32 / GPIO 25 / GPIO 33 |
| MAX98357A | VIN / GND | 5V (VIN) / GND |
| MAX98357A | BCLK / LRC / DIN | GPIO 26 / GPIO 27 / GPIO 22 |
| Botão | um lado / outro lado | GPIO 4 / GND |

O LED azul da placa (GPIO 2) mostra o estado:
- piscando devagar: procurando o Wi-Fi;
- aceso: conectado ao JARVIS;
- piscando rápido: mandando a sua voz.

## Passo a passo

1. **Arduino IDE.** Instale a placa "esp32" by Espressif (versão 2.0.x é a mais testada). Depois instale a biblioteca **WebSockets** de *Markus Sattler* pelo Gerenciador de Bibliotecas.
2. **No PC, abra o painel remoto** pelo botão ◉ CONTROLE REMOTO do JARVIS. É ele que sobe o servidor das portas 8000 e 8001.
3. **Pegue a configuração.** Diga *"Jarvis, configura o capacete"*. O painel mostra o IP do PC e a chave do capacete.
4. **Edite o `capacete.ino`.** No bloco `CONFIGURE AQUI`, coloque o nome e a senha do Wi-Fi, o `PC_IP` e a `CHAVE`.
5. **Grave no ESP32.** Abra o Monitor Serial em 115200 e confira se aparece `conectado ao JARVIS`.
6. **Teste.** Aperte o botão, fale *"Jarvis, que horas são?"* e solte. A resposta sai no capacete e no PC.

## Problemas comuns

- **Não conecta, mas o Wi-Fi está ok.** Confira se o painel remoto está aberto no PC e se o firewall liberou a porta 8000. Na primeira abertura do painel, o JARVIS pede permissão.
- **"4001" no Monitor Serial.** A chave está errada ou foi trocada. Diga "Jarvis, configura o capacete" de novo e copie a chave.
- **Voz picotando.** Use a rede de 2,4 GHz perto do roteador e mantenha `WiFi.setSleep(false)`.
- **Som distorcido.** Baixe o `VOLUME` no sketch, por exemplo para 0.4.
- **O microfone do PC fica mudo.** Isso só acontece enquanto o capacete manda áudio, igual ao microfone do celular. Ao soltar o botão, o microfone do PC volta em cerca de 1 segundo.

## Segurança

A chave do capacete fica no `config/capacete.json` e não expira. Se perder o capacete, diga *"Jarvis, gera outra chave do capacete"*.

O áudio vai sem criptografia pela porta 8000, só dentro da sua rede. Use apenas em redes confiáveis.
