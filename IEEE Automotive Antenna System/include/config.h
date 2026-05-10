#pragma once
#include <Arduino.h>

// ----------- Device -----------
const byte DEVICE_UID = 0x01;

// ----------- LoRa (Ra-02 / SX1278, 433 MHz) -----------
// Ra-02 uses SPI. With VSPI (default): SCK=18, MISO=19, MOSI=23.
// WARNING: LORA_SS=18 conflicts with VSPI SCK, and LORA_RESET=19 conflicts
//          with VSPI MISO. Suggested safe reassignment:
//            LORA_SS    → 5   (VSPI default CS)
//            LORA_RESET → 14
//          Update these to match your actual wiring before flashing.
#define LORA_FREQ   433E6
#define LORA_SS     18   // ← verify: conflicts with VSPI SCK if unchanged
#define LORA_RESET  19   // ← verify: conflicts with VSPI MISO if unchanged
#define LORA_DIO0   26

// ----------- OLED (SSD1309, 128×64, HW SPI) -----------
// NOTE: Original code had OLED_RESET=4, which conflicts with GPS_RX=4.
//       Reassigned to GPIO 32 — update if your wiring differs.
#define OLED_CS     15
#define OLED_DC     2
#define OLED_RESET  32

// ----------- LIDAR (RPLidar A1M8, UART) -----------
#define LIDAR_RX        16
#define LIDAR_TX        17
#define MOTOR_PIN       22
#define DIST_THRESHOLD  150  // mm — minimum depth to classify as a pothole

// ----------- GPS (NEO-6M / NEO-8M, UART) -----------
#define GPS_RX  4
#define GPS_TX  5

// ----------- Shared Packet -----------
// Identical struct sent over both LoRa (binary) and ESP-NOW.
// sizeof(PotholePacket) must stay ≤ 250 bytes (ESP-NOW payload limit).
struct PotholePacket {
    byte     uid;
    double   latitude;
    double   longitude;
    float    distance;   // cm
    uint32_t timestamp;  // millis()
};
