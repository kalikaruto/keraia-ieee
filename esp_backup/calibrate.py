from machine import UART, Pin
from config import LIDAR
from rplidar import RPLidar
from config import POTHOLE
from pothole import PotholeDetector

uart = UART(
    LIDAR.UART_ID,
    baudrate=LIDAR.BAUDRATE,
    tx=LIDAR.TX,
    rx=LIDAR.RX
)

lidar = RPLidar(uart, LIDAR.CTRL_M)

lidar.start_device()

detector = PotholeDetector(
    tangent_angle_deg=POTHOLE.TANGENT_ANGLE,
    window_angle_deg=POTHOLE.WINDOW_ANGLE,
    tangent_distance_mm=POTHOLE.TANGENT_DISTANCE_MM,
    depth_threshold_mm=POTHOLE.DEPTH_THRESHOLD_MM,
)

from calibration import Calibration

R = Calibration.calibrate(
    lidar,
    tangent_angle_deg=0,
    search_window_deg=2,
    num_scans=20
)

print("R =", R)