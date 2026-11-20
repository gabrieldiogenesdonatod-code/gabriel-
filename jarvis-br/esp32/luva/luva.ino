/*
  J.A.R.V.I.S BR — Luva repulsor (ESP32 + MPU6050)        fork PT-BR 2.5

  Abra a mão com a palma para a frente (a pose do repulsor do Homem de Ferro):
  o PC toca o som do repulsor e o JARVIS faz a ação (por padrão, fecha a janela
  da frente). Passar a mão para os lados troca de slide; levantar/abaixar mexe
  no volume. As ações de cada gesto mudam em ⚙ → Luva repulsor, no PC.

  PLACA      ESP32 DevKit ou ESP32 mini (D1 mini ESP32) — core "esp32" 2.0.x ou 3.x
  BIBLIOTECA nenhuma além das do core (Wire, WiFi, HTTPClient): o MPU6050 é lido direto
  SENSORES   MPU6050 (GY-521) nas costas da mão: eixo X apontando para os dedos
             sensor de flexão 2.2" no dedo indicador (opcional, recomendado)

  LIGAÇÕES (veja LEIA-ME.md)
    MPU6050  VCC → 3V3   GND → GND   SDA → GPIO 21   SCL → GPIO 22
    Flexão   uma ponta → 3V3; a outra → GPIO 34 e um resistor de 47 kΩ até o GND
    Vibracall (opcional) → GPIO 26 (com transistor) — dá um "tranco" quando dispara
    LED da placa (GPIO 2) pisca a cada gesto

  No PC: "Jarvis, configura a luva" mostra o IP e a CHAVE para colar abaixo.
  Abra o Monitor Serial (115200) para ver os números e ajustar os limites.
*/

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ======================= CONFIGURE AQUI =======================
const char* WIFI_NOME   = "NOME_DA_SUA_REDE";
const char* WIFI_SENHA  = "SENHA_DA_SUA_REDE";
const char* PC_IP       = "192.168.0.10";       // IP do PC com o JARVIS
const uint16_t PC_PORTA = 8765;                 // porta dos aparelhos ESP32
const char* CHAVE       = "COLE_A_CHAVE_AQUI";  // "Jarvis, configura a luva"
#define USAR_FLEXAO 1          // 0 = sem sensor de flexão (o repulsor dispara com um "empurrão")
#define FLEX_ABERTA 2300       // leitura acima disto = mão aberta (veja no Monitor Serial)
#define FLEX_FECHADA 1900      // leitura abaixo disto = mão fechada
#define GIRO_TAPA 220.0        // graus/s para contar como "passar a mão"
#define INVERTER_LADOS 0       // 1 se esquerda/direita saírem trocados
#define INVERTER_CIMA 0        // 1 se cima/baixo saírem trocados
// ==============================================================

#define MPU 0x68
#define PINO_FLEX 34
#define PINO_VIBRA 26
#define LED 2

float ax, ay, az, gx, gy, gz;
bool maoAberta = true;
unsigned long ultimoGesto = 0;

void mpuEscrever(uint8_t reg, uint8_t valor) {
  Wire.beginTransmission(MPU);
  Wire.write(reg);
  Wire.write(valor);
  Wire.endTransmission(true);
}

void mpuIniciar() {
  Wire.begin(21, 22);
  Wire.setClock(400000);
  mpuEscrever(0x6B, 0x00);     // acorda
  mpuEscrever(0x1C, 0x10);     // acelerômetro ±8 g   (4096 por g)
  mpuEscrever(0x1B, 0x18);     // giroscópio ±2000 °/s (16,4 por °/s)
  mpuEscrever(0x1A, 0x03);     // filtro passa-baixa ~44 Hz
}

bool mpuLer() {
  Wire.beginTransmission(MPU);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint16_t)MPU, (uint8_t)14, true) != 14) return false;
  int16_t v[7];
  for (int i = 0; i < 7; i++) {
    uint8_t alto = Wire.read();
    uint8_t baixo = Wire.read();
    v[i] = (int16_t)((alto << 8) | baixo);
  }
  ax = v[0] / 4096.0;  ay = v[1] / 4096.0;  az = v[2] / 4096.0;
  gx = v[4] / 16.4;    gy = v[5] / 16.4;    gz = v[6] / 16.4;   // v[3] é a temperatura
  return true;
}

void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);        // resposta rápida
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 10000) {
    digitalWrite(LED, !digitalRead(LED));
    delay(200);
  }
  digitalWrite(LED, LOW);
}

void avisarPC(const char* gesto) {
  Serial.printf("gesto: %s\n", gesto);
  digitalWrite(LED, HIGH);
  digitalWrite(PINO_VIBRA, HIGH);
  conectarWiFi();
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.setTimeout(2500);
    http.begin(String("http://") + PC_IP + ":" + PC_PORTA + "/esp32/luva?k=" + CHAVE);
    http.addHeader("Content-Type", "application/json");
    int codigo = http.POST(String("{\"gesto\":\"") + gesto + "\"}");
    Serial.printf("  JARVIS: %d %s\n", codigo, http.getString().c_str());
    http.end();
  }
  delay(80);
  digitalWrite(PINO_VIBRA, LOW);
  digitalWrite(LED, LOW);
  ultimoGesto = millis();
}

void setup() {
  Serial.begin(115200);
  pinMode(LED, OUTPUT);
  pinMode(PINO_VIBRA, OUTPUT);
  digitalWrite(PINO_VIBRA, LOW);
  // o ADC do ESP32 já começa em 12 bits e 11 dB (lê de 0 a ~3,1 V)
  mpuIniciar();
  conectarWiFi();
  Serial.println("luva pronta. Mexa a mão e veja os números para ajustar os limites.");
}

void loop() {
  if (!mpuLer()) {
    delay(20);
    return;
  }
  unsigned long agora = millis();
  bool livre = agora - ultimoGesto > 700;          // um gesto de cada vez
  bool dedosPraCima = ax > 0.7;                    // eixo X (dedos) apontando para o teto
  bool palmaPraBaixo = az > 0.7;                   // mão deitada, palma para o chão

#if USAR_FLEXAO
  int flex = analogRead(PINO_FLEX);
  static unsigned long ultimoPrint = 0;
  if (agora - ultimoPrint > 500) {
    Serial.printf("ax %.2f ay %.2f az %.2f | gx %.0f gy %.0f gz %.0f | flexao %d\n", ax, ay, az, gx, gy, gz, flex);
    ultimoPrint = agora;
  }
  if (maoAberta && flex < FLEX_FECHADA) {
    maoAberta = false;
    if (livre) avisarPC("punho");
  } else if (!maoAberta && flex > FLEX_ABERTA) {
    maoAberta = true;
    if (livre && dedosPraCima) avisarPC("repulsor");   // abriu a mão com a palma para a frente
  }
#else
  float forca = sqrt(ax * ax + ay * ay + az * az);
  if (livre && dedosPraCima && forca > 1.9) {      // pose do repulsor + um "empurrão" para a frente
    avisarPC("repulsor");
    return;
  }
#endif

  if (!livre || !palmaPraBaixo) {
    delay(10);
    return;
  }
  float lado = INVERTER_LADOS ? -gz : gz;
  float cima = INVERTER_CIMA ? -gy : gy;
  if (lado < -GIRO_TAPA) avisarPC("tapa_direita");
  else if (lado > GIRO_TAPA) avisarPC("tapa_esquerda");
  else if (cima < -GIRO_TAPA) avisarPC("cima");
  else if (cima > GIRO_TAPA) avisarPC("baixo");
  delay(10);
}
