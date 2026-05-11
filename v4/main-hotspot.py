# sender/main.py

import time
import json

from oled import OLED
from gps import GPS
from wifi_manager import WiFiManager


oled = OLED()

gps = GPS()

wifi = WiFiManager(
    mode="ap",
    ssid="ESP32_LINK",
    password="12345678",
    ip="192.168.4.1",
    port=5000,
)

oled.fill(0)
oled.text("STARTING AP", 0, 0, 1)
oled.show()

wifi.start()

while True:

    if gps.update():

        oled.fill(0)

        oled.text("GPS TX NODE", 0, 0, 1)

        if gps.has_fix():

            data = gps.summary()

            payload = json.dumps(data)

            wifi.send(payload)

            print("SENT:")
            print(payload)

            lat = str(gps.latitude)
            lon = str(gps.longitude)

            sats = str(gps.satellites)

            oled.text("FIX OK", 0, 14, 1)

            oled.text(lat[:16], 0, 28, 1)
            oled.text(lon[:16], 0, 40, 1)

            oled.text("SAT:" + sats, 0, 54, 1)

        else:

            oled.text("NO GPS FIX", 0, 20, 1)

        oled.show()

    time.sleep_ms(100)
