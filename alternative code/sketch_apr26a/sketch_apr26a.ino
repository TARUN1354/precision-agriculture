#include <DHT.h>

#define DHTPIN 27        // DHT11 connected to GPIO27
#define DHTTYPE DHT11    // Type of DHT sensor

DHT dht(DHTPIN, DHTTYPE);  // Initialize DHT sensor

const int soilPin = 26;    // GPIO26 for Soil sensor
const int lightPin = 23;   // GPIO23 for Light sensor (LDR)

void setup() {
  Serial.begin(9600);
  dht.begin();             // Start DHT sensor
}

void loop() {
  int soilRaw = analogRead(soilPin);
  int lightRaw = analogRead(lightPin);

  float temp = dht.readTemperature();  // °C
  float humid = dht.readHumidity();    // %

  float soilPercent = map(soilRaw, 0, 4095, 100, 0);   // % scale
  float lightLevel = map(lightRaw, 0, 4095, 0, 1000);  // lux scale

  // ✅ Send all in one line
  Serial.print(soilPercent); Serial.print(",");
  Serial.print(temp); Serial.print(",");
  Serial.print(humid); Serial.print(",");
  Serial.println(lightLevel);

  delay(2000);
}
