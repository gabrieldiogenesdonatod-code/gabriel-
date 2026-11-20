/*
  J.A.R.V.I.S BR — Modo capacete (ESP32)              fork PT-BR 1.4

  O capacete vira mais um "terminal" do MESMO JARVIS que roda no PC:
  aperte o botão, fale; a resposta sai no alto-falante do capacete.

  PLACA      ESP32 DevKit (ESP32-WROOM-32)
  CORE       "esp32" by Espressif, versão 2.0.x (usa o driver I2S clássico).
             Na 3.x também compila, com avisos de "deprecated".
  BIBLIOTECA "WebSockets" de Markus Sattler (Links2004) — Gerenciador de Bibliotecas

  LIGAÇÕES (veja LEIA-ME.md)
    INMP441 (microfone)   VDD→3V3  GND→GND  L/R→GND  SCK→32  WS→25  SD→33
    MAX98357A (amplific.) VIN→5V   GND→GND  BCLK→26  LRC→27  DIN→22  (+ alto-falante 4–8 Ω)
    Botão de falar        um lado no GPIO 4, o outro no GND
    LED de status         GPIO 2 (o LED azul da própria placa)

  No PC: "Jarvis, configura o capacete" mostra o IP e a CHAVE para colar abaixo.
*/

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>
#include <esp_idf_version.h>

// ======================= CONFIGURE AQUI =======================
const char* WIFI_NOME  = "NOME_DA_SUA_REDE";
const char* WIFI_SENHA = "SENHA_DA_SUA_REDE";
const char* PC_IP      = "192.168.0.10";       // IP do PC com o JARVIS
const uint16_t PC_PORTA = 8000;                // porta HTTP do painel remoto
const char* CHAVE      = "COLE_A_CHAVE_AQUI";  // "Jarvis, configura o capacete"
#define SEMPRE_OUVINDO 0      // 1 = manda áudio quando há voz, sem botão (gasta mais rede)
#define VOLUME 0.6f           // 0.0 a 1.0 (alto-falantes pequenos distorcem no máximo)
// ==============================================================

#define MIC_SCK 32
#define MIC_WS  25
#define MIC_SD  33
#define AMP_BCLK 26
#define AMP_LRC  27
#define AMP_DIN  22
#define BOTAO 4
#define LED   2

#define TAXA_MIC 16000      // o que o JARVIS espera ouvir
#define TAXA_VOZ 24000      // o que o JARVIS manda falar
#define AMOSTRAS 512        // 32 ms de microfone por pacote

WebSocketsClient ws;
bool conectado = false;
bool falando = false;
unsigned long ultimoSom = 0;
int32_t bruto[AMOSTRAS];
int16_t pcm[AMOSTRAS];
int16_t estereo[1024];

void configurarMicrofone() {
  i2s_config_t c;
  memset(&c, 0, sizeof(c));
  c.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
  c.sample_rate = TAXA_MIC;
  c.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  c.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  c.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  c.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  c.dma_buf_count = 8;
  c.dma_buf_len = 256;
  i2s_driver_install(I2S_NUM_0, &c, 0, NULL);

  i2s_pin_config_t p;
  memset(&p, 0, sizeof(p));
  p.bck_io_num = MIC_SCK;
  p.ws_io_num = MIC_WS;
  p.data_out_num = I2S_PIN_NO_CHANGE;
  p.data_in_num = MIC_SD;
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(4, 4, 0)
  p.mck_io_num = I2S_PIN_NO_CHANGE;
#endif
  i2s_set_pin(I2S_NUM_0, &p);
}

void configurarAltoFalante() {
  i2s_config_t c;
  memset(&c, 0, sizeof(c));
  c.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  c.sample_rate = TAXA_VOZ;
  c.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  c.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;   // mono duplicado nos dois lados
  c.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  c.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  c.dma_buf_count = 10;
  c.dma_buf_len = 512;
  c.tx_desc_auto_clear = true;                     // silêncio quando acaba a fala
  i2s_driver_install(I2S_NUM_1, &c, 0, NULL);

  i2s_pin_config_t p;
  memset(&p, 0, sizeof(p));
  p.bck_io_num = AMP_BCLK;
  p.ws_io_num = AMP_LRC;
  p.data_out_num = AMP_DIN;
  p.data_in_num = I2S_PIN_NO_CHANGE;
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(4, 4, 0)
  p.mck_io_num = I2S_PIN_NO_CHANGE;
#endif
  i2s_set_pin(I2S_NUM_1, &p);
}

// A voz do JARVIS chega como PCM 16 bits mono 24 kHz: duplica para L/R e toca.
void tocar(uint8_t* dados, size_t tamanho) {
  int16_t* amostras = (int16_t*)dados;
  size_t n = tamanho / 2;
  size_t i = 0;
  while (i < n) {
    size_t bloco = min((size_t)512, n - i);
    for (size_t k = 0; k < bloco; k++) {
      int16_t v = (int16_t)(amostras[i + k] * VOLUME);
      estereo[2 * k] = v;
      estereo[2 * k + 1] = v;
    }
    size_t escritos = 0;
    i2s_write(I2S_NUM_1, estereo, bloco * 4, &escritos, portMAX_DELAY);
    i += bloco;
  }
}

void aoEvento(WStype_t tipo, uint8_t* dados, size_t tamanho) {
  switch (tipo) {
    case WStype_CONNECTED:
      conectado = true;
      digitalWrite(LED, HIGH);
      ws.sendTXT("{\"tipo\":\"ola\",\"nome\":\"capacete\"}");
      Serial.println("[capacete] conectado ao JARVIS");
      break;
    case WStype_DISCONNECTED:
      conectado = false;
      digitalWrite(LED, LOW);
      Serial.println("[capacete] desconectado; tentando de novo...");
      break;
    case WStype_BIN:
      tocar(dados, tamanho);
      break;
    case WStype_TEXT:
      Serial.printf("[capacete] %.*s\n", (int)tamanho, (char*)dados);
      break;
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BOTAO, INPUT_PULLUP);
  pinMode(LED, OUTPUT);
  configurarMicrofone();
  configurarAltoFalante();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);                     // menos atraso no áudio
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  Serial.print("[capacete] conectando no Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED, !digitalRead(LED));
    delay(300);
    Serial.print(".");
  }
  Serial.printf("\n[capacete] Wi-Fi ok, IP %s\n", WiFi.localIP().toString().c_str());

  String caminho = String("/ws/capacete?chave=") + CHAVE;
  ws.begin(PC_IP, PC_PORTA, caminho.c_str());
  ws.onEvent(aoEvento);
  ws.setReconnectInterval(3000);
  ws.enableHeartbeat(15000, 3000, 2);
}

// Lê um pacote do microfone e converte 32 → 16 bits. Devolve o volume (RMS).
float lerMicrofone() {
  size_t lidos = 0;
  i2s_read(I2S_NUM_0, bruto, sizeof(bruto), &lidos, portMAX_DELAY);
  size_t n = lidos / 4;
  double soma = 0;
  for (size_t i = 0; i < n; i++) {
    int32_t v = bruto[i] >> 14;              // INMP441: 24 bits alinhados à esquerda
    if (v > 32767) v = 32767;
    if (v < -32768) v = -32768;
    pcm[i] = (int16_t)v;
    soma += (double)v * v;
  }
  return n ? sqrt(soma / n) : 0;
}

void loop() {
  ws.loop();
  if (!conectado) {
    return;
  }
  bool apertado = digitalRead(BOTAO) == LOW;
  float rms = lerMicrofone();                // sempre lê, para o buffer não envelhecer

#if SEMPRE_OUVINDO
  if (rms > 900) ultimoSom = millis();
  bool mandar = millis() - ultimoSom < 700;  // 0,7 s depois da última fala
#else
  bool mandar = apertado;
#endif

  if (mandar) {
    ws.sendBIN((uint8_t*)pcm, AMOSTRAS * 2);
    if (!falando) {
      falando = true;
      Serial.println("[capacete] falando...");
    }
    digitalWrite(LED, (millis() / 120) % 2);   // pisca enquanto manda áudio
  } else if (falando) {
    falando = false;
    digitalWrite(LED, HIGH);
    ws.sendTXT("{\"tipo\":\"botao\",\"estado\":\"solto\"}");
  }
}
