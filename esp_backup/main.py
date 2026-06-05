import time
from machine import UART, Pin
from rplidar import RPLidar
from wifi_manager import WiFiManager
from gps import GPS
import math
import json

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WIFI_MODE   = "ap"
SSID        = "LidarNetwork"
PASSWORD    = "lidar1234"
IP          = "192.168.4.1"
PORT        = 5000

POTHOLE_THRESHOLD_MM = 50    # how much deeper than baseline to count as pothole
POTHOLE_MIN_WIDTH_MM = 30    # minimum width to count as pothole
ANGLE_LEFT           = -45   # scan cone left bound (degrees)
ANGLE_RIGHT          = 45    # scan cone right bound (degrees)

# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------
uart  = UART(2, baudrate=115200, tx=Pin(17), rx=Pin(16))
motor = Pin(4, Pin.OUT)

# ---------------------------------------------------------------------------
# Pothole detection (mirrors laptop-side logic, no numpy)
# ---------------------------------------------------------------------------

def process_scan(scan):
    """
    Convert raw (quality, angle, distance) scan points into
    (x, y) coordinates within the configured angle cone.

    Returns list of (x, y) tuples in mm.
    """
    points = []
    for _, angle, distance in scan:
        if angle > 180:
            angle -= 360
        if ANGLE_LEFT <= angle <= ANGLE_RIGHT:
            radians = angle * math.pi / 180.0
            y = -distance * math.cos(radians)
            x =  distance * math.sin(radians)
            points.append((x, y))
    return points


def median(values):
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return (s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0)


def detect_potholes(points):
    """
    Detect potholes from (x, y) points.

    Returns list of dicts:
        center_x   : float  (mm)
        depth_mm   : float  (mm below baseline)
        width_mm   : float  (mm)
        baseline_mm: float  (mm)
    """
    if len(points) < 5:
        return [], 0.0

    y_vals   = [p[1] for p in points]
    baseline = median(y_vals)

    # Sort by x for left-to-right traversal
    ordered  = sorted(points, key=lambda p: p[0])

    potholes  = []
    in_hole   = False
    hole_pts  = []

    for x, y in ordered:
        if y < baseline - POTHOLE_THRESHOLD_MM:
            in_hole = True
            hole_pts.append((x, y))
        else:
            if in_hole:
                width = max(p[0] for p in hole_pts) - min(p[0] for p in hole_pts)
                if width >= POTHOLE_MIN_WIDTH_MM:
                    potholes.append({
                        "cx":  sum(p[0] for p in hole_pts) / len(hole_pts),
                        "depth": baseline - sum(p[1] for p in hole_pts) / len(hole_pts),
                        "width": width,
                        "baseline": baseline,
                    })
                hole_pts = []
                in_hole  = False

    return potholes, baseline


def build_payload(potholes, baseline, n_points, gps_summary):
    """
    Build a compact JSON string to send over WiFi.

    Format:
    {
        "n": <int>,               # number of scan points used
        "baseline": <float>,      # baseline distance in mm
        "potholes": [
            {"cx": <float>, "depth": <float>, "width": <float>},
            ...
        ]
    }
    """
    return json.dumps({
        "n":        n_points,
        "baseline": round(baseline, 1),
        "potholes": [
            {
                "cx":    round(p["cx"],    1),
                "depth": round(p["depth"], 1),
                "width": round(p["width"], 1),
                "latitude": gps_summary.get("latitude","-"),
                "longitude": gps_summary.get("longitude", "-")
            }
            for p in potholes
        ]
    }) + "\n"


# ---------------------------------------------------------------------------
# STEP 1: Start lidar FIRST
# ---------------------------------------------------------------------------
lidar = RPLidar(uart, motor_pin=motor)

if not lidar.start_device():
    raise SystemExit("Lidar failed to start")
gps = GPS()

# ---------------------------------------------------------------------------
# STEP 2: Start WiFi and wait for client
# ---------------------------------------------------------------------------
wifi = WiFiManager(
    mode=WIFI_MODE,
    ssid=SSID,
    password=PASSWORD,
    ip=IP,
    port=PORT,
)
wifi.start()

# ---------------------------------------------------------------------------
# STEP 3: Process scans and send pothole metadata only
# ---------------------------------------------------------------------------
try:
    print("starting")
    for raw_scan in lidar.iter_raw_scans():
        # raw_scan is the "quality,angle,distance\n...\n---\n" string;
        # parse it back into tuples for processing
        scan_points = []
        for line in raw_scan.split("\n"):
            line = line.strip()
            if not line or line == "---":
                continue
            try:
                q, a, d = line.split(",")
                scan_points.append((float(q), float(a), float(d)))
            except ValueError:
                continue

        if not scan_points:
            continue
        summary = {}
        if gps.update():
            if gps.has_fix():
                summary = gps.summary()
                print(gps.summary())
        points             = process_scan(scan_points)
        potholes, baseline = detect_potholes(points)
        payload            = build_payload(potholes, baseline, len(points), summary)
#         print(payload)
        wifi.send(payload.rstrip("\n"))

except KeyboardInterrupt:
    print("Stopping...")

finally:
    lidar.stop_device()
    print("Done.")