# Luva repulsor (ESP32) — J.A.R.V.I.S BR 2.5

Abra a mão com a palma para a frente, como o Homem de Ferro: o PC toca o som do repulsor e o JARVIS faz uma ação. Por padrão:

| Gesto | Como fazer | Ação padrão |
|---|---|---|
| **repulsor** | dedos para cima, palma para a frente, e **abrir** a mão (com o sensor de flexão) ou dar um **empurrão** para a frente (sem ele) | fechar a janela da frente |
| **punho** | fechar a mão | nada |
| **tapa_direita** / **tapa_esquerda** | mão deitada (palma para o chão), passar rápido para o lado | próximo slide / slide anterior |
| **cima** / **baixo** | mão deitada, levantar ou abaixar rápido o punho | volume + / volume − |

Cada ação muda em ⚙ → Luva repulsor ou por voz: *"Jarvis, o repulsor passa o slide"*. Ações possíveis: fechar janela, minimizar, próximo slide, slide anterior, play/pausa, próxima música, volume +/−, print da tela e chamar o JARVIS. A janela do próprio JARVIS e os programas protegidos nunca são fechados (o "fechar" é o mesmo do Alt+F4: o programa pergunta se quer salvar).

*"Jarvis, trava a luva"* faz ele ignorar os gestos (bom para quando for tirar a luva).

## Peças (uns R$ 50 a R$ 90)

| Peça | Para quê |
|---|---|
| ESP32 (DevKit ou um "mini", que cabe melhor na mão) | Wi-Fi |
| **MPU6050** (placa GY-521) | Acelerômetro e giroscópio: a pose e os movimentos |
| Sensor de flexão 2.2" + resistor de 47 kΩ (opcional, recomendado) | Saber quando a mão abre e fecha |
| Motor de vibracall + transistor (opcional) | Um "tranco" quando o repulsor dispara |
| Bateria LiPo pequena + módulo TP4056, ou power bank | Energia |
| Uma luva (de ciclismo funciona bem) | Prender tudo |

## Ligações

| Peça | Pino | ESP32 |
|---|---|---|
| MPU6050 | VCC / GND | 3V3 / GND |
| MPU6050 | SDA / SCL | GPIO 21 / GPIO 22 |
| Flexão | uma ponta | 3V3 |
| Flexão | outra ponta | GPIO 34, e um resistor de 47 kΩ dela até o GND |
| Vibracall | (via transistor) | GPIO 26 |

**Posição do MPU6050:** nas costas da mão, com a seta **X** da plaquinha apontando para os dedos e os componentes para cima. O sensor de flexão vai por cima do dedo indicador.

## Passo a passo

1. **Arduino IDE.** Placa "esp32" by Espressif. Não precisa de biblioteca extra.
2. **No PC, diga** *"Jarvis, configura a luva"* e copie o IP e a CHAVE para o bloco `CONFIGURE AQUI` do `luva.ino`. Aceite o aviso do firewall na primeira vez.
3. **Grave e abra o Monitor Serial (115200).** Mexa a mão e olhe os números:
   - com a mão deitada (palma para o chão), `az` fica perto de **1,0**;
   - com os dedos para cima, `ax` fica perto de **1,0**;
   - `flexao`: anote o valor com a mão aberta e fechada e ajuste `FLEX_ABERTA` e `FLEX_FECHADA` (um pouco para dentro de cada valor).
4. **Teste no PC:** *"Jarvis, testa o repulsor"* toca o som e faz a ação sem a luva.
5. Se esquerda/direita ou cima/baixo saírem trocados, mude `INVERTER_LADOS` / `INVERTER_CIMA` para 1.

Sem o sensor de flexão, mude `USAR_FLEXAO` para 0: o repulsor dispara com os dedos para cima e um empurrão rápido para a frente.

## Problemas comuns

- **Nada acontece no PC.** Veja no Monitor Serial a linha `JARVIS: …`. `-1` = PC não encontrado (IP, JARVIS aberto, firewall da porta 8765); `401` = chave errada.
- **Dispara sozinho.** Aumente `GIRO_TAPA` (ex.: 300) ou afaste `FLEX_ABERTA` e `FLEX_FECHADA`.
- **O MPU6050 não responde.** Confira SDA/SCL. Algumas placas GY-521 usam o endereço 0x69 (pino AD0 ligado no VCC): mude `#define MPU 0x69`.
