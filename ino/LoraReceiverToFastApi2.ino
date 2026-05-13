#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

#include <ArduinoJson.h>
#include <mbedtls/base64.h>

#include "LoRaWan_APP.h"
#include "Arduino.h"
#include "HT_SSD1306Wire.h"

// ======================================================
// OLED
// ======================================================

static SSD1306Wire display(
    0x3c,
    500000,
    SDA_OLED,
    SCL_OLED,
    GEOMETRY_128_64,
    RST_OLED
);

// -------- WIFI --------
const char* ssid = "";
const char* password = "";
const char* ESP32_TOKEN_ADMIN_KEY = ""; // do NOT embed real admin keys in production devices
// ======================================================
// ROOT CA
// ======================================================
const char* root_ca = \
"-----BEGIN CERTIFICATE-----\n" \

"-----END CERTIFICATE-----\n";

// -------- FASTAPI --------
const char* serverName = ""; //"";// change IP "192.168.1.142:8000"

WiFiClientSecure client;

// ======================================================
// LORA
// ======================================================

#define RF_FREQUENCY 868000000
#define RECEIVER_ID "LIMPIEZA"

#define BUFFER_SIZE 128

char rxpacket[BUFFER_SIZE];

static RadioEvents_t RadioEvents;

// ======================================================
// MESSAGE QUEUE
// ======================================================

volatile bool newMessage = false;

char pendingMessage[BUFFER_SIZE];

int16_t pendingRSSI = 0;
int8_t pendingSNR = 0;

// ======================================================
// JWT
// ======================================================

String jwtToken = "";
unsigned long tokenExpiry = 0;

// ======================================================
// OLED TIMER
// ======================================================

bool messageDisplayed = false;
unsigned long displayTimeout = 0;

// ======================================================
// RSSI / SNR THRESHOLDS
// ======================================================

#define RSSI_GOOD -80
#define RSSI_POOR -100

#define SNR_GOOD 5
#define SNR_POOR 0

// ======================================================
// FUNCTION DECLARATIONS
// ======================================================

void OnRxDone(uint8_t *payload, uint16_t size,
              int16_t rssi, int8_t snr);

void ensureWiFi();

void processMessage();

void sendToAPI(const char* message,
               int16_t rssi,
               int8_t snr);

String requestToken();

bool isTokenValid();

void updateTokenIfNeeded();

unsigned long getJWTExpiry(String token);

void drawTextFlowDemo(String msg,
                      int16_t rssi,
                      int8_t snr);

void VextON();

// ======================================================
// SETUP
// ======================================================

void setup() {

    Serial.begin(115200);

    delay(1000);

    Serial.println();
    Serial.println("Receiver started");

    // ------------------------------------------
    // OLED
    // ------------------------------------------

    VextON();

    delay(100);

    display.init();

    display.clear();
    display.display();

    // ------------------------------------------
    // WIFI
    // ------------------------------------------

    WiFi.mode(WIFI_STA);

    ensureWiFi();

    configTime(0, 0,
               "pool.ntp.org",
               "time.nist.gov");

    // ------------------------------------------
    // TLS
    // ------------------------------------------

    client.setCACert(root_ca);

    // ------------------------------------------
    // LORA
    // ------------------------------------------

    Mcu.begin(HELTEC_BOARD, SLOW_CLK_TPYE);

    RadioEvents.RxDone = OnRxDone;

    Radio.Init(&RadioEvents);

    Radio.SetChannel(RF_FREQUENCY);

    Radio.SetRxConfig(
        MODEM_LORA,
        0,
        7,
        1,
        0,
        8,
        0,
        false,
        0,
        true,
        0,
        0,
        false,
        true
    );

    Radio.Rx(0);

    Serial.println("LoRa RX ready");
}

// ======================================================
// LOOP
// ======================================================

void loop() {

    // Process radio IRQ
    Radio.IrqProcess();

    // Process pending message OUTSIDE callback
    if (newMessage) {

        noInterrupts();

        newMessage = false;

        char localMessage[BUFFER_SIZE];

        strncpy(localMessage,
                pendingMessage,
                BUFFER_SIZE);

        int16_t localRSSI = pendingRSSI;
        int8_t localSNR = pendingSNR;

        interrupts();

        processMessageInternal:
        {
            String msg = String(localMessage);

            Serial.println();
            Serial.print("Received: ");
            Serial.println(msg);

            Serial.print("RSSI: ");
            Serial.println(localRSSI);

            Serial.print("SNR: ");
            Serial.println(localSNR);

            if (msg.indexOf(RECEIVER_ID) >= 0) {

                Serial.println("Message for this node");

                drawTextFlowDemo(
                    msg,
                    localRSSI,
                    localSNR
                );

                display.display();

                messageDisplayed = true;

                displayTimeout = millis();

                sendToAPI(
                    localMessage,
                    localRSSI,
                    localSNR
                );
            }
            else {

                Serial.println("Not for this node");
            }
        }
    }

    // OLED timeout
    if (messageDisplayed &&
        millis() - displayTimeout > 10000UL) {

        display.clear();
        display.display();

        messageDisplayed = false;
    }

    delay(2);
}

// ======================================================
// CALLBACK
// VERY SHORT CALLBACK
// ======================================================

void OnRxDone(uint8_t *payload,
              uint16_t size,
              int16_t rssi,
              int8_t snr) {

    if (size >= BUFFER_SIZE) {
        size = BUFFER_SIZE - 1;
    }

    memcpy(pendingMessage, payload, size);

    pendingMessage[size] = '\0';

    pendingRSSI = rssi;
    pendingSNR = snr;

    newMessage = true;

    // Restart RX IMMEDIATELY
    Radio.Rx(0);
}

// ======================================================
// WIFI RECONNECT
// ======================================================

void ensureWiFi() {

    if (WiFi.status() == WL_CONNECTED) {
        return;
    }

    Serial.println("Connecting WiFi...");

    WiFi.disconnect(true);

    delay(1000);

    WiFi.begin(ssid, password);

    unsigned long startAttempt = millis();

    while (WiFi.status() != WL_CONNECTED &&
           millis() - startAttempt < 15000) {

        delay(500);
        Serial.print(".");
    }

    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {

        Serial.println("WiFi connected");
        Serial.println(WiFi.localIP());
    }
    else {

        Serial.println("WiFi FAILED");
    }
}

// ======================================================
// JWT VALIDATION
// ======================================================

bool isTokenValid() {

    unsigned long now = time(nullptr);

    return jwtToken.length() > 0 &&
           now < tokenExpiry - 60;
}

// ======================================================
// UPDATE TOKEN
// ======================================================

void updateTokenIfNeeded() {

    if (isTokenValid()) {

        Serial.println("Using cached JWT");

        return;
    }

    Serial.println("Refreshing JWT...");

    jwtToken = requestToken();

    if (jwtToken.length() > 0) {

        tokenExpiry = getJWTExpiry(jwtToken);

        Serial.print("Token expiry: ");
        Serial.println(tokenExpiry);
    }
}

// ======================================================
// GET JWT EXP
// ======================================================

unsigned long getJWTExpiry(String token) {

    int firstDot = token.indexOf('.');
    int secondDot = token.indexOf('.', firstDot + 1);

    if (firstDot < 0 || secondDot < 0) {
        return 0;
    }

    String payload =
        token.substring(firstDot + 1, secondDot);

    payload.replace('-', '+');
    payload.replace('_', '/');

    while (payload.length() % 4) {
        payload += '=';
    }

    unsigned char decoded[256];

    size_t out_len = 0;

    int result = mbedtls_base64_decode(
        decoded,
        sizeof(decoded) - 1,
        &out_len,
        (const unsigned char*)payload.c_str(),
        payload.length()
    );

    if (result != 0) {
        return 0;
    }

    decoded[out_len] = '\0';

    StaticJsonDocument<256> doc;

    if (deserializeJson(doc, decoded)) {
        return 0;
    }

    return doc["exp"] | 0;
}

