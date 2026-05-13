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


// -------- FASTAPI --------
const char* serverName = "https://r.costabravas.com"; //"http://r.costabravas.com/door";// change IP "192.168.1.142:8000"

// ======================================================
// WIFI CLIENT
// ======================================================

WiFiClientSecure client;

// ======================================================
// LORA
// ======================================================

#define RF_FREQUENCY 868000000
#define RECEIVER_ID "LIMPIEZA"

static RadioEvents_t RadioEvents;

// ======================================================
// PACKET QUEUE
// ======================================================

#define MAX_QUEUE 10
#define MAX_MESSAGE_SIZE 128

struct Packet {

    char msg[MAX_MESSAGE_SIZE];

    int16_t rssi;

    int8_t snr;
};

volatile uint8_t queueHead = 0;
volatile uint8_t queueTail = 0;

Packet packetQueue[MAX_QUEUE];

// ======================================================
// JWT
// ======================================================

String jwtToken = "";

unsigned long tokenExpiry = 0;

bool timeReady = false;

// ======================================================
// OLED
// ======================================================

bool messageDisplayed = false;

unsigned long displayTimeout = 0;

// ======================================================
// SIGNAL QUALITY
// ======================================================

#define RSSI_GOOD -80
#define RSSI_POOR -100

#define SNR_GOOD 5
#define SNR_POOR 0

// ======================================================
// FUNCTION DECLARATIONS
// ======================================================

void OnRxDone(
    uint8_t *payload,
    uint16_t size,
    int16_t rssi,
    int8_t snr
);

void ensureWiFi();

bool enqueuePacket(
    const char* msg,
    int16_t rssi,
    int8_t snr
);

bool dequeuePacket(Packet &packet);

void processPacket(Packet &packet);

void sendToAPI(
    const char* message,
    int16_t rssi,
    int8_t snr
);

bool isTokenValid();

void updateTokenIfNeeded();

String requestToken();

unsigned long getJWTExpiry(String token);

void drawTextFlowDemo(
    const char* msg,
    int16_t rssi,
    int8_t snr
);

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

    WiFi.setSleep(false);

    ensureWiFi();

    // ------------------------------------------
    // NTP
    // ------------------------------------------

    configTime(
        0,
        0,
        "pool.ntp.org",
        "time.nist.gov"
    );

    struct tm timeinfo;

    if (getLocalTime(&timeinfo, 10000)) {

        timeReady = true;

        Serial.println("NTP synced");
    }
    else {

        Serial.println("NTP FAILED");
    }

    // ------------------------------------------
    // TLS
    // ------------------------------------------

    client.setCACert(root_ca);

    client.setTimeout(5);

    client.setHandshakeTimeout(5);

    // ------------------------------------------
    // LORA
    // ------------------------------------------

    Mcu.begin(
        HELTEC_BOARD,
        SLOW_CLK_TPYE
    );

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

    Radio.IrqProcess();

    Packet packet;

    while (dequeuePacket(packet)) {

        processPacket(packet);
    }

    // OLED timeout

    if (
        messageDisplayed &&
        millis() - displayTimeout > 10000UL
    ) {

        display.clear();

        display.display();

        messageDisplayed = false;
    }

    // Heap monitor

    static unsigned long lastHeapPrint = 0;

    if (millis() - lastHeapPrint > 30000) {

        lastHeapPrint = millis();

        Serial.printf(
            "Free heap: %u\n",
            ESP.getFreeHeap()
        );
    }

    delay(2);
}

// ======================================================
// LORA CALLBACK
// ======================================================

void OnRxDone(
    uint8_t *payload,
    uint16_t size,
    int16_t rssi,
    int8_t snr
) {

    if (size >= MAX_MESSAGE_SIZE) {

        size = MAX_MESSAGE_SIZE - 1;
    }

    char buffer[MAX_MESSAGE_SIZE];

    memcpy(buffer, payload, size);

    buffer[size] = '\0';

    enqueuePacket(buffer, rssi, snr);

    Radio.Rx(0);
}

// ======================================================
// ENQUEUE
// ======================================================

bool enqueuePacket(
    const char* msg,
    int16_t rssi,
    int8_t snr
) {

    uint8_t nextHead =
        (queueHead + 1) % MAX_QUEUE;

    // Queue full

    if (nextHead == queueTail) {

        Serial.println("Queue FULL");

        return false;
    }

    strncpy(
        packetQueue[queueHead].msg,
        msg,
        MAX_MESSAGE_SIZE
    );

    packetQueue[queueHead]
        .msg[MAX_MESSAGE_SIZE - 1] = '\0';

    packetQueue[queueHead].rssi = rssi;

    packetQueue[queueHead].snr = snr;

    queueHead = nextHead;

    return true;
}

// ======================================================
// DEQUEUE
// ======================================================

bool dequeuePacket(Packet &packet) {

    noInterrupts();

    if (queueTail == queueHead) {

        interrupts();

        return false;
    }

    packet = packetQueue[queueTail];

    queueTail =
        (queueTail + 1) % MAX_QUEUE;

    interrupts();

    return true;
}

// ======================================================
// PROCESS PACKET
// ======================================================

void processPacket(Packet &packet) {

    Serial.println();
    Serial.print("Received: ");
    Serial.println(packet.msg);

    Serial.print("RSSI: ");
    Serial.println(packet.rssi);

    Serial.print("SNR: ");
    Serial.println(packet.snr);

    if (
        strstr(packet.msg, RECEIVER_ID)
        == nullptr
    ) {

        Serial.println("Not for this node");

        return;
    }

    Serial.println("Message for this node");

    drawTextFlowDemo(
        packet.msg,
        packet.rssi,
        packet.snr
    );

    display.display();

    messageDisplayed = true;

    displayTimeout = millis();

    sendToAPI(
        packet.msg,
        packet.rssi,
        packet.snr
    );
}

