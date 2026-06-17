import wifi_manager
import oled
WIFI_MODE = "sta"
SSID      = "Guest"
PASSWORD  = "Hol2023@"
SERVER_IP = "192.168.4.1"   # sender ESP32 AP IP
PORT      = 5000
oled.init()
wifi = wifi_manager.WiFiManager(
    mode=WIFI_MODE,
    ssid=SSID,
    password=PASSWORD,
    ip=SERVER_IP,
    port=PORT,
)
wifi.start()