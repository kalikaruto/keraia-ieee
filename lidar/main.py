import network
import socket
import time
from machine import UART, Pin
from rplidar import RPLidar, RPLidarException

# --- Config ---
SSID     = "Smart Devices"
PASSWORD = "Devices@2023"
PORT     = 5000

# --- Hardware ---
uart  = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
motor = Pin(2, Pin.OUT)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("Connecting to WiFi", end="")
    for _ in range(20):
        if wlan.isconnected():
            break
        print(".", end="")
        time.sleep(1)
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"\nConnected! Pico IP: {ip}")
        return ip
    print("\nWiFi failed!")
    return None


# ── STEP 1: Start lidar FIRST ───────────────────────────────────────────────
lidar = RPLidar(uart, motor_pin=motor)

if not lidar.start_device():
    raise SystemExit("Lidar failed to start")

# ── STEP 2: Connect WiFi ────────────────────────────────────────────────────
ip = connect_wifi()
if ip is None:
    lidar.stop_device()
    raise SystemExit("WiFi failed")

# ── STEP 3: Wait for laptop ─────────────────────────────────────────────────
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', PORT))
server.listen(1)
print(f"Waiting for laptop on {ip}:{PORT} ...")

conn, addr = server.accept()
conn.setblocking(False)
print(f"Laptop connected from {addr}")

# ── STEP 4: Stream scan data ────────────────────────────────────────────────
try:
    for payload in lidar.iter_raw_scans():
        try:
            conn.sendall(payload.encode())
        except OSError:
            print("Client disconnected")
            break

except KeyboardInterrupt:
    print("Stopping...")

finally:
    lidar.stop_device()
    conn.close()
    server.close()
    print("Done.")

