# Planta com sede (ESP32) — J.A.R.V.I.S BR 2.5

Um sensor na terra do vaso mede a umidade a cada 30 minutos e manda para o JARVIS. Quando a terra fica seca por algumas horas, ele avisa: *"A planta da sala está com sede: a terra está em 22%."* Se continuar seca, ele lembra uma vez por dia: *"A planta da sala está seca há 2 dias."* Quando você rega, ele percebe sozinho.

## Peças (uns R$ 40 a R$ 60 por planta)

| Peça | Para quê |
|---|---|
| ESP32 DevKit (ESP32-WROOM-32) | Wi-Fi e leitura do sensor |
| Sensor de umidade de solo **capacitivo v1.2** | Medir a terra (o resistivo, de dois garfos, oxida) |
| Fonte USB **ou** bateria 18650 + suporte + módulo TP4056 | Energia (dormindo, a bateria dura semanas) |
| 2 resistores de 100 kΩ (opcional) | Medir a bateria |

## Ligações

| Sensor | ESP32 |
|---|---|
| VCC | GPIO 25 (o ESP32 liga o sensor só na hora de medir) |
| GND | GND |
| AOUT | GPIO 34 |

Opcional, bateria: bateria(+) → 100 kΩ → GPIO 35 → 100 kΩ → GND. Depois tire o `//` da linha `#define PINO_BATERIA 35` no sketch.

## Passo a passo

1. **Arduino IDE.** Instale a placa "esp32" by Espressif (2.0.x ou 3.x). Não precisa de biblioteca extra.
2. **No PC, diga** *"Jarvis, configura a planta"*. Ele liga o servidor dos aparelhos (porta 8765) e mostra o IP do PC e a CHAVE. Na primeira vez, o Windows pede para liberar a porta no firewall: aceite.
3. **Edite o `planta.ino`.** No bloco `CONFIGURE AQUI`, coloque o Wi-Fi (2,4 GHz), o `PC_IP`, a `CHAVE` e o `ID_PLANTA` (um nome curto por vaso: `sala`, `quarto`, `varanda`).
4. **Grave e abra o Monitor Serial (115200).** Deve aparecer `JARVIS respondeu 200`.
5. **Enterre o sensor** até a linha branca, perto da raiz, sem molhar a parte de cima (os componentes).
6. **Dê um nome:** *"Jarvis, o sensor da sala é a samambaia"*. Pergunte *"Jarvis, como estão as plantas?"*.

## Calibrar (recomendado)

Cada sensor lê um pouco diferente. Com o ESP32 ligado:

1. Deixe o sensor **no ar**, seco, e espere ele mandar uma leitura (ou aperte o botão EN para acordar). Diga *"Jarvis, calibra o sensor da sala: está no ar"*.
2. Coloque o sensor num **copo d'água** (até a linha) e repita: *"…está na água"*.

Sem calibrar, ele usa 3000 (seco) e 1300 (água), que servem para a maioria dos sensores v1.2 em 3,3 V.

Cada planta gosta de um ponto: *"Jarvis, a samambaia fica seca abaixo de 40"* muda o limite (o padrão é 30%).

## Problemas comuns

- **`JARVIS respondeu -1`.** O PC não foi encontrado: confira o `PC_IP`, se o JARVIS está aberto e se o firewall liberou a porta 8765.
- **`401`.** A chave está errada. Diga *"Jarvis, configura a planta"* e copie de novo.
- **Leitura sempre 0 ou 4095.** Fio solto, ou o sensor ligado num pino do ADC2. Use o GPIO 34.
- **Bateria acaba rápido.** Placas DevKit gastam alguns mA dormindo por causa do LED e do regulador. Para meses de bateria, use uma placa feita para deep sleep (ex.: FireBeetle ESP32).

## Segurança

A chave fica em `config/esp32.json` e é a mesma para a planta, o painel de LED e a luva. Os dados vão sem criptografia, só dentro da sua rede.
