import time
from wifi_manager import WiFiManager
from oled import OLED
import json

# ---------------------------------------------------------------------------
# Config — must match sender's AP settings
# ---------------------------------------------------------------------------
WIFI_MODE = "sta"
SSID      = "LidarNetwork"
PASSWORD  = "lidar1234"
SERVER_IP = "192.168.4.1"   # sender ESP32 AP IP
PORT      = 5000

# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------
wifi = WiFiManager(
    mode=WIFI_MODE,
    ssid=SSID,
    password=PASSWORD,
    ip=SERVER_IP,
    port=PORT,
)

oled = OLED()
# ---------------------------------------------------------------------------
# RX callback — called by WiFiManager._rx_loop on every received message
# ---------------------------------------------------------------------------
def on_data(msg):
    msg = msg.strip()
    if not msg:
        return

    try:
        data = json.loads(msg)
    except ValueError:
        print("BAD JSON:", msg)
        return

    n        = data.get("n", 0)
    baseline = data.get("baseline", 0.0)
    potholes = data.get("potholes", [])
    latitude = data.get("latitude", "-")
    longitude = data.get("longitude", "-")

#     print("-" * 40)
#     print(f"Points : {n}")
#     print(f"Baseline: {baseline:.1f} mm ({abs(baseline):.0f} mm above ground)")

    if not potholes:
        print("")
        oled.reset()
    else:
        print("Pothole ahead")
        print(f"N: {n}, baseline: {baseline:.1f} mm ({abs(baseline):.0f} mm above ground), latitude: {latitude:.2f}, longitude: {longitude:.2f}")
        oled.center_text("POTHOLE AHEAD", 32)

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
wifi.on_receive(on_data)
wifi.start()   # connects to sender AP, spawns rx thread, then returns

print("Listening for pothole data...")

# Keep main thread alive — rx_loop runs in background thread
try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("Stopped.")