// ======================================================
// REQUEST TOKEN
// ======================================================

String requestToken() {

    ensureWiFi();

    if (WiFi.status() != WL_CONNECTED) {
        return "";
    }

    HTTPClient http;

    String url = String(serverName) + "/token";

    Serial.println(url);

    if (!http.begin(client, url)) {

        Serial.println("HTTP begin failed");

        return "";
    }

    http.addHeader("Content-Type",
                   "application/json");

    StaticJsonDocument<256> req;

    req["admin_key"] = ESP32_TOKEN_ADMIN_KEY;
    req["sub"] = "esp32-device-1";

    String body;

    serializeJson(req, body);

    int code = http.POST(body);

    if (code != 200) {

        Serial.print("Token failed: ");
        Serial.println(code);

        http.end();

        return "";
    }

    String response = http.getString();

    http.end();

    StaticJsonDocument<512> doc;

    if (deserializeJson(doc, response)) {

        Serial.println("JSON parse failed");

        return "";
    }

    return doc["token"] | "";
}

// ======================================================
// SEND API
// ======================================================

void sendToAPI(const char* message,
               int16_t rssi,
               int8_t snr) {

    ensureWiFi();

    if (WiFi.status() != WL_CONNECTED) {

        Serial.println("WiFi disconnected");

        return;
    }

    updateTokenIfNeeded();

    if (!jwtToken.length()) {

        Serial.println("No valid JWT");

        return;
    }

    HTTPClient http;

    String url = String(serverName) + "/door";

    if (!http.begin(client, url)) {

        Serial.println("HTTP begin failed");

        return;
    }

    http.addHeader("Content-Type",
                   "application/json");

    http.addHeader("Authorization",
                   "Bearer " + jwtToken);

    StaticJsonDocument<256> doc;

    doc["device_id"] = "limpieza";
    doc["state"] = message;
    doc["rssi"] = rssi;
    doc["snr"] = snr;

    String json;

    serializeJson(doc, json);

    Serial.println(json);

    int code = http.POST(json);

    Serial.print("HTTP code: ");
    Serial.println(code);

    if (code > 0) {

        String response = http.getString();

        Serial.println(response);
    }
    else {

        Serial.println(http.errorToString(code));
    }

    http.end();
}

// ======================================================
// OLED
// ======================================================

void drawTextFlowDemo(String msg,
                      int16_t rssi,
                      int8_t snr) {

    display.clear();

    display.setFont(ArialMT_Plain_16);

    display.setTextAlignment(TEXT_ALIGN_LEFT);

    String rssiStatus;

    if (rssi >= RSSI_GOOD) {
        rssiStatus = "Good";
    }
    else if (rssi <= RSSI_POOR) {
        rssiStatus = "Poor";
    }
    else {
        rssiStatus = "Fair";
    }

    String snrStatus;

    if (snr >= SNR_GOOD) {
        snrStatus = "Good";
    }
    else if (snr <= SNR_POOR) {
        snrStatus = "Poor";
    }
    else {
        snrStatus = "Fair";
    }

    display.drawStringMaxWidth(
        0,
        0,
        128,
        msg
    );

    display.drawString(
        0,
        20,
        "RSSI: " + String(rssi)
    );

    display.drawString(
        0,
        40,
        "SNR: " + String(snr)
    );
}

// ======================================================
// POWER
// ======================================================

void VextON() {

    pinMode(Vext, OUTPUT);

    digitalWrite(Vext, LOW);
}

void VextOFF() {

    pinMode(Vext, OUTPUT);

    digitalWrite(Vext, HIGH);
}
