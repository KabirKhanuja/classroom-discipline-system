#include <WiFi.h>
#include <HTTPClient.h>
#include "env_config.h"

const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;

const char* apiKey = THINGSPEAK_API_KEY;
const char* server = "https://api.thingspeak.com/update";

const int micPin = 34;
const int buzzerPin = 25;

int threshold = 1800;

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(buzzerPin, OUTPUT);

  WiFi.begin(ssid, password);
  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnected");
}

void loop() {

  int val = analogRead(micPin);

  Serial.print("Sound: ");
  Serial.println(val);

  if (val > threshold) {
    digitalWrite(buzzerPin, HIGH);
  } else {
    digitalWrite(buzzerPin, LOW);
  }

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;

    String url = server;
    url += "?api_key=";
    url += apiKey;
    url += "&field2=" + String(val);

    http.begin(url);
    http.GET();
    http.end();
  }

  delay(16000);
}