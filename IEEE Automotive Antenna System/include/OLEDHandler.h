#pragma once
#include <U8g2lib.h>
#include <SPI.h>
#include "config.h"

class OLEDHandler {
public:
    OLEDHandler(uint8_t cs, uint8_t dc, uint8_t reset)
        : _oled(U8G2_R0, cs, dc, reset) {}

    void begin() { _oled.begin(); }

    template <typename T>
    void writeStr(T text, int x, int y) {
        _oled.setFont(u8g2_font_ncenB08_tr);
        _oled.setCursor(x, y);
        _oled.print(text);
    }

    void display() { _oled.sendBuffer(); }

    void showPothole(double lat, double lon, float distCm) {
        _oled.clearBuffer();
        writeStr("! Pothole Detected", 0, 10);
        writeStr("Lat: " + String(lat, 6), 0, 24);
        writeStr("Lon: " + String(lon, 6), 0, 36);
        writeStr("Dist: " + String(distCm, 1) + " cm", 0, 48);
        display();
    }

    void showReceived(byte senderUID, double lat, double lon, const char* channel) {
        _oled.clearBuffer();
        writeStr(String("[") + channel + "] Pothole", 0, 10);
        writeStr("From UID: 0x" + String(senderUID, HEX), 0, 24);
        writeStr("Lat: " + String(lat, 6), 0, 36);
        writeStr("Lon: " + String(lon, 6), 0, 48);
        display();
    }

    void showStatus(const char* line1, const char* line2 = "") {
        _oled.clearBuffer();
        writeStr(line1, 0, 24);
        if (line2[0]) writeStr(line2, 0, 36);
        display();
    }

private:
    U8G2_SSD1309_128X64_NONAME0_F_4W_HW_SPI _oled;
};
