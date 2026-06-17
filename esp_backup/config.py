from machine import Pin

class OLED:
    SDA = 21
    SCL = 22

    WIDTH = 128
    HEIGHT = 64


class LIDAR:
    UART_ID = 2

    TX = 17
    RX = 16
    CTRL_M = 4

    BAUDRATE = 115200


class POTHOLE:

    TANGENT_ANGLE = 0

    WINDOW_ANGLE = 20

    TANGENT_DISTANCE_MM = 389

    DEPTH_THRESHOLD_MM = 20


class CALIBRATION:

    SCANS = 20

    SEARCH_WINDOW = 2


class WIFI:

    MODE = "ap"

    SSID = "ESP32_LINK"
    PASSWORD = "12345678"

    IP = "192.168.4.1"
    PORT = 5000

    HEARTBEAT_MS = 3000

    RECONNECT_DELAY_MS = 1000
