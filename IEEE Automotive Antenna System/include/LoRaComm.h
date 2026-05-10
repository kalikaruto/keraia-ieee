#pragma once
#include <LoRa.h>
#include <SPI.h>
#include "config.h"

class LoRaComm {
public:
    LoRaComm(uint8_t ss, uint8_t reset, uint8_t dio0, SPIClass& spi)
        : _ss(ss), _reset(reset), _dio0(dio0), _spi(spi) {}

    // setPins() must be called before begin() — order matters for the Ra-02.
    bool begin(long frequency = LORA_FREQ) {
        LoRa.setSPI(_spi);
        LoRa.setPins(_ss, _reset, _dio0);
        return LoRa.begin(frequency);
    }

    void startReceive(void (*callback)(int)) {
        LoRa.onReceive(callback);
        LoRa.receive();
    }

    // Broadcasts a PotholePacket as raw binary prefixed with the sender UID.
    bool broadcast(byte uid, const PotholePacket& pkt) {
        LoRa.beginPacket();
        LoRa.write(uid);
        LoRa.write(reinterpret_cast<const uint8_t*>(&pkt), sizeof(pkt));
        return LoRa.endPacket(true);  // async send
    }

    // Call from the onReceive ISR. Returns false on malformed/short packet.
    bool parsePacket(int packetSize, byte& senderUID, PotholePacket& out) {
        if (packetSize < static_cast<int>(1 + sizeof(PotholePacket))) return false;

        senderUID = LoRa.read();

        uint8_t buf[sizeof(PotholePacket)];
        for (size_t i = 0; i < sizeof(PotholePacket); i++) {
            buf[i] = LoRa.read();
        }
        memcpy(&out, buf, sizeof(PotholePacket));
        return true;
    }

private:
    uint8_t   _ss, _reset, _dio0;
    SPIClass& _spi;
};
