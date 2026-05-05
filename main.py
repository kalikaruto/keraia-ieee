# ESP32 FULL SYSTEM
# OLED + LoRa + BNO085 + NEO6M
#
# OLED  : SCK=18 MOSI=23 CS=25 DC=16 RES=17
# LoRa  : SCK=14 MOSI=13 MISO=12 NSS=32 RST=27 DIO0=26
# BNO085: SDA=21 SCL=22
# GPS   : TX=34 RX=33

from machine import Pin, SPI, I2C, UART
import time
from lora import LoRa
import ssd1309
from bno085 import BNO08x
from neo6m import NEO6M

# ──────────────────────────────────────────────────────
# BOOT STABILIZATION
# ──────────────────────────────────────────────────────
print("BOOT: Starting system...")
time.sleep(2)

# ──────────────────────────────────────────────────────
# OLED INIT (VSPI / SPI2)
# ──────────────────────────────────────────────────────
print("INIT: OLED")

spi_oled = SPI(
    2,
    baudrate=10000000,
    polarity=0,
    phase=0,
    sck=Pin(18),
    mosi=Pin(23)
)

oled_cs = Pin(25, Pin.OUT)
oled_dc = Pin(16, Pin.OUT)
oled_res = Pin(17, Pin.OUT)

oled_res.value(0)
time.sleep_ms(50)
oled_res.value(1)
time.sleep_ms(50)

oled = ssd1309.SSD1309(
    128,
    64,
    spi_oled,
    oled_dc,
    oled_res,
    oled_cs
)

oled.fill(0)
oled.text("OLED OK", 0, 24)
oled.show()

print("OLED OK")
time.sleep(1)

# ──────────────────────────────────────────────────────
# LORA INIT (HSPI / SPI1)
# ──────────────────────────────────────────────────────
print("INIT: LoRa")

lora_rst = Pin(27, Pin.OUT)
lora_rst.value(0)
time.sleep_ms(100)
lora_rst.value(1)
time.sleep_ms(300)

spi_lora = SPI(
    1,
    baudrate=5000000,
    polarity=0,
    phase=0,
    sck=Pin(14),
    mosi=Pin(13),
    miso=Pin(12)
)

lora = LoRa(
    spi_lora,
    cs=Pin(32, Pin.OUT),
    rx=Pin(26, Pin.IN),
    frequency=433.0
)

print("LoRa OK")

oled.fill(0)
oled.text("OLED OK", 0, 12)
oled.text("LORA OK", 0, 32)
oled.show()

time.sleep(1)

# ──────────────────────────────────────────────────────
# IMU INIT (BNO085)
# ──────────────────────────────────────────────────────
print("INIT: IMU")

imu_i2c = I2C(
    0,
    scl=Pin(22),
    sda=Pin(21),
    freq=100000
)

imu = BNO08x()

print("IMU OK")

# ──────────────────────────────────────────────────────
# GPS INIT (UART2)
# ──────────────────────────────────────────────────────
print("INIT: GPS")

gps_uart = UART(
    2,
    baudrate=9600,
    tx=Pin(33),
    rx=Pin(34)
)

gps = NEO6M(uart=gps_uart)

print("GPS OK")

# GPS warmup
time.sleep(2)

# ──────────────────────────────────────────────────────
# BOOT SUMMARY
# ──────────────────────────────────────────────────────
oled.fill(0)
oled.text("SYSTEM READY", 0, 0)
oled.text("OLED OK", 0, 12)
oled.text("LORA OK", 0, 24)
oled.text("IMU OK", 0, 36)
oled.text("GPS OK", 0, 48)
oled.show()

print("SYSTEM READY")

# ──────────────────────────────────────────────────────
# PACKET ENCODER
# ──────────────────────────────────────────────────────
def encode_packet(text):
    payload = text.encode("utf-8")
    length = len(payload)

    checksum = length
    for b in payload:
        checksum ^= b

    return bytes([0xAA, length]) + payload + bytes([checksum])

# ──────────────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────────────
counter = 0

while True:
    # Default values
    ax = ay = az = 0.0
    gx = gy = gz = 0.0
    mx = my = mz = 0.0
    roll = pitch = yaw = 0.0
    lat = lon = 0.0
    fix = False

    # ── IMU UPDATE ─────────────────────────────────
    try:
        imu.update()

        ax, ay, az = imu.accel
        gx, gy, gz = imu.gyro
        mx, my, mz = imu.mag
        roll, pitch, yaw = imu.euler

    except Exception as e:
        print("IMU ERROR:", e)

    # ── GPS UPDATE ─────────────────────────────────
    try:
        gps.update()

        gps_lat, gps_lon = gps.location()

        if gps_lat is not None:
            lat = gps_lat

        if gps_lon is not None:
            lon = gps_lon

        fix = gps.has_fix()

    except Exception as e:
        print("GPS ERROR:", e)

    # ──────────────────────────────────────────────
    # SERIAL OUTPUT
    # ──────────────────────────────────────────────
    print("KERAIA - IEEE")
    print("ax,ay,az,gx,gy,gz,mx,my,mz,roll,pitch,yaw,lat,lon,fix")

    print(
        "{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.2f},{:.2f},{:.2f},{:.6f},{:.6f},{}".format(
            ax, ay, az,
            gx, gy, gz,
            mx, my, mz,
            roll, pitch, yaw,
            lat, lon,
            int(fix)
        )
    )

    # ──────────────────────────────────────────────
    # LORA TRANSMIT
    # ──────────────────────────────────────────────
    try:
        msg = "{:.2f},{:.2f},{:.2f},{:.6f},{:.6f},{}".format(
            roll,
            pitch,
            yaw,
            lat,
            lon,
            int(fix)
        )

        packet = encode_packet(msg)

        lora.send(packet)

    except Exception as e:
        print("LORA ERROR:", e)

    # ──────────────────────────────────────────────
    # OLED DISPLAY
    # ──────────────────────────────────────────────
    oled.fill(0)

    oled.text("KERAIA - IEEE", 0, 0)
    oled.text("R:{:.1f}".format(roll), 0, 12)
    oled.text("P:{:.1f}".format(pitch), 0, 24)
    oled.text("Y:{:.1f}".format(yaw), 0, 36)

    if fix:
        oled.text("GPS OK", 0, 52)
    else:
        oled.text("NO FIX", 0, 52)

    oled.show()

    # ──────────────────────────────────────────────
    # LOOP DELAY
    # ──────────────────────────────────────────────
    counter += 1
    time.sleep(1)

