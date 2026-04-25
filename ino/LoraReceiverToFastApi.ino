#include <arduino_lmic.h>
#include <arduino_lmic_hal_boards.h>
#include <arduino_lmic_hal_configuration.h>
#include <arduino_lmic_lorawan_compliance.h>
#include <arduino_lmic_user_configuration.h>
#include <lmic.h>
#include "LoRaWan_APP.h"
#include "Arduino.h"
#include <ArduinoJson.h>

#include <WiFiClientSecure.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "HT_SSD1306Wire.h"
#include "mbedtls/base64.h"

static SSD1306Wire display(0x3c, 500000, SDA_OLED, SCL_OLED, GEOMETRY_128_64, RST_OLED); // addr , freq , i2c group , resolution , rst
WiFiClientSecure client;
String jwtToken;
unsigned long tokenExpiry = 0;

// -------- WIFI --------
const char* ssid = "XXX"; //"YYY";
const char* password = "XXXX";//"YYY";
const char* ESP32_TOKEN_ADMIN_KEY = "xxxxxxxxxxxxxxxxxxx"; // do NOT embed real admin keys in production devices
const char* root_ca = \
"-----BEGIN CERTIFICATE-----\n" \
"jasjdfkaduj7sd6fdBkdsjsdfasdjfhasdhfakjs\n" \
"....."
"-----END CERTIFICATE-----\n";

// -------- FASTAPI --------
const char* serverName = "https://xxxxxx.com"; // change IP "192.168.1.2:8000"

#define RECEIVER_ID "LIMPIEZA"
#define RF_FREQUENCY 868000000
#define BUFFER_SIZE 30

char rxpacket[BUFFER_SIZE];

static RadioEvents_t RadioEvents;

// Global variables for non-blocking OLED
unsigned long displayTimeout = 0;
bool messageDisplayed = false;

// Define thresholds (tune as needed)
#define RSSI_GOOD -80   // RSSI stronger (less negative) than -80 is good
#define RSSI_POOR -100  // RSSI weaker than -100 is poor
#define SNR_GOOD 5      // SNR above 5 is good
#define SNR_POOR 0      // SNR below 0 is poor

// -------- FUNCTION --------
void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr);


bool isTokenValid() {
    return jwtToken.length() > 0 && (millis() / 1000) < tokenExpiry;
}

void updateTokenIfNeeded() {

    if (isTokenValid()) {
        Serial.println("Using cached token");
        return;
    }

    Serial.println("Refreshing JWT token...");

    jwtToken = requestToken();

    if (jwtToken.length() > 0) {
        tokenExpiry = getJWTExpiry(jwtToken);

        Serial.print("Token expires at: ");
        Serial.println(tokenExpiry);
    } else {
        Serial.println("Token request failed");
    }
}

unsigned long getJWTExpiry(String token) {

    int firstDot = token.indexOf('.');
    int secondDot = token.indexOf('.', firstDot + 1);

    String payload = token.substring(firstDot + 1, secondDot);

    // Base64url → Base64 fix
    payload.replace('-', '+');
    payload.replace('_', '/');

    // Add padding if needed
    while (payload.length() % 4) {
        payload += '=';
    }

    unsigned char decoded[256];
    size_t out_len = 0;

    mbedtls_base64_decode(
        decoded,
        sizeof(decoded),
        &out_len,
        (const unsigned char*)payload.c_str(),
        payload.length()
    );

    decoded[out_len] = '\0';

    StaticJsonDocument<256> doc;
    deserializeJson(doc, (char*)decoded);

    return doc["exp"] | 0;
}

String requestToken() {
  // If SERVER_BASE uses https:// use WiFiClientSecure and validate cert in production.

  client.setCACert(root_ca);;
  HTTPClient http;
  String url = String(serverName) + "/token";
  Serial.print("Requesting token from: "); Serial.println(url);

  if (!http.begin(client, url)) {
    Serial.println("HTTP begin failed");
    return String();
  }
  http.addHeader("Content-Type", "application/json");

  // Build request JSON: {"admin_key":"...","sub":"device-001"}
  StaticJsonDocument<256> req;
  req["admin_key"] = ESP32_TOKEN_ADMIN_KEY;
  req["sub"] = "esp32-device-1";
  String body;
  serializeJson(req, body);

  int code = http.POST(body);
  if (code != 200) {
    Serial.print("Token request failed, code="); Serial.println(code);
    String resp = http.getString();
    Serial.println(resp);
    http.end();
    return String();
  }

  String resp = http.getString();
  http.end();

  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, resp);
  if (err) {
    Serial.println("Failed to parse token response");
    return String();
  }
  const char* token = doc["token"];
  if (!token) {
    Serial.println("No token field in response");
    return String();
  }
  Serial.println("Got token: " + String(token));
  return String(token);
}

void setup() {
   Serial.begin(115200);
   while (!Serial);
   delay(1000);

   Serial.println("Receptor V3 iniciado");

   // -------- WIFI CONNECT --------
   WiFi.begin(ssid, password);
   Serial.print("Connecting WiFi");

   while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
   }

   Serial.println("\nWiFi connected!");
   Serial.println(WiFi.localIP());
   configTime(0, 0, "pool.ntp.org", "time.nist.gov");

   // -------- LORA INIT --------
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

   VextON();
   delay(100);
   // Initialising the UI will init the display too.
   display.init();
}

void loop() {
   Radio.IrqProcess();

     // Check if it's time to clear OLED
   if (messageDisplayed && millis() > displayTimeout) {
       display.clear();
       display.display();   // must call display() after clearing
       messageDisplayed = false;
   }
}

// -------- SEND TO FASTAPI --------
void sendToAPI(String message, int16_t rssi, int8_t snr) {
   if (WiFi.status() == WL_CONNECTED) {
       updateTokenIfNeeded();  // 👈 ONLY refresh if needed

    if (!jwtToken.length()) {
        Serial.println("No valid token");
        return;
    }
      if (jwtToken.length()) {
        HTTPClient http;
        client.setCACert(root_ca);;
        http.begin(String(serverName) + "/door");
        http.addHeader("Content-Type", "application/json");
        http.addHeader("Authorization", "Bearer " + jwtToken);
        // JSON payload
        String json = "{";
        json += "\"device_id\":\"limpieza\",";
        json += "\"state\":\"" + message + "\",";
        json += "\"rssi\":\"" + String(rssi)+ "\",";
        json += "\"snr\":\"" + String(snr)+ "\"";
        json += "}";

        int httpResponseCode = http.POST(json);
        Serial.print("JSON: " + json);
        Serial.print("HTTP Response: ");
        Serial.println(httpResponseCode);

        if (httpResponseCode > 0) {
            String response = http.getString(); // get full response body
            Serial.println("Server response:");
            Serial.println(response);
        } else {
            Serial.print("Error on sending POST: ");
            Serial.println(http.errorToString(httpResponseCode));
        }

        http.end();
    } else {
        Serial.println("WiFi not connected or incorrect token");
    }
   }
}

// -------- LORA CALLBACK --------
void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr) {

   memcpy(rxpacket, payload, size);
   rxpacket[size] = '\0';

   String msg = String(rxpacket);

   Serial.print("Recibido: ");
   Serial.println(msg);

   Serial.print("RSSI: ");
   Serial.println(rssi);

   // -------- CHECK IF MESSAGE IS FOR ME --------
   if (msg.indexOf(RECEIVER_ID) >= 0) {

      Serial.println("👉 Mensaje para ESTE nodo");
      // Draw to OLED
      drawTextFlowDemo(msg, rssi, snr);
      display.display();  // update display buffer
      messageDisplayed = true;
      displayTimeout = millis() + 11500; // show for 1.5 seconds

      // 👉 SEND TO API
      sendToAPI(msg, rssi, snr);
   } else {
      Serial.println("❌ No es para este nodo");
   }

   // -------- BACK TO RX --------
   delay(50);
   Radio.Rx(0);
}

void VextON(void)
{
  pinMode(Vext,OUTPUT);
  digitalWrite(Vext, LOW);
}

void VextOFF(void) //Vext default OFF
{
  pinMode(Vext,OUTPUT);
  digitalWrite(Vext, HIGH);
}

void drawTextFlowDemo(String msg, int16_t rssi, int8_t snr) {
    display.clear();
    display.setFont(ArialMT_Plain_16);
    display.setTextAlignment(TEXT_ALIGN_LEFT);
        // Assess RSSI
    String rssiStatus;
    if (rssi >= RSSI_GOOD) {
        rssiStatus = "Good";
    } else if (rssi <= RSSI_POOR) {
        rssiStatus = "Poor";
    } else {
        rssiStatus = "Fair";
    }

    // Assess SNR
    String snrStatus;
    if (snr >= SNR_GOOD) {
        snrStatus = "Good";
    } else if (snr <= SNR_POOR) {
        snrStatus = "Poor";
    } else {
        snrStatus = "Fair";
    }
    display.drawStringMaxWidth(0, 0, 128, msg);
    display.drawString(0, 20, "RSSI: " + String(rssi) + " " + rssiStatus);
    display.drawString(0, 40, "SNR: " + String(snr)+ " " + snrStatus);
}