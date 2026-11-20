/*
  J.A.R.V.I.S BR — Painel de LED na parede (ESP32)       fork PT-BR 2.5

  Letreiro que passa da direita para a esquerda: hora, a música que está
  tocando, os avisos do JARVIS e as vendas do dia. Cada vez que o texto termina
  de passar, ele pergunta ao PC o que mostrar agora. Aviso novo: pisca 3 vezes.

  PLACA       ESP32 DevKit (ESP32-WROOM-32) — core "esp32" by Espressif 2.0.x ou 3.x
  BIBLIOTECAS (Gerenciador de Bibliotecas)
              "MD_Parola" e "MD_MAX72XX" de majicDesigns
              "ArduinoJson" de Benoit Blanchon (versão 7)
  MATRIZ      módulo MAX7219 "4 em 1" (FC-16), 32x8 LEDs; dá para emendar 2 (64x8)

  LIGAÇÕES (veja LEIA-ME.md)
    Matriz VCC → 5V (VIN)   GND → GND   DIN → GPIO 23   CLK → GPIO 18   CS → GPIO 5

  No PC: "Jarvis, configura o painel de LED" mostra o IP e a CHAVE para colar abaixo.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <MD_Parola.h>
#include <MD_MAX72xx.h>
#include <SPI.h>

// ======================= CONFIGURE AQUI =======================
const char* WIFI_NOME   = "NOME_DA_SUA_REDE";
const char* WIFI_SENHA  = "SENHA_DA_SUA_REDE";
const char* PC_IP       = "192.168.0.10";       // IP do PC com o JARVIS
const uint16_t PC_PORTA = 8765;                 // porta dos aparelhos ESP32
const char* CHAVE       = "COLE_A_CHAVE_AQUI";  // "Jarvis, configura o painel de LED"
#define MAX_DEVICES 4                           // blocos 8x8: 4 = um módulo 4 em 1; 8 = dois emendados
#define HARDWARE_TYPE MD_MAX72XX::FC16_HW       // se aparecer espelhado/embaralhado: GENERIC_HW ou ICSTATION_HW
// ==============================================================

#define CS_PIN 5            // DIN = GPIO 23 e CLK = GPIO 18 são o SPI padrão do ESP32

MD_Parola painel = MD_Parola(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);
char texto[400] = "J.A.R.V.I.S";
uint16_t velocidade = 35;
bool alerta = false;

void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 10000) {
    delay(200);
  }
}

void buscar() {
  conectarWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    strlcpy(texto, "Sem Wi-Fi", sizeof(texto));
    alerta = false;
    return;
  }
  HTTPClient http;
  http.setTimeout(4000);
  http.begin(String("http://") + PC_IP + ":" + PC_PORTA + "/esp32/painel?k=" + CHAVE);
  int codigo = http.GET();
  if (codigo == 200) {
    JsonDocument doc;
    DeserializationError erro = deserializeJson(doc, http.getString());
    if (!erro) {
      strlcpy(texto, doc["texto"] | "J.A.R.V.I.S", sizeof(texto));
      painel.setIntensity((uint8_t)(doc["brilho"] | 4));
      velocidade = doc["velocidade"] | 35;
      alerta = doc["alerta"] | false;
    }
  } else {
    snprintf(texto, sizeof(texto), "JARVIS offline (%d)", codigo);
    alerta = false;
  }
  http.end();
}

void piscar() {
  for (int i = 0; i < 3; i++) {
    painel.displayShutdown(true);
    delay(150);
    painel.displayShutdown(false);
    delay(150);
  }
}

void setup() {
  Serial.begin(115200);
  painel.begin();
  painel.setIntensity(4);
  painel.displayClear();
  painel.displayText(texto, PA_LEFT, velocidade, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
  conectarWiFi();
  Serial.println(WiFi.status() == WL_CONNECTED ? "Wi-Fi ok" : "sem Wi-Fi ainda");
}

void loop() {
  if (painel.displayAnimate()) {               // o texto terminou de passar
    buscar();
    if (alerta) piscar();
    painel.displayText(texto, PA_LEFT, velocidade, 0, PA_SCROLL_LEFT, PA_SCROLL_LEFT);
  }
}
