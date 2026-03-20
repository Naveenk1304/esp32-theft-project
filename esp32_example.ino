#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi Credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Flask Server URL (Replace with your laptop's IP)
const char* serverName = "http://192.168.1.XX:5000/data";
const char* userEmail = "yourname@example.com"; // Enter verified email here

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverName);
    http.addHeader("Content-Type", "application/json");

    // Simulate Sensor Data
    float current = random(5, 20) / 10.0; // 0.5 - 2.0 A
    float power = current * 230.0;
    float energy = random(1, 100) / 100.0;

    // Create JSON
    StaticJsonDocument<200> doc;
    doc["current"] = current;
    doc["power"] = power;
    doc["energy"] = energy;
    doc["email"] = userEmail;

    String requestBody;
    serializeJson(doc, requestBody);

    int httpResponseCode = http.POST(requestBody);

    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println(httpResponseCode);
      Serial.println(response);
    } else {
      Serial.print("Error on sending POST: ");
      Serial.println(httpResponseCode);
    }
    http.end();
  }
  
  delay(5000); // Send data every 5 seconds
}
