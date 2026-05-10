#pragma once
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

struct GPSData {
    double   latitude;
    double   longitude;
    double   altitude;
    uint32_t satellites;
    bool     valid;
};

class GPSHandler {
public:
    GPSHandler(uint8_t rx, uint8_t tx)
        : _serial(1), _rx(rx), _tx(tx) {}

    void begin() {
        _serial.begin(9600, SERIAL_8N1, _rx, _tx);
    }

    // Call every loop iteration to keep the internal fix current.
    // Drains all bytes available right now; never blocks.
    void update() {
        while (_serial.available()) {
            _gps.encode(_serial.read());
        }
    }

    // Returns the most recently decoded fix. Call update() first each loop.
    GPSData getLocation() {
        if (!_gps.location.isValid()) {
            return {0.0, 0.0, 0.0, 0, false};
        }
        return {
            _gps.location.lat(),
            _gps.location.lng(),
            _gps.altitude.meters(),
            _gps.satellites.value(),
            true
        };
    }

private:
    TinyGPSPlus    _gps;
    HardwareSerial _serial;
    uint8_t        _rx, _tx;
};
