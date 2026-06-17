# tx main.py

from machine import UART

from config import (
    LIDAR,
    POTHOLE,
    CALIBRATION,
    WIFI,
)

from oled import OLED
from wifi_manager import WiFiManager
from rplidar import RPLidar
from calibration import Calibration
from pothole import PotholeDetector
import ui


def initialize():

    oled = OLED()

    wifi = WiFiManager(
        mode=WIFI.MODE,
        ssid=WIFI.SSID,
        password=WIFI.PASSWORD,
        ip=WIFI.IP,
        port=WIFI.PORT,
        oled=oled,
    )

    wifi.start()

    uart = UART(
        LIDAR.UART_ID,
        baudrate=LIDAR.BAUDRATE,
        tx=LIDAR.TX,
        rx=LIDAR.RX,
    )

    lidar = RPLidar(
        uart,
        LIDAR.CTRL_M
    )

    lidar.start_device()

    R = Calibration.calibrate(
        lidar,
        tangent_angle=POTHOLE.TANGENT_ANGLE,
        search_window=CALIBRATION.SEARCH_WINDOW,
        scans=CALIBRATION.SCANS,
    )

    print("Calibration:", round(R, 2), "mm")

    detector = PotholeDetector(
        tangent_angle_deg=POTHOLE.TANGENT_ANGLE,
        window_angle_deg=POTHOLE.WINDOW_ANGLE,
        tangent_distance_mm=R,
        depth_threshold_mm=POTHOLE.DEPTH_THRESHOLD_MM,
    )

    return oled, wifi, lidar, detector

def publish(result, oled, wifi):

    ui.print_result(result)

    ui.display_result(
        oled,
        result
    )

    wifi.send(result)


def main():

    oled, wifi, lidar, detector = initialize()

    while True:

        for scan in lidar.iter_scans():

            result = detector.process_scan(scan)

            if result is None:
                continue

            publish(
                result,
                oled,
                wifi
            )


if __name__ == "__main__":

    main()
