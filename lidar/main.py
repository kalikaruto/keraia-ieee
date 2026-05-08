from machine import UART, Pin
from rplidar import RPLidar
import time

# -----------------------------
# GPS UART
# -----------------------------
gps_uart = UART(
    1,
    baudrate=9600,
    tx=5,
    rx=4
)

# -----------------------------
# LIDAR UART
# -----------------------------
lidar_uart = UART(
    2,
    baudrate=115200,
    tx=17,   # TX2
    rx=16    # RX2
)

# -----------------------------
# Motor control
# -----------------------------
motor_pin = Pin(25, Pin.OUT)
motor_pin.on()   # start motor

# -----------------------------
# Initialize lidar
# -----------------------------
lidar = RPLidar(lidar_uart)

print("Starting lidar...")
time.sleep(2)

DIST_THRESHOLD = 150  # mm


# -----------------------------
# GPS helper
# -----------------------------
def get_gps():
    """
    Very simple NMEA parser.
    Extracts lat/lon from GPGGA.
    """

    if gps_uart.any():
        line = gps_uart.readline()

        if line:
            try:
                line = line.decode('utf-8')

                if "$GPGGA" in line:
                    parts = line.split(',')

                    if len(parts) > 5:
                        lat = parts[2]
                        lat_dir = parts[3]

                        lon = parts[4]
                        lon_dir = parts[5]

                        return lat, lat_dir, lon, lon_dir

            except:
                pass

    return None


# -----------------------------
# Main loop
# -----------------------------
try:

    for scan in lidar.iter_scans():

        for (_, angle, distance) in scan:

            if distance > 0 and distance < DIST_THRESHOLD:

                print("⚠ Object detected")
                print("Distance:", distance, "mm")
                print("Angle:", angle)

                gps = get_gps()

                if gps:
                    lat, lat_dir, lon, lon_dir = gps

                    print("GPS:")
                    print("Lat:", lat, lat_dir)
                    print("Lon:", lon, lon_dir)

                else:
                    print("GPS not locked")

                print("-------------------")

                time.sleep(1)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    lidar.stop()
    lidar.disconnect()
    motor_pin.off()

