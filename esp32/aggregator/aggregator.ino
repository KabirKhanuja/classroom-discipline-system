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
THINGSPEAK API
========================================================
*/

String apiKey =
"8ZUG78XOQ6KVLNNL";

const char* server =
"https://api.thingspeak.com/update";

/*
========================================================
DATA STRUCTURE
========================================================
*/

typedef struct struct_message {

  int sensorID;
  int value;

} struct_message;

struct_message incomingData;

/*
========================================================
STORE SENSOR VALUES
========================================================
*/

int sensor1 = 0;
int sensor2 = 0;

/*
========================================================
RECEIVE CALLBACK
========================================================
*/

void OnDataRecv(
  const esp_now_recv_info *recv_info,
  const uint8_t *incomingDataBytes,
  int len
) {

  memcpy(
    &incomingData,
    incomingDataBytes,
    sizeof(incomingData)
  );

  /*
  ======================================================
  SENSOR 1
  ======================================================
  */

  if (incomingData.sensorID == 1) {

    sensor1 = incomingData.value;
  }

  /*
  ======================================================
  SENSOR 2
  ======================================================
  */

  if (incomingData.sensorID == 2) {

    sensor2 = incomingData.value;
  }

  /*
  ======================================================
  SERIAL OUTPUT
  ======================================================
  */

  Serial.println("---------------");

  Serial.print("Sensor1: ");
  Serial.println(sensor1);

  Serial.print("Sensor2: ");
  Serial.println(sensor2);

  /*
  ======================================================
  COMPARE VALUES
  ======================================================
  */

  if (sensor1 > sensor2) {

    Serial.println("LEFT SIDE NOISY");
  }

  else if (sensor2 > sensor1) {

    Serial.println("RIGHT SIDE NOISY");
  }

  else {

    Serial.println("BALANCED");
  }
}

/*
========================================================
SETUP
========================================================
*/

void setup() {

  Serial.begin(115200);

  /*
  ======================================================
  WIFI
  ======================================================
  */

  WiFi.mode(WIFI_STA);

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

  if (esp_now_init() != ESP_OK) {

    Serial.println("ESP-NOW Init Failed");
    return;
  }

  /*
  ======================================================
  REGISTER CALLBACK
  ======================================================
  */

  esp_now_register_recv_cb(OnDataRecv);

  Serial.println("Aggregator Ready");
}

/*
========================================================
LOOP
========================================================
*/

void loop() {

  /*
  ======================================================
  UPLOAD BOTH VALUES
  ======================================================
  */

  if (WiFi.status() == WL_CONNECTED) {

    HTTPClient http;

    String url = server;

    url += "?api_key=" + apiKey;

    url += "&field1=" + String(sensor1);

    url += "&field2=" + String(sensor2);

    http.begin(url);

    int httpCode = http.GET();

    Serial.print("HTTP Response Code: ");
    Serial.println(httpCode);

    http.end();
  }

  delay(16000);
}