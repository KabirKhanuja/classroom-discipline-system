/*
========================================================
SMART CLASSROOM SENSOR NODE
FINAL CORRECT CODE
========================================================

MODE 1 = Shared Channel
MODE 2 = ESP NOW Aggregator
MODE 3 = Separate Channels

========================================================
CHANGE ONLY:
1. MODE
2. SENSOR_ID
========================================================
*/

#define MODE 2

/*
========================================================
SENSOR ID

1 = LEFT SENSOR
2 = RIGHT SENSOR
========================================================
*/

#define SENSOR_ID 1

/*
========================================================
LIBRARIES
========================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <esp_now.h>

/*
========================================================
WIFI
========================================================
*/

const char* ssid = "1222";
const char* password = "12345678";

/*
========================================================
THINGSPEAK API KEYS
========================================================
*/

// MODE 1
String sharedApiKey =
"X5CMI1X9K04SWGSE";

// MODE 3
String leftChannelApi =
"BM2O2NDXZD5Z5VW7";

String rightChannelApi =
"9N64AVZST2DU5O72";

/*
========================================================
SERVER
========================================================
*/

const char* server =
"https://api.thingspeak.com/update";

/*
========================================================
AGGREGATOR MAC ADDRESS
========================================================
*/

uint8_t aggregatorAddress[] =
{0xEC, 0xE3, 0x34, 0x1A, 0x00, 0xCC};

/*
========================================================
PINS
========================================================
*/

const int micPin = 34;
const int buzzerPin = 25;

int threshold = 1800;

/*
========================================================
ESP NOW DATA STRUCTURE
========================================================
*/

typedef struct struct_message {

  int sensorID;
  int value;

} struct_message;

struct_message myData;

/*
========================================================
SETUP
========================================================
*/

void setup() {

  Serial.begin(115200);

  pinMode(buzzerPin, OUTPUT);

  /*
  ======================================================
  WIFI STATION MODE
  ======================================================
  */

  WiFi.mode(WIFI_STA);

  /*
  ======================================================
  CONNECT WIFI
  IMPORTANT FOR SAME CHANNEL
  ======================================================
  */

  WiFi.begin(ssid, password);

  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected");

  /*
  ======================================================
  ESP NOW INIT
  ======================================================
  */

  if (MODE == 2) {

    if (esp_now_init() != ESP_OK) {

      Serial.println("ESP-NOW Init Failed");
      return;
    }

    /*
    ====================================================
    PEER CONFIGURATION
    ====================================================
    */

    esp_now_peer_info_t peerInfo = {};

    memcpy(peerInfo.peer_addr,
           aggregatorAddress,
           6);

    peerInfo.channel = 0;

    peerInfo.encrypt = false;

    peerInfo.ifidx = WIFI_IF_STA;

    /*
    ====================================================
    ADD PEER
    ====================================================
    */

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {

      Serial.println("Failed To Add Peer");
      return;
    }

    Serial.println("ESP-NOW READY");
  }

  /*
  ======================================================
  OFFSET FOR MODE 1
  ======================================================
  */

  if (MODE == 1 && SENSOR_ID == 2) {

    delay(10000);
  }
}

/*
========================================================
LOOP
========================================================
*/

void loop() {

  int peak = 0;

  unsigned long startTime = millis();

  /*
  ======================================================
  PEAK DETECTION
  ======================================================
  */

  while (millis() - startTime < 15000) {

    int val = analogRead(micPin);

    if (val > peak) {

      peak = val;
    }

    delay(10);
  }

  /*
  ======================================================
  SERIAL OUTPUT
  ======================================================
  */

  Serial.println("---------------");

  Serial.print("Sensor ID: ");
  Serial.println(SENSOR_ID);

  Serial.print("Peak Sound: ");
  Serial.println(peak);

  /*
  ======================================================
  BUZZER LOGIC
  ======================================================
  */

  if (peak > threshold) {

    digitalWrite(buzzerPin, HIGH);
  }

  else {

    digitalWrite(buzzerPin, LOW);
  }

  /*
  ======================================================
  MODE 1
  SHARED CHANNEL
  ======================================================
  */

  if (MODE == 1) {

    if (WiFi.status() == WL_CONNECTED) {

      HTTPClient http;

      String url = server;

      url += "?api_key=" + sharedApiKey;

      if (SENSOR_ID == 1) {

        url += "&field1=" + String(peak);
      }

      if (SENSOR_ID == 2) {

        url += "&field2=" + String(peak);
      }

      http.begin(url);

      int httpCode = http.GET();

      Serial.print("HTTP Code: ");
      Serial.println(httpCode);

      http.end();
    }

    if (SENSOR_ID == 1) {

      delay(20000);
    }

    if (SENSOR_ID == 2) {

      delay(30000);
    }
  }

  /*
  ======================================================
  MODE 2
  ESP NOW AGGREGATOR
  ======================================================
  */

  else if (MODE == 2) {

    myData.sensorID = SENSOR_ID;
    myData.value = peak;

    /*
    ====================================================
    SEND DATA
    ====================================================
    */

    esp_err_t result = esp_now_send(
      aggregatorAddress,
      (uint8_t *) &myData,
      sizeof(myData)
    );

    /*
    ====================================================
    SEND STATUS
    ====================================================
    */

    if (result == ESP_OK) {

      Serial.println("SEND SUCCESS");
    }

    else {

      Serial.println("SEND FAILED");
    }

    delay(1000);
  }

  /*
  ======================================================
  MODE 3
  SEPARATE CHANNELS
  ======================================================
  */

  else if (MODE == 3) {

    if (WiFi.status() == WL_CONNECTED) {

      HTTPClient http;

      String url = server;

      /*
      ==================================================
      LEFT SENSOR
      ==================================================
      */

      if (SENSOR_ID == 1) {

        url += "?api_key=" + leftChannelApi;

        url += "&field1=" + String(peak);
      }

      /*
      ==================================================
      RIGHT SENSOR
      ==================================================
      */

      if (SENSOR_ID == 2) {

        url += "?api_key=" + rightChannelApi;

        url += "&field1=" + String(peak);
      }

      http.begin(url);

      int httpCode = http.GET();

      Serial.print("HTTP Code: ");
      Serial.println(httpCode);

      http.end();
    }

    delay(16000);
  }
}