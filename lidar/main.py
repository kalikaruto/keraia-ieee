import network
import socket
import time
from machine import UART, Pin

# --- WiFi ---
SSID = "Smart Devices"
PASSWORD = "Devices@2023"
PORT = 5000

# --- RPLidar Setup ---
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
motor = Pin(2, Pin.OUT)

SYNC_BYTE  = 0xA5
SYNC_BYTE2 = 0x5A
CMD_STOP   = 0x25
CMD_RESET  = 0x40
CMD_SCAN   = 0x20
DESCRIPTOR_LEN = 7
SCAN_DATA_LEN  = 5


def send_command(cmd):
    uart.write(bytes([SYNC_BYTE, cmd]))


def flush_uart(duration_ms=200):
    """Read and discard all pending bytes."""
    deadline = time.ticks_add(time.ticks_ms(), duration_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        data = uart.read(128)
        if data is None:
            time.sleep_ms(10)


def stop_scan():
    send_command(CMD_STOP)
    time.sleep_ms(150)
    flush_uart(200)


def reset_lidar():
    send_command(CMD_RESET)
    time.sleep_ms(2000)   # A1M8 needs ~1-2s after reset
    flush_uart(500)        # flush all boot messages


def read_descriptor(timeout_ms=1000):
    """Wait up to timeout_ms for a valid 7-byte descriptor."""
    buf = bytearray()
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)

    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        chunk = uart.read(1)
        if chunk is None:
            time.sleep_ms(5)
            continue
        buf += chunk

        # Keep only last 7 bytes
        if len(buf) > DESCRIPTOR_LEN:
            buf = buf[-DESCRIPTOR_LEN:]

        if len(buf) == DESCRIPTOR_LEN:
            if buf[0] == SYNC_BYTE and buf[1] == SYNC_BYTE2:
                data_type = buf[6]
                print(f"Descriptor OK: type=0x{data_type:02X}")
                return data_type

    print("ERROR: Descriptor timeout")
    return None


def parse_scan_packet(raw):
    if len(raw) < SCAN_DATA_LEN:
        return None
    s     = (raw[0] >> 0) & 0x01
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
    return quality, angle, distance


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


def start_lidar():
    """Full lidar startup sequence with verification."""
    print("Resetting lidar...")
    motor.value(0)         # motor off during reset
    stop_scan()
    reset_lidar()

    print("Starting motor...")
    motor.value(1)
    time.sleep_ms(1000)    # let motor reach speed

    print("Sending SCAN command...")
    send_command(CMD_SCAN)

    desc = read_descriptor(timeout_ms=2000)
    if desc is None:
        return False

    print("Lidar ready — scanning!")
    return True


# ── STEP 1: Start lidar FIRST, before WiFi/socket ──────────────────────────
if not start_lidar():
    motor.value(0)
    raise SystemExit("Lidar failed to start")

# ── STEP 2: Connect WiFi ────────────────────────────────────────────────────
ip = connect_wifi()
if ip is None:
    stop_scan()
    motor.value(0)
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
buf = bytearray()
scan_points = []
last_angle  = 0

try:
    while True:
        # Read UART
        chunk = uart.read(128)
        if chunk:
            buf += chunk

        # Parse packets
        while len(buf) >= SCAN_DATA_LEN:
            result = parse_scan_packet(buf)
            if result:
                quality, angle, distance = result
                buf = buf[SCAN_DATA_LEN:]

                # Detect scan boundary (angle wraps 359 → ~0)
                if angle < 10 and last_angle > 300 and scan_points:
                    # Send complete scan
                    payload = ""
                    for q, a, d in scan_points:
                        payload += f"{q},{a:.2f},{d:.1f}\n"
                    payload += "---\n"
                    try:
                        conn.sendall(payload.encode())
                    except OSError:
                        print("Client disconnected")
                        raise KeyboardInterrupt
                    scan_points = []

                if distance > 0:
                    scan_points.append((quality, angle, distance))

                last_angle = angle
            else:
                buf = buf[1:]   # re-sync

except KeyboardInterrupt:
    print("Stopping...")
finally:
    stop_scan()
    motor.value(0)
    conn.close()
    server.close()
    print("Done.")

