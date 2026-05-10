#pragma once
#include <WiFi.h>
#include <esp_now.h>
#include <esp_idf_version.h>
#include "config.h"

// ESP-NOW broadcast address — reaches all peers on the same channel.
static const uint8_t ESPNOW_BROADCAST_ADDR[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

class WiFiComm {
public:
    WiFiComm() {}

    // Initialises WiFi in station mode (no AP connection) and starts ESP-NOW.
    // Station mode is required for ESP-NOW; no router needed.
    bool begin() {
        WiFi.mode(WIFI_STA);
        WiFi.disconnect();

        if (esp_now_init() != ESP_OK) return false;

        esp_now_register_send_cb(_onSent);
        esp_now_register_recv_cb(_onReceive);

        // Register the broadcast "peer" so esp_now_send accepts the address.
        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, ESPNOW_BROADCAST_ADDR, 6);
        peer.channel = 0;
        peer.encrypt = false;
        if (esp_now_add_peer(&peer) != ESP_OK) return false;

        return true;
    }

    // Broadcasts a PotholePacket to all nearby ESP32 nodes via ESP-NOW.
    bool broadcast(const PotholePacket& pkt) {
        esp_err_t r = esp_now_send(
            ESPNOW_BROADCAST_ADDR,
            reinterpret_cast<const uint8_t*>(&pkt),
            sizeof(pkt)
        );
        return r == ESP_OK;
    }

    bool hasNewPacket() const { return _hasNew; }

    // Retrieves and clears the most recently received packet.
    PotholePacket takePacket() {
        _hasNew = false;
        return _lastPacket;
    }

    bool lastSendOk() const { return _lastSendOk; }

private:
    static inline PotholePacket _lastPacket  = {};
    static inline bool          _hasNew      = false;
    static inline bool          _lastSendOk  = false;

    static void _onSent(const uint8_t* mac, esp_now_send_status_t status) {
        _lastSendOk = (status == ESP_NOW_SEND_SUCCESS);
    }

    // ESP-IDF 5.x changed the recv callback signature to use esp_now_recv_info_t.
    // ESP-IDF 4.x used (const uint8_t* mac, ...). The guard below handles both.
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
    static void _onReceive(const esp_now_recv_info_t* info, const uint8_t* data, int len) {
#else
    static void _onReceive(const uint8_t* mac, const uint8_t* data, int len) {
#endif
        if (len != sizeof(PotholePacket)) return;
        memcpy(&_lastPacket, data, sizeof(PotholePacket));
        _hasNew = true;
    }
};
