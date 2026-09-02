// Copy to secrets.h and fill in. secrets.h is gitignored and must never be committed.
#pragma once

#define SECRET_WIFI_SSID        "your-wifi-ssid"
#define SECRET_WIFI_PASS        "your-wifi-password"

// ThingSpeak channel the board publishes to.
#define SECRET_TS_CHANNEL_ID    0
#define SECRET_TS_WRITE_KEY     "your-thingspeak-write-key"

// ThingSpeak MQTT device credentials (Devices -> MQTT in the ThingSpeak console).
#define SECRET_TS_MQTT_CLIENT_ID "your-mqtt-client-id"
#define SECRET_TS_MQTT_USER      "your-mqtt-username"
#define SECRET_TS_MQTT_PASS      "your-mqtt-password"

// Shared secret the firmware presents to POST /api/alerts.
#define SECRET_DEVICE_TOKEN     "match-PLANTIQ_DEVICE_TOKEN"
