#include <Arduino.h>
#include <SPI.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"
#include "OLEDHandler.h"
#include "GPSHandler.h"
#include "LIDARHandler.h"
#include "LoRaComm.h"
#include "WiFiComm.h"

// ── Peripherals ───────────────────────────────────────────────────────────────
OLEDHandler  oled (OLED_CS,  OLED_DC,   OLED_RESET);
GPSHandler   gps  (GPS_RX,   GPS_TX);
LIDARHandler lidar(LIDAR_RX, LIDAR_TX,  MOTOR_PIN, DIST_THRESHOLD);

SPIClass loraSPI(VSPI);
LoRaComm lora(LORA_SS, LORA_RESET, LORA_DIO0, loraSPI);
WiFiComm wifi;

// ── LIDAR ↔ main-loop shared state ───────────────────────────────────────────
// The LIDAR task runs on Core 0. The main loop runs on Core 1.
// A mutex guards the shared result so neither core sees a torn write.
static SemaphoreHandle_t s_potholeMutex;
static float             s_potholeDistCm = 0.0f;
static bool              s_potholeReady  = false;

// Minimum gap between successive broadcasts of the same pothole event.
// At 20 km/h ≈ 5.5 m/s, 3 s ≈ 16 m of travel — enough to clear a single pit.
static constexpr uint32_t BROADCAST_COOLDOWN_MS = 3000;

// ── Forward declarations ──────────────────────────────────────────────────────
void lidarTask(void* pvParam);
void onLoRaReceive(int packetSize);

// ─────────────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);

    oled.begin();
    oled.showStatus("Initialising...");

    gps.begin();
    lidar.begin();

    if (!lora.begin(LORA_FREQ)) {
        Serial.println("[LoRa] Init failed — check Ra-02 wiring");
        oled.showStatus("LoRa FAIL", "Check wiring");
        while (1);
    }
    lora.startReceive(onLoRaReceive);
    Serial.println("[LoRa] Ready");

    if (!wifi.begin()) {
        Serial.println("[WiFi] ESP-NOW init failed");
        oled.showStatus("ESP-NOW FAIL");
    } else {
        Serial.println("[WiFi] ESP-NOW ready  MAC: " + WiFi.macAddress());
    }

    // Mutex must exist before the LIDAR task starts.
    s_potholeMutex = xSemaphoreCreateMutex();

    // Pin the LIDAR task to Core 0 so it never competes with the main loop
    // (Core 1). The WiFi stack also lives on Core 0 but at higher priority;
    // FreeRTOS preemption keeps them from interfering.
    xTaskCreatePinnedToCore(
        lidarTask,   // task function
        "LIDAR",     // name (debug only)
        4096,        // stack in bytes
        nullptr,     // parameter
        1,           // priority (low — yields to WiFi stack)
        nullptr,     // task handle (not needed)
        0            // core 0
    );

    oled.showStatus("System Ready", WiFi.macAddress().c_str());
    Serial.println("[System] Ready");
}

// ─────────────────────────────────────────────────────────────────────────────
// Core 0 — LIDAR scanning task.
// Calls detectPothole() in a loop. That function drains whatever bytes are
// currently in the UART buffer and returns immediately when empty, so the
// vTaskDelay gives other Core-0 tasks (WiFi stack) a chance to run between
// buffer drain cycles. reset() is only called on a hardware fault (-2).
void lidarTask(void* pvParam) {
    for (;;) {
        float dist = lidar.detectPothole();

        if (dist > 0.0f) {
            if (xSemaphoreTake(s_potholeMutex, portMAX_DELAY) == pdTRUE) {
                s_potholeDistCm = dist;
                s_potholeReady  = true;
                xSemaphoreGive(s_potholeMutex);
            }
        } else if (dist == -2.0f) {
            Serial.println("[LIDAR] Fault — restarting scan");
            lidar.reset();  // only legitimate use of reset()
        }

        // Yield between drain cycles. At A1M8's ~2000 pts/s × 5 bytes,
        // 1 ms produces ~10 bytes — well within the 256-byte HW FIFO.
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Core 1 — main loop.
// Never touches the LIDAR directly; only reads the shared result.
void loop() {
    // Keep GPS decoder fed every iteration — at 9600 baud the cost is trivial.
    gps.update();

    uint32_t now = millis();

    // ── Check for a LIDAR detection (non-blocking mutex attempt) ─────────────
    if (xSemaphoreTake(s_potholeMutex, 0) == pdTRUE) {
        bool  ready = s_potholeReady;
        float dist  = s_potholeDistCm;

        if (ready) s_potholeReady = false;
        xSemaphoreGive(s_potholeMutex);

        static uint32_t lastBroadcastMs = 0;
        if (ready && (now - lastBroadcastMs >= BROADCAST_COOLDOWN_MS)) {
            GPSData loc = gps.getLocation();
            if (loc.valid) {
                lastBroadcastMs = now;

                PotholePacket pkt = {DEVICE_UID, loc.latitude, loc.longitude, dist, now};
                bool loraOk = lora.broadcast(DEVICE_UID, pkt);
                bool wifiOk = wifi.broadcast(pkt);

                Serial.printf("[Pothole] %.6f, %.6f — %.1f cm  |  LoRa:%s  WiFi:%s\n",
                              loc.latitude, loc.longitude, dist,
                              loraOk ? "OK" : "ERR",
                              wifiOk ? "OK" : "ERR");

                oled.showPothole(loc.latitude, loc.longitude, dist);
            } else {
                Serial.println("[GPS] No fix — pothole not broadcast");
            }
        }
    }

    // ── Handle incoming ESP-NOW packets ──────────────────────────────────────
    if (wifi.hasNewPacket()) {
        PotholePacket pkt = wifi.takePacket();
        oled.showReceived(pkt.uid, pkt.latitude, pkt.longitude, "WiFi");
        Serial.printf("[WiFi RX] UID=0x%02X  %.6f, %.6f — %.1f cm\n",
                      pkt.uid, pkt.latitude, pkt.longitude, pkt.distance);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// LoRa receive ISR — runs in interrupt context; keep it short.
void onLoRaReceive(int packetSize) {
    byte          senderUID;
    PotholePacket pkt;

    if (!lora.parsePacket(packetSize, senderUID, pkt)) {
        Serial.println("[LoRa RX] Malformed packet");
        return;
    }
    pkt.uid = senderUID;

    oled.showReceived(senderUID, pkt.latitude, pkt.longitude, "LoRa");
    Serial.printf("[LoRa RX] UID=0x%02X  %.6f, %.6f — %.1f cm\n",
                  senderUID, pkt.latitude, pkt.longitude, pkt.distance);
}
