# receiver_main.py

from oled import OLED
from wifi_manager import WiFiManager
from config import WIFI

oled = OLED()


def show_packet(packet):

    oled.clear_buf()

    packet_type = packet.get("type", "")

    if packet_type == "pothole":

        depth = packet.get("depth", 0)
        angle = packet.get("angle", 0)

        print(
            "POTHOLE",
            "Depth:", round(depth, 1),
            "Angle:", round(angle, 1)
        )

        oled.text("POTHOLE", 5, 5)
        oled.text(
            "D:{:.1f}mm".format(depth),
            5,
            25
        )
        oled.text(
            "A:{:.1f}".format(angle),
            5,
            45
        )

    elif packet_type == "object":

        height = packet.get("height", 0)
        angle = packet.get("angle", 0)

        print(
            "OBJECT",
            "Height:", round(height, 1),
            "Angle:", round(angle, 1)
        )

        oled.text("OBJECT", 5, 5)
        oled.text(
            "H:{:.1f}mm".format(height),
            5,
            25
        )
        oled.text(
            "A:{:.1f}".format(angle),
            5,
            45
        )

    else:

        print(packet)

        oled.text("UNKNOWN", 5, 5)
        oled.text(packet_type, 5, 25)

    oled.show()


wifi = WiFiManager(

    mode=WIFI.MODE,
    ssid=WIFI.SSID,
    password=WIFI.PASSWORD,
    ip=WIFI.IP,
    port=WIFI.PORT
    oled=oled,
)

wifi.on_receive(show_packet)

wifi.start()

print("Receiver Ready")

while True:
    pass
