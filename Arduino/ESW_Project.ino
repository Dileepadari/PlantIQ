#include <DHT.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <string.h>
#include <PubSubClient.h>
#include <ThingSpeak.h>
#include <Arduino.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "SparkFun_SGP30_Arduino_Library.h"
#include "secrets.h"  // untracked, copy from secrets.example.h

#define CSE_IP "192.168.245.105"
#define CSE_PORT 5089
#define OM2M_ORGIN "admin:admin"
#define OM2M_MN "/~/in-cse/in-name/"
#define OM2M_AE "Smart_Farming"
#define OM2M_DATA_CONT "Sensors/Data"

int some_var = 0;
const char *ssid = "GALAXY KING";
const char *password = "DILEEPPRASANTHi";

const char *ntpServer = "pool.ntp.org";
const char *server = "mqtt3.thingspeak.com";
const int port = 1883;

const char *mqttUserName = SECRET_TS_MQTT_USER;
const char ClientID[] = SECRET_TS_MQTT_CLIENT_ID;
const char *mqttPass = SECRET_TS_MQTT_PASS;
long int channelID = SECRET_TS_CHANNEL_ID;
const char *apiKey = SECRET_TS_WRITE_KEY;

HTTPClient http;

WiFiClient client;
PubSubClient mqttClient(server, port, client);
SGP30 VOCsensor;

#define DHTPIN 32
#define DHTTYPE DHT11

int _moisture, sensor_analog, LDRValue, CO2Val, VOCVal;
const int sensor_pin = 34;
const int LDRPin = 33;
DHT dht(DHTPIN, DHTTYPE);

void setup(void)
{
    dht.begin();
    pinMode(LDRPin, INPUT);
    Serial.begin(115200);
    Wire.begin();
    if (VOCsensor.begin() == false)
    {
        Serial.println("No SGP30 Detected. Check connections.");
            while (1);
    }
    VOCsensor.initAirQuality();
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("Connecting to WiFi...");
        delay(1000);
    }
    Serial.println("WiFi Connected!");
    ThingSpeak.begin(client);
    mqttClient.setServer(server, port);
    configTime(0, 0, ntpServer);
}

