# Painel de LED na parede (ESP32) — J.A.R.V.I.S BR 2.5

Um letreiro de LEDs que passa da direita para a esquerda, estilo painel de rodoviária:

    15:42 * > Quer Voar - Matue * Hoje: 3 vendas, R$ 245 * Aviso: A conta de luz vence sexta, R$ 142.

Mostra a hora, a música que está tocando (Spotify ou o que estiver no PC), os avisos do JARVIS e as vendas do dia da Cristal Malhas. Aviso novo chega na hora e o painel pisca. A fonte da matriz não tem acento, então o JARVIS manda o texto sem acentos.

## Peças (uns R$ 50 a R$ 80)

| Peça | Para quê |
|---|---|
| ESP32 DevKit (ESP32-WROOM-32) | Wi-Fi |
| Matriz de LED **MAX7219 4 em 1** (FC-16), 32x8 | O letreiro (dá para emendar duas: 64x8) |
| Fonte USB 5 V / 2 A | Energia (muitos LEDs acesos puxam corrente) |

## Ligações

| Matriz | ESP32 |
|---|---|
| VCC | 5V (VIN) |
| GND | GND |
| DIN | GPIO 23 |
| CLK | GPIO 18 |
| CS | GPIO 5 |

## Passo a passo

1. **Arduino IDE.** Placa "esp32" by Espressif. Bibliotecas (Gerenciador de Bibliotecas): **MD_Parola** e **MD_MAX72XX** (majicDesigns) e **ArduinoJson** (Benoit Blanchon, versão 7).
2. **No PC, diga** *"Jarvis, configura o painel de LED"*. Ele mostra o IP do PC e a CHAVE (a mesma da planta e da luva). Aceite o aviso do firewall na primeira vez.
3. **Edite o `painel_led.ino`**: Wi-Fi (2,4 GHz), `PC_IP`, `CHAVE` e `MAX_DEVICES` (4 para um módulo, 8 para dois).
4. **Grave.** O painel mostra "J.A.R.V.I.S" e, em seguida, a hora e o resto.

## Comandos de voz

- *"Jarvis, escreve no painel: Feliz aniversário, mãe!"* — fica 10 minutos (ou *"…por 30 minutos"*).
- *"Jarvis, brilho do painel no 2"* — de 0 a 15.
- *"Jarvis, tira as vendas do painel"* / *"põe a música no painel"*.
- Em ⚙ → Painel de LED dá para ligar e desligar cada item e mudar a velocidade.

## Problemas comuns

- **Letras espelhadas, de cabeça para baixo ou embaralhadas.** Troque `HARDWARE_TYPE` para `MD_MAX72XX::GENERIC_HW` ou `MD_MAX72XX::ICSTATION_HW`.
- **"JARVIS offline (-1)".** O PC não respondeu: confira o `PC_IP`, se o JARVIS está aberto e o firewall (porta 8765).
- **"JARVIS offline (401)".** Chave errada: diga *"Jarvis, configura o painel de LED"* de novo.
- **Pisca fraco ou reinicia.** Fonte fraca: use 5 V / 2 A e baixe o brilho.
