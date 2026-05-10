#pragma once
#include <RPLidar.h>
#include <Arduino.h>

class LIDARHandler {
public:
    LIDARHandler(uint8_t rx, uint8_t tx, uint8_t motorPin, int distThresholdMm)
        : _serial(2), _rx(rx), _tx(tx), _motorPin(motorPin),
          _distThresholdMm(distThresholdMm) {}

    void begin() {
        _serial.begin(115200, SERIAL_8N1, _rx, _tx);
        _lidar.begin(_serial);
        pinMode(_motorPin, OUTPUT);
        analogWrite(_motorPin, 255);
        _lidar.startScan();
    }

    // Drains whatever is currently in the serial buffer (one pass, non-blocking
    // on entry). Accumulates hits across calls via member state so detection
    // works correctly even when the buffer only has a few points at a time.
    //
    // Returns: >0  pothole distance in cm (resets internal counters)
    //          -1  still scanning, no conclusion yet
    //          -2  hardware fault — caller should invoke reset()
    float detectPothole() {
        while (_serial.available()) {
            if (IS_OK(_lidar.waitPoint())) {
                _failCount = 0;

                float dist  = _lidar.getCurrentPoint().distance;
                float angle = _lidar.getCurrentPoint().angle;
                float qual  = _lidar.getCurrentPoint().quality;

                bool inFOV    = (angle < 45.0f || angle > 315.0f);
                bool reliable = (qual > 10 && dist > 0);

                if (inFOV && reliable && dist > _distThresholdMm) {
                    if (++_hitCount > 4) {
                        float result = dist / 10.0f;  // mm → cm
                        _hitCount = 0;
                        return result;
                    }
                }
            } else {
                if (++_failCount > 10) {
                    _failCount = 0;
                    _hitCount  = 0;
                    return -2.0f;
                }
            }
        }
        return -1.0f;
    }

    void reset() {
        _lidar.stop();
        delay(10);
        _serial.flush();
        while (_serial.available()) _serial.read();
        _lidar.startScan();
    }

    ~LIDARHandler() {
        _lidar.stop();
        _serial.end();
        analogWrite(_motorPin, 0);
    }

private:
    RPLidar        _lidar;
    HardwareSerial _serial;
    const uint8_t  _rx, _tx, _motorPin;
    const int      _distThresholdMm;
    uint8_t        _hitCount  = 0;
    uint8_t        _failCount = 0;

    // Attempts motor/scan restart; returns -2 to propagate fault to caller.
    float _recover() {
        analogWrite(_motorPin, 0);
        rplidar_response_device_health_t health;
        if (!IS_OK(_lidar.getHealth(health))) return -2.0f;
        _lidar.startScan();
        analogWrite(_motorPin, 255);
        delay(1000);
        return -2.0f;
    }
};