String field_values[6];
void loop(void)
{
    some_var = some_var % 6;
    while (mqttClient.connected() == NULL)
    {
        Serial.println("COnnecting to mqtt...");
        mqttConnect();
        delay(1000);
    }
    StaticJsonDocument<200> jsonDoc;
    jsonDoc["secret"] = SECRET_DEVICE_TOKEN;
    jsonDoc["plant_name"] = "Mango";
    //  jsonDoc["msg"] = "this is a sample msg";
    //  jsonDoc["notif_type"] = "danger";
    String jsonStr;
    //  serializeJson(jsonDoc, jsonStr);

    mqttClient.loop();
    VOCsensor.measureAirQuality();
    CO2Val = VOCsensor.CO2;
    VOCVal = VOCsensor.TVOC;
    sensor_analog = analogRead(sensor_pin);
     //(more than 3000 is random value)(range: 10 -1000)

    // for(int i = 0;i < 20;i++){
    //   Serial.println("Values of CO2 and VOC are being calculated");
    // }
    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();
    _moisture = (100 - ((sensor_analog / 4095.00) * 100));
    Serial.print("Moisture Percentage = ");
    if (_moisture == 100)
    {
        _moisture = 0;
    }
    
    Serial.print(_moisture);
    Serial.println("%");
    Serial.print("Light Intensity: ");
    LDRValue = analogRead(LDRPin);
    int LDRPerc = (4096 - LDRValue)*100/4096;
    Serial.print(LDRPerc);
    Serial.println("%");
    if (isnan(humidity) || isnan(temperature))
    {
        if (isnan(humidity))
        {
            humidity = 0;
        }
        if (isnan(temperature))
        {
            temperature = 0;
        }
        Serial.println("Failed to read from DHT sensor cause getting 0");
    }
    else
    {
        Serial.print("Humidity: ");
        Serial.print(humidity);
        Serial.print(" %\t");
        Serial.print("Temperature: ");
        Serial.print(temperature);
        Serial.println(" °C\n\n");
    }

    Serial.print("CO2: ");
    Serial.print(CO2Val);
    Serial.print(" ppm\tTVOC: ");
    Serial.print(VOCVal);
    Serial.println(" ppb");

    if (some_var == 0)
    {
        if (temperature > 35)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! High Temperature.";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
        else if (temperature < 25)  
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! Low Temperature.";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
    }
    delay(100);

    // humidity
    if (some_var == 1)
    {
        if (humidity < 40)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! Low Humidity.";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
        else if (humidity > 80)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! High Humidity.";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
    }
    delay(100);

    // ldr
    if (some_var == 2)
    {
        if (LDRPerc < 20)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! Low Intensity.";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
    }
    delay(100);

    // soil moisture
    if (some_var == 3)
    {
        if (_moisture > 80)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! High Soil Moisture.";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
        else if (_moisture < 20)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! Low Soil Moisture.";
            jsonDoc["notif_type"] = "danger";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
    }
    delay(100);

    // co2
    if (some_var == 4)
    {
        if (CO2Val > 800)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! High CO2.Probability of pathogen attack!!";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
        else if (CO2Val < 400)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! Low CO2.";
            jsonDoc["notif_type"] = "warning";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
    }
    delay(100);
    // voc
    if (some_var == 5)
    {
        if (VOCVal > 100)
        {
            http.begin(client, "http://greenplant.pythonanywhere.com/receive");
            http.addHeader("Content-Type", "application/json");
            jsonDoc["msg"] = "Caution! High VOC.Probability of pathogen attack!!";
            jsonDoc["notif_type"] = "danger";
            serializeJson(jsonDoc, jsonStr);
            Serial.println(http.POST(jsonStr));
            http.end();
        }
    }
    delay(100);
    some_var = some_var + 1;

    // payload for the string

    // VOC = field 4 ; CO2 = field 5;
    field_values[0] = "field1=" + String(temperature) + "&";
    field_values[1] = "field2=" + String(_moisture) + "&";
    field_values[2] = "field3=" + String(LDRPerc) + "&";
    field_values[3] = "field4=" + String(VOCVal) + "&";
    field_values[4] = "field5=" + String(CO2Val) + "&";
    field_values[5] = "field6=" + String(humidity) + "&";
    String answer = "";
    for (int i = 0; i < 6; i++)
    {
        answer += field_values[i];
    }
    int field_to_publish[1] = {6};
    mqttPublish(channelID, apiKey, answer, field_to_publish);

    String data;
    String server = "http://" + String() + CSE_IP + ":" + String() + CSE_PORT + String() + OM2M_MN;

    http.begin(server + String() + OM2M_AE + "/" + OM2M_DATA_CONT + "/");

    http.addHeader("X-M2M-Origin", OM2M_ORGIN);
    http.addHeader("Content-Type", "application/json;ty=4");
    http.addHeader("Content-Length", "100");

    data = "[" + String(temperature) + ", " + String(_moisture) + ", " + String(LDRPerc) + ", " + String(VOCVal) + ", " + String(CO2Val) + ", " + String(humidity) + "]";
    String req_data = String() + "{\"m2m:cin\": {"

                      +
                      "\"con\": \"" + data + "\","

                      +
                      "\"lbl\": \"" + "V1.0.0" + "\","

                      //+ "\"rn\": \"" + "cin_"+String(i++) + "\","

                      +
                      "\"cnf\": \"text\""

                      +
                      "}}";
    int code = http.POST(req_data);
    http.end();
    Serial.println(code);
    delay(500);
}

void mqttConnect()
{
    while (!mqttClient.connected())
    {
        Serial.print("Attempting connection to MQTT...");
        Serial.print("\n");
        if (mqttClient.connect(ClientID, mqttUserName, mqttPass))
        {
            Serial.println("connected to MQTT broker");
            Serial.print("\n");
        }
        else
        {
            Serial.print("failed due to error ");
            Serial.print(mqttClient.state());
            Serial.print("\n");
            Serial.println("making a retry...");
            Serial.print("\n");
            delay(3000);
        }
    }
}

void mqttPublish(long pubChannelID, String pubWriteAPIKey, String data, int fieldArray[])
{
    String topicstring = "channels/" + String(pubChannelID) + "/publish"; //+String(pubWriteAPIKey);

    mqttClient.publish(topicstring.c_str(), data.c_str());
    delay(1000);
}