// ======================================================
// WIFI
// ======================================================

void ensureWiFi() {

    if (WiFi.status() == WL_CONNECTED) {

        return;
    }

    Serial.println("Connecting WiFi...");

    WiFi.begin(ssid, password);

    unsigned long start =
        millis();

    while (
        WiFi.status() != WL_CONNECTED &&
        millis() - start < 15000
    ) {

        delay(500);

        Serial.print(".");
    }

    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {

        Serial.println("WiFi connected");

        Serial.println(
            WiFi.localIP()
        );
    }
    else {

        Serial.println("WiFi FAILED");
    }
}

// ======================================================
// JWT
// ======================================================

bool isTokenValid() {

    if (!timeReady) {

        return false;
    }

    unsigned long now = time(nullptr);

    return (
        jwtToken.length() > 0 &&
        now < tokenExpiry - 60
    );
}

// ======================================================
// UPDATE TOKEN
// ======================================================

void updateTokenIfNeeded() {

    if (isTokenValid()) {

        return;
    }

    Serial.println("Refreshing JWT");

    jwtToken = requestToken();

    if (jwtToken.length()) {

        tokenExpiry =
            getJWTExpiry(jwtToken);

        Serial.print("Token exp: ");

        Serial.println(tokenExpiry);
    }
}

// ======================================================
// JWT EXP
// ======================================================

unsigned long getJWTExpiry(
    String token
) {

    int firstDot =
        token.indexOf('.');

    int secondDot =
        token.indexOf(
            '.',
            firstDot + 1
        );

    if (
        firstDot < 0 ||
        secondDot < 0
    ) {

        return 0;
    }

    String payload =
        token.substring(
            firstDot + 1,
            secondDot
        );

    payload.replace('-', '+');

    payload.replace('_', '/');

    while (payload.length() % 4) {

        payload += '=';
    }

    unsigned char decoded[256];

    size_t out_len = 0;

    int result =
        mbedtls_base64_decode(
            decoded,
            sizeof(decoded) - 1,
            &out_len,
            (const unsigned char*)
                payload.c_str(),
            payload.length()
        );

    if (result != 0) {

        return 0;
    }

    decoded[out_len] = '\0';

    StaticJsonDocument<256> doc;

    if (
        deserializeJson(doc, decoded)
    ) {

        return 0;
    }

    return doc["exp"] | 0;
}

// ======================================================
// REQUEST TOKEN
// ======================================================

String requestToken() {

    ensureWiFi();

    if (
        WiFi.status() != WL_CONNECTED
    ) {

        return "";
    }

    HTTPClient http;

    String url =
        String(serverName) +
        "/token";

    if (!http.begin(client, url)) {

        Serial.println(
            "HTTP begin failed"
        );

        return "";
    }

    http.setTimeout(5000);

    http.addHeader(
        "Content-Type",
        "application/json"
    );

    StaticJsonDocument<256> req;

    req["admin_key"] =
        ESP32_TOKEN_ADMIN_KEY;

    req["sub"] =
        "esp32-device-1";

    String body;

    serializeJson(req, body);

    int code =
        http.POST(body);

    if (code != 200) {

        Serial.print(
            "Token failed: "
        );

        Serial.println(code);

        http.end();

        return "";
    }

    String response =
        http.getString();

    http.end();

    StaticJsonDocument<512> doc;

    if (
        deserializeJson(
            doc,
            response
        )
    ) {

        return "";
    }

    return doc["token"] | "";
}

// ======================================================
// SEND API
// ======================================================

void sendToAPI(
    const char* message,
    int16_t rssi,
    int8_t snr
) {

    ensureWiFi();

    if (
        WiFi.status() != WL_CONNECTED
    ) {

        return;
    }

    updateTokenIfNeeded();

    if (!jwtToken.length()) {

        return;
    }

    HTTPClient http;

    String url =
        String(serverName) +
        "/door";

    if (!http.begin(client, url)) {

        return;
    }

    http.setTimeout(5000);

    http.addHeader(
        "Content-Type",
        "application/json"
    );

    http.addHeader(
        "Authorization",
        "Bearer " + jwtToken
    );

    StaticJsonDocument<256> doc;

    doc["device_id"] =
        "limpieza";

    doc["state"] =
        message;

    doc["rssi"] =
        rssi;

    doc["snr"] =
        snr;

    String json;

    serializeJson(doc, json);

    int code =
        http.POST(json);

    Serial.print("HTTP: ");

    Serial.println(code);

    if (code > 0) {

        String response =
            http.getString();

        Serial.println(response);
    }
    else {

        Serial.println(
            http.errorToString(code)
        );
    }

    http.end();
}

// ======================================================
// OLED
// ======================================================

void drawTextFlowDemo(
    const char* msg,
    int16_t rssi,
    int8_t snr
) {

    display.clear();

    display.setFont(
        ArialMT_Plain_16
    );

    display.setTextAlignment(
        TEXT_ALIGN_LEFT
    );

    char line[64];

    display.drawStringMaxWidth(
        0,
        0,
        128,
        msg
    );

    snprintf(
        line,
        sizeof(line),
        "RSSI: %d",
        rssi
    );

    display.drawString(
        0,
        20,
        line
    );

    snprintf(
        line,
        sizeof(line),
        "SNR: %d",
        snr
    );

    display.drawString(
        0,
        40,
        line
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