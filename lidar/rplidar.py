from machine import UART, Pin
import time

# --- Setup ---
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
motor = Pin(2, Pin.OUT)

# --- Constants ---
SYNC_BYTE  = 0xA5
SYNC_BYTE2 = 0x5A
CMD_STOP   = 0x25
CMD_RESET  = 0x40
CMD_SCAN   = 0x20
CMD_EXPRESS_SCAN = 0x82
CMD_GET_INFO     = 0x50
CMD_GET_HEALTH   = 0x52

DESCRIPTOR_LEN = 7
SCAN_DATA_LEN  = 5


def send_command(cmd):
    uart.write(bytes([SYNC_BYTE, cmd]))


def stop_scan():
    send_command(CMD_STOP)
    time.sleep_ms(100)
    uart.read()  # flush


def reset_lidar():
    send_command(CMD_RESET)
    time.sleep_ms(500)
    uart.read()  # flush


def read_descriptor():
    """Read and validate 7-byte response descriptor."""
    buf = uart.read(DESCRIPTOR_LEN)
    if buf is None or len(buf) < DESCRIPTOR_LEN:
        return None
    if buf[0] != SYNC_BYTE or buf[1] != SYNC_BYTE2:
        print(f"Bad descriptor sync: {buf.hex()}")
        return None
    data_len  = buf[2] | (buf[3] << 8) | (buf[4] << 16) | (buf[5] << 24)
    data_type = buf[6]
    return data_len, data_type


def get_health():
    stop_scan()
    send_command(CMD_GET_HEALTH)
    time.sleep_ms(100)
    desc = read_descriptor()
    if desc is None:
        print("No health descriptor")
        return
    data = uart.read(3)
    if data and len(data) == 3:
        status = data[0]
        error_code = data[1] | (data[2] << 8)
        labels = {0: "Good", 1: "Warning", 2: "Error"}
        print(f"Health: {labels.get(status, 'Unknown')}  Error code: {error_code}")


def get_info():
    stop_scan()
    send_command(CMD_GET_INFO)
    time.sleep_ms(100)
    desc = read_descriptor()
    if desc is None:
        print("No info descriptor")
        return
    data = uart.read(20)
    if data and len(data) == 20:
        model    = data[0]
        fw_minor = data[1]
        fw_major = data[2]
        hw       = data[3]
        serial   = data[4:].hex()
        print(f"Model: {model}  FW: {fw_major}.{fw_minor}  HW: {hw}  Serial: {serial}")


def parse_scan_packet(raw):
    """
    Parse one 5-byte standard scan packet.
    Returns (quality, angle_deg, distance_mm) or None on error.
    """
    if len(raw) < SCAN_DATA_LEN:
        return None

    # Byte 0: quality (bits 7-2), S (bit 1), S_bar (bit 0)
    s     = (raw[0] >> 0) & 0x01
    s_bar = (raw[0] >> 1) & 0x01
    if s == s_bar:          # start-bit check
        return None
    quality = raw[0] >> 2

    # Byte 1-2: angle (15 bits, Q6)
    if not (raw[1] & 0x01):  # check bit must be 1
        return None
    angle_q6 = ((raw[1] >> 1) | (raw[2] << 7)) & 0x7FFF
    angle = angle_q6 / 64.0

    # Byte 3-4: distance (16 bits, Q2 in mm)
    distance_q2 = raw[3] | (raw[4] << 8)
    distance = distance_q2 / 4.0

    return quality, angle, distance


def start_scan():
    stop_scan()
    time.sleep_ms(50)

    motor.value(1)          # spin up motor
    time.sleep_ms(500)

    send_command(CMD_SCAN)
    time.sleep_ms(100)

    desc = read_descriptor()
    if desc is None:
        print("ERROR: No scan descriptor received.")
        return False
    print(f"Scan descriptor OK — type=0x{desc[1]:02X}")
    return True


# --- Main ---
print("=== RPLidar A1M8 - MicroPython ===")
reset_lidar()
get_info()
get_health()

print("\nStarting scan...\n")
if not start_scan():
    motor.value(0)
    raise SystemExit

scan_count = 0
buf = bytearray()

try:
    while True:
        # Read available bytes into rolling buffer
        chunk = uart.read(32)
        if chunk:
            buf += chunk

        # Process complete 5-byte packets from buffer
        while len(buf) >= SCAN_DATA_LEN:
            result = parse_scan_packet(buf)
            if result:
                quality, angle, distance = result
                buf = buf[SCAN_DATA_LEN:]  # consume packet
                scan_count += 1

                # Only print non-zero distance readings
                if distance > 0:
                    print(f"#{scan_count:05d} | Angle: {angle:6.2f}°  Dist: {distance:7.1f} mm  Quality: {quality}")
            else:
                # Sync lost — skip one byte and re-align
                buf = buf[1:]

except KeyboardInterrupt:
    print("\nStopped by user.")
    stop_scan()
    motor.value(0)

