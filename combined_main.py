# combined_main.py — ESP32-WROOM Pothole Detection System
#
# All sensors connected directly to this ESP32.
# Scans LiDAR, detects potholes, geotags with GPS,
# transmits events via LoRa and WiFi UDP.
#
# Wiring:
#   RPLidar A1M8 TX → ESP32 GPIO5  (UART1 RX)
#   RPLidar A1M8 RX → ESP32 GPIO4  (UART1 TX)
#   RPLidar motor   → ESP32 GPIO15 (HIGH = spin)
#   NEO-6M TX       → ESP32 GPIO34 (UART2 RX)
#   NEO-6M RX       → ESP32 GPIO33 (UART2 TX)
#   LoRa SCK=14 MOSI=13 MISO=12 NSS=32 RST=27 DIO0=26  (SPI1/HSPI)
#   OLED SCK=18 MOSI=23 CS=25 DC=16 RES=17              (SPI2/VSPI)

import math
import time
import gc
import network
import socket
from machine import Pin, SPI, UART

from lora import LoRa
import ssd1309
from neo6m import NEO6M

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

WIFI_SSID     = "Smart Devices"
WIFI_PASSWORD = "Devices@2023"
RECV_IP       = "10.1.16.100"  # WiFi receiver (laptop/server) — update this
RECV_PORT     = 5001            # UDP port on the receiver

DEPTH_THRESHOLD_MM = 50     # minimum pothole depth to trigger event
WIDTH_THRESHOLD_MM = 30     # minimum pothole width to trigger event
SCAN_HALF_ANGLE    = 45     # use LiDAR points within ±45° forward cone
EVENT_DEBOUNCE_MS  = 2000   # minimum ms between transmitted events
OLED_EVERY_N_SCANS = 5      # update display every N scans (~1 Hz at 5.5 Hz spin)

# LiDAR protocol constants (RPLidar A1M8)
_SYNC     = 0xA5
_SYNC2    = 0x5A
_CMD_STOP = 0x25
_CMD_RST  = 0x40
_CMD_SCAN = 0x20
_DESC_LEN = 7
_PKT_LEN  = 5

# ── OLED ──────────────────────────────────────────────────────────────────────

spi_oled = SPI(2, baudrate=10_000_000, polarity=0, phase=0,
               sck=Pin(18), mosi=Pin(23))
oled_cs  = Pin(25, Pin.OUT)
oled_dc  = Pin(16, Pin.OUT)
oled_res = Pin(17, Pin.OUT)

oled_res.value(0)
time.sleep_ms(50)
oled_res.value(1)
time.sleep_ms(50)

oled = ssd1309.SSD1309(128, 64, spi_oled, oled_dc, oled_res, oled_cs)

def disp(lines):
    oled.fill(0)
    for i, line in enumerate(lines[:6]):
        oled.text(str(line)[:16], 0, i * 10)
    oled.show()

disp(["KERAIA - IEEE", "Booting..."])
print("BOOT: KERAIA system starting")

# ── LIDAR ─────────────────────────────────────────────────────────────────────

_lidar_uart  = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5))
_lidar_motor = Pin(15, Pin.OUT)
_lidar_motor.value(0)

def _lidar_cmd(cmd):
    _lidar_uart.write(bytes([_SYNC, cmd]))

def _lidar_flush(ms=200):
    deadline = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if _lidar_uart.any():
            _lidar_uart.read(128)
        else:
            time.sleep_ms(10)

def _lidar_read_descriptor(timeout_ms=2000):
    buf = bytearray()
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        b = _lidar_uart.read(1)
        if b is None:
            time.sleep_ms(5)
            continue
        buf += b
        if len(buf) > _DESC_LEN:
            buf = buf[-_DESC_LEN:]
        if len(buf) == _DESC_LEN and buf[0] == _SYNC and buf[1] == _SYNC2:
            return buf[6]  # data type byte
    return None

def lidar_start():
    print("LIDAR: resetting...")
    _lidar_motor.value(0)
    _lidar_cmd(_CMD_STOP)
    time.sleep_ms(150)
    _lidar_flush(200)
    _lidar_cmd(_CMD_RST)
    time.sleep_ms(2000)
    _lidar_flush(500)

    print("LIDAR: motor spin-up...")
    _lidar_motor.value(1)
    time.sleep_ms(1000)

    print("LIDAR: sending SCAN command...")
    _lidar_cmd(_CMD_SCAN)
    dtype = _lidar_read_descriptor(2000)
    if dtype is None:
        return False
    print("LIDAR: ready, descriptor type=0x{:02X}".format(dtype))
    return True

def lidar_parse_packet(raw):
    """
    Parse one 5-byte RPLidar scan packet.
    Returns (quality, angle_deg, distance_mm, is_new_scan) or None on bad packet.
    """
    if len(raw) < _PKT_LEN:
        return None
    s     = raw[0] & 0x01
    s_bar = (raw[0] >> 1) & 0x01
    if s == s_bar:
        return None
    quality = raw[0] >> 2
    if not (raw[1] & 0x01):
        return None
    angle_q6 = ((raw[1] >> 1) | (raw[2] << 7)) & 0x7FFF
    angle    = angle_q6 / 64.0
    dist_q2  = raw[3] | (raw[4] << 8)
    distance = dist_q2 / 4.0
    return quality, angle, distance, (s == 1)

# ── LORA ──────────────────────────────────────────────────────────────────────

lora_rst = Pin(27, Pin.OUT)
lora_rst.value(0)
time.sleep_ms(100)
lora_rst.value(1)
time.sleep_ms(300)

spi_lora = SPI(1, baudrate=5_000_000, polarity=0, phase=0,
               sck=Pin(14), mosi=Pin(13), miso=Pin(12))
lora = LoRa(spi_lora, cs=Pin(32, Pin.OUT), rx=Pin(26, Pin.IN), frequency=433.0)
print("INIT: LoRa OK")

# ── GPS ───────────────────────────────────────────────────────────────────────

gps_uart = UART(2, baudrate=9600, tx=Pin(33), rx=Pin(34))
gps = NEO6M(uart=gps_uart)
print("INIT: GPS OK")

disp(["KERAIA - IEEE", "LoRa OK", "GPS OK", "WiFi connecting..."])

# ── WIFI ──────────────────────────────────────────────────────────────────────

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASSWORD)

print("INIT: WiFi connecting", end="")
for _ in range(20):
    if wlan.isconnected():
        break
    print(".", end="")
    time.sleep(1)
print()

wifi_ok = wlan.isconnected()
my_ip   = wlan.ifconfig()[0] if wifi_ok else "0.0.0.0"
print("INIT: WiFi", my_ip if wifi_ok else "FAILED")

udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if wifi_ok else None

disp([
    "KERAIA - IEEE",
    "LoRa OK",
    "GPS OK",
    "WiFi:" + ("OK" if wifi_ok else "FAIL"),
    my_ip,
])
time.sleep(1)

# ── START LIDAR ───────────────────────────────────────────────────────────────

disp(["KERAIA - IEEE", "LiDAR starting..."])
if not lidar_start():
    _lidar_motor.value(0)
    disp(["KERAIA - IEEE", "LIDAR FAILED!", "Check wiring."])
    raise SystemExit("LiDAR init failed")
print("INIT: LiDAR OK")

# ── PACKET ENCODER (LoRa wire format) ────────────────────────────────────────

def encode_packet(text):
    payload  = text.encode("utf-8")
    checksum = len(payload)
    for b in payload:
        checksum ^= b
    return bytes([0xAA, len(payload)]) + payload + bytes([checksum])

# ── POTHOLE DETECTION (pure Python — no numpy) ────────────────────────────────

