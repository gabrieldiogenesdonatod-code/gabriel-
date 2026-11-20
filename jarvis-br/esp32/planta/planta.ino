/*
  J.A.R.V.I.S BR — Planta com sede (ESP32)              fork PT-BR 2.5

  Mede a umidade da terra, manda para o JARVIS no PC e volta a dormir.
  Na bateria, dura semanas: acorda a cada 30 minutos, fica uns 3 segundos
  acordado e dorme (deep sleep).

  PLACA      ESP32 DevKit (ESP32-WROOM-32) — core "esp32" by Espressif 2.0.x ou 3.x
  BIBLIOTECA nenhuma além das que já vêm com o core (WiFi, HTTPClient)
  SENSOR     umidade de solo CAPACITIVO v1.2 (o resistivo, de dois garfos, oxida em semanas)

  LIGAÇÕES (veja LEIA-ME.md)
    Sensor VCC  → GPIO 25  (o ESP32 liga o sensor só na hora de medir)
    Sensor GND  → GND
    Sensor AOUT → GPIO 34  (ADC1: os pinos do ADC2 não leem com o Wi-Fi ligado)

  No PC: "Jarvis, configura a planta" mostra o IP e a CHAVE para colar abaixo.
*/

#include <WiFi.h>
#include <HTTPClient.h>

// ======================= CONFIGURE AQUI =======================
const char* WIFI_NOME   = "NOME_DA_SUA_REDE";
const char* WIFI_SENHA  = "SENHA_DA_SUA_REDE";
const char* PC_IP       = "192.168.0.10";       // IP do PC com o JARVIS
const uint16_t PC_PORTA = 8765;                 // porta dos aparelhos ESP32
const char* CHAVE       = "COLE_A_CHAVE_AQUI";  // "Jarvis, configura a planta"
const char* ID_PLANTA   = "sala";               // um nome por planta: sala, quarto, varanda...
const int MINUTOS_DORMINDO = 30;
// #define PINO_BATERIA 35   // tire o // se ligou a bateria num divisor 100k/100k no GPIO 35
// ==============================================================

#define PINO_SENSOR  34
#define PINO_ENERGIA 25

int lerSensor() {
  pinMode(PINO_ENERGIA, OUTPUT);
  digitalWrite(PINO_ENERGIA, HIGH);
  delay(300);                                   // o sensor capacitivo precisa estabilizar
  long soma = 0;
  for (int i = 0; i < 16; i++) {
    soma += analogRead(PINO_SENSOR);
    delay(10);
  }
  digitalWrite(PINO_ENERGIA, LOW);
  return (int)(soma / 16);
}

float lerBateria() {
#ifdef PINO_BATERIA
  return analogReadMilliVolts(PINO_BATERIA) * 2 / 1000.0;   // divisor de 2
#else
  return 0;
#endif
}

void dormir() {
  esp_sleep_enable_timer_wakeup((uint64_t)MINUTOS_DORMINDO * 60ULL * 1000000ULL);
  esp_deep_sleep_start();
}

void setup() {
  Serial.begin(115200);
  delay(50);
  // o ADC do ESP32 já começa em 12 bits e 11 dB (lê de 0 a ~3,1 V)
  int bruto = lerSensor();
  float bateria = lerBateria();
  Serial.printf("leitura do sensor: %d   bateria: %.2f V\n", bruto, bateria);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(200);
  }
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.setTimeout(5000);
    String url = String("http://") + PC_IP + ":" + PC_PORTA + "/esp32/planta?k=" + CHAVE;
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    String corpo = String("{\"id\":\"") + ID_PLANTA + "\",\"bruto\":" + bruto;
    if (bateria > 0.5) {
      corpo += String(",\"bateria\":") + String(bateria, 2);
    }
    corpo += "}";
    int codigo = http.POST(corpo);
    Serial.printf("JARVIS respondeu %d: %s\n", codigo, http.getString().c_str());
    http.end();
  } else {
    Serial.println("sem Wi-Fi; tento de novo no proximo ciclo");
  }
  WiFi.disconnect(true);
  dormir();
}

void loop() {
  // nunca chega aqui: o setup() termina dormindo
}
