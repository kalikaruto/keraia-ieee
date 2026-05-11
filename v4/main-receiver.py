# receiver/main.py

import json

from wifi_manager import WiFiManager


def received(msg):

    try:

        data = json.loads(msg)

        print("\nGPS DATA")
        print("----------------")

        print("FIX:", data["fix"])

        print("LATITUDE:", data["latitude"])
        print("LONGITUDE:", data["longitude"])

        print("ALTITUDE:", data["altitude"])

        print("SATELLITES:", data["satellites"])

        print("HDOP:", data["hdop"])

        print("SPEED:", data["speed_knots"])

        print("COURSE:", data["course"])

        print("DATETIME:", data["datetime"])

    except Exception as e:

        print("PARSE ERROR:", e)
        print(msg)


wifi = WiFiManager(
    mode="sta",
    ssid="ESP32_LINK",
    password="12345678",
    ip="192.168.4.1",
    port=5000,
)

wifi.on_receive(received)

wifi.start()

while True:
    pass