def _median(lst):
    s = sorted(lst)
    n = len(s)
    return s[n // 2] if n & 1 else (s[n // 2 - 1] + s[n // 2]) * 0.5

def _mean(lst):
    return sum(lst) / len(lst) if lst else 0.0

def process_scan(scan_points):
    """Filter to forward cone and convert polar → Cartesian (mm)."""
    xs, ys = [], []
    for _, angle, distance, _ in scan_points:
        if angle > 180:
            angle -= 360
        if -SCAN_HALF_ANGLE <= angle <= SCAN_HALF_ANGLE and distance > 0:
            rad = math.radians(angle)
            xs.append(distance * math.sin(rad))
            ys.append(-distance * math.cos(rad))
    return xs, ys

def detect_potholes(xs, ys):
    """
    Find contiguous x-sorted regions deeper than baseline by DEPTH_THRESHOLD_MM
    and at least WIDTH_THRESHOLD_MM wide.
    """
    if len(ys) < 5:
        return []
    baseline = _median(ys)
    potholes = []
    in_hole  = False
    hole_x   = []
    hole_y   = []
    for xi, yi in sorted(zip(xs, ys), key=lambda p: p[0]):
        if yi < baseline - DEPTH_THRESHOLD_MM:
            in_hole = True
            hole_x.append(xi)
            hole_y.append(yi)
        else:
            if in_hole:
                w = max(hole_x) - min(hole_x)
                if w >= WIDTH_THRESHOLD_MM:
                    potholes.append({
                        "depth_mm": baseline - _mean(hole_y),
                        "width_mm": w,
                        "center_x": _mean(hole_x),
                    })
                hole_x, hole_y, in_hole = [], [], False
    if in_hole and hole_x:
        w = max(hole_x) - min(hole_x)
        if w >= WIDTH_THRESHOLD_MM:
            potholes.append({
                "depth_mm": baseline - _mean(hole_y),
                "width_mm": w,
                "center_x": _mean(hole_x),
            })
    return potholes

# ── TRANSMISSION ──────────────────────────────────────────────────────────────

def transmit_event(lat, lon, depth_mm, width_mm):
    msg = "POTHOLE,{:.6f},{:.6f},{:.1f},{:.1f}".format(lat, lon, depth_mm, width_mm)
    print("EVENT:", msg)
    if udp_sock:
        try:
            udp_sock.sendto(msg.encode(), (RECV_IP, RECV_PORT))
        except Exception as e:
            print("WiFi TX error:", e)
    try:
        lora.send(encode_packet(msg))
    except Exception as e:
        print("LoRa TX error:", e)

# ── MAIN LOOP ─────────────────────────────────────────────────────────────────

lat      = 0.0
lon      = 0.0
fix      = False
scan_cnt = 0
ph_cnt   = 0
last_evt = time.ticks_add(time.ticks_ms(), -EVENT_DEBOUNCE_MS)

uart_buf    = bytearray()
scan_points = []

print("SYSTEM READY")
disp(["KERAIA - IEEE", "Scanning...", "PH: 0"])

while True:
    # ── Read all available LiDAR bytes into rolling buffer ─────────────────
    chunk = _lidar_uart.read(128)
    if chunk:
        uart_buf += chunk

    # ── Parse complete 5-byte packets ──────────────────────────────────────
    scan_ready = False
    while len(uart_buf) >= _PKT_LEN:
        result = lidar_parse_packet(uart_buf)
        if result is None:
            uart_buf = uart_buf[1:]  # bad sync byte — shift and retry
            continue

        quality, angle, distance, is_new_scan = result

        # Scan boundary: new_scan flag set while we already have points
        if is_new_scan and scan_points:
            scan_ready = True
            break  # leave this packet in uart_buf — it starts the next scan

        uart_buf = uart_buf[_PKT_LEN:]
        if distance > 0:
            scan_points.append((quality, angle, distance, is_new_scan))

    # ── GPS update (non-blocking) ──────────────────────────────────────────
    try:
        gps.update()
        g_lat, g_lon = gps.location()
        if g_lat is not None:
            lat, lon = g_lat, g_lon
        fix = gps.has_fix()
    except Exception as e:
        print("GPS error:", e)

    if not scan_ready:
        continue

    # ── Process completed scan ─────────────────────────────────────────────
    scan_cnt  += 1
    completed  = scan_points[:]
    scan_points = []  # reset for next scan

    xs, ys   = process_scan(completed)
    potholes = detect_potholes(xs, ys)

    if potholes:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_evt) >= EVENT_DEBOUNCE_MS:
            biggest  = max(potholes, key=lambda p: p["depth_mm"])
            ph_cnt  += 1
            last_evt = now
            transmit_event(lat, lon, biggest["depth_mm"], biggest["width_mm"])
            disp([
                "** POTHOLE! **",
                "#{} D:{:.0f}mm".format(ph_cnt, biggest["depth_mm"]),
                "W:{:.0f}mm".format(biggest["width_mm"]),
                "LAT:{:.5f}".format(lat),
                "LON:{:.5f}".format(lon),
                "FIX:{}".format("YES" if fix else "NO"),
            ])
    elif scan_cnt % OLED_EVERY_N_SCANS == 0:
        disp([
            "KERAIA - IEEE",
            "Scans:{}".format(scan_cnt),
            "PH:{}".format(ph_cnt),
            "LAT:{:.5f}".format(lat),
            "LON:{:.5f}".format(lon),
            "FIX:{}".format("YES" if fix else "NO"),
        ])

    if scan_cnt % 20 == 0:
        gc.collect()
