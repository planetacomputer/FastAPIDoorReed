#include <RadioLib.h>
#include "Arduino.h"

// Heltec Lora Esp32 V2
// -------- LORA PINS --------
#define LORA_CS    18
#define LORA_RST   14
#define LORA_DIO0  26

// -----RECEVIER IDENTIFICATOR FOR VALIDATION-----
#define RECEIVER_ID "LIMPIEZA"

SX1276 radio = new Module(LORA_CS, LORA_DIO0, LORA_RST, -1);

// -------- REED SWITCH --------
#define REED_PIN 33

// -------- BATTERY PIN --------
#define VBAT_PIN 37

// -------- RTC MEMORY --------
RTC_DATA_ATTR int messageCounter = 0;
RTC_DATA_ATTR bool lastDoorState = false;

// -------- LORA europe --------
#define RF_FREQUENCY 868.0

// -------- CONFIG --------
#define DEBUG 0   // set to 1 for debugging



// -------- FUNCTIONS --------
float readBatteryVoltage() {
  uint16_t adc = analogRead(VBAT_PIN);
  return ((float)adc / 4095.0) * 3.3 * 2;
}

int readBatteryPercent() {
  float v = readBatteryVoltage();
  if (v >= 4.20) return 100;
  else if (v >= 4.00) return map(v * 100, 400, 420, 75, 100);
  else if (v >= 3.80) return map(v * 100, 380, 400, 50, 75);
  else if (v >= 3.60) return map(v * 100, 360, 380, 25, 50);
  else if (v >= 3.30) return map(v * 100, 330, 360, 0, 25);
  else return 0;
}

void setupWakeup(bool doorOpen) {
  if (doorOpen) {
    esp_sleep_enable_ext0_wakeup((gpio_num_t)REED_PIN, 1); // wait HIGH
  } else {
    esp_sleep_enable_ext0_wakeup((gpio_num_t)REED_PIN, 0); // wait LOW
  }
}

void goToSleep(bool doorOpen) {
  setupWakeup(doorOpen);
  esp_deep_sleep_start();
}

void setup() {

  if (DEBUG){
    #define DEBUG_PRINT(x) Serial.print(x);
    #define DEBUG_PRINTLN(x) Serial.println(x);
    #define DEBUG_PRINTF(x,y) Serial.printf(x,y);
  }
  else{
    #define DEBUG_PRINT(x)
    #define DEBUG_PRINTLN(x)
    #define DEBUG_PRINTF(x,y)
  }

  if (DEBUG)
    Serial.begin(115200);

  pinMode(REED_PIN, INPUT_PULLUP);

  // -------- READ STATE --------
  bool doorOpen = digitalRead(REED_PIN) == LOW;

  // -------- DEBOUNCE --------
  delay(20);
  bool confirm = digitalRead(REED_PIN) == LOW;
  if (doorOpen != confirm) {
    goToSleep(lastDoorState); // ignore bounce
  }

  // -------- CHECK CHANGE --------
  if (doorOpen == lastDoorState) {
      DEBUG_PRINTLN("No change");
      goToSleep(doorOpen);
  }

  // -------- STATE CHANGED --------
  lastDoorState = doorOpen;
  messageCounter++;

  DEBUG_PRINTF("State changed: %s\n", doorOpen ? "CLOSED" : "OPEN");

  // -------- INIT LORA ONLY NOW --------
  if (radio.begin(RF_FREQUENCY) != RADIOLIB_ERR_NONE) {
    goToSleep(doorOpen);
  }

  radio.setSpreadingFactor(7);
  radio.setBandwidth(125.0);
  radio.setCodingRate(5);
  radio.setOutputPower(3); //5

char msg[32];
float battery = 0;
// -------- BATTERY (rare) --------
if (messageCounter % 200 == 0 || messageCounter < 10) {
  battery = readBatteryPercent();
  DEBUG_PRINTF("Battery: %.2f%\n", battery);
}

snprintf(msg, sizeof(msg), "%s|%d|%d|%d",
         "LIMPIEZA",
         doorOpen ? 1 : 0,
         messageCounter, int(battery));

// Send
radio.transmit(msg);

// -------- SLEEP ASAP --------
radio.sleep();
goToSleep(doorOpen);
}

void loop() {}