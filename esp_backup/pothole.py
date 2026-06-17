# pothole.py

from math import cos, radians


class PotholeDetector:

    def __init__(
        self,
        tangent_angle_deg,
        window_angle_deg,
        tangent_distance_mm,
        depth_threshold_mm,
    ):
        self.tangent_angle = tangent_angle_deg
        self.window_angle = window_angle_deg
        self.R = tangent_distance_mm
        self.threshold = depth_threshold_mm

    def _angle_diff(self, angle):

        diff = angle - self.tangent_angle

        while diff > 180:
            diff -= 360

        while diff < -180:
            diff += 360

        return diff

    def process_scan(self, scan):

        potholes = []
        objects = []

        for quality, angle, distance in scan:

            theta = self._angle_diff(angle)

            if abs(theta) > self.window_angle:
                continue

            c = cos(radians(theta))

            if c <= 0:
                continue

            expected = self.R / c

            delta = distance - expected

            if delta > self.threshold:

                potholes.append({
                    "angle": angle,
                    "depth": delta,
                    "distance": distance,
                    "expected": expected
                })

            elif delta < -self.threshold:

                objects.append({
                    "angle": angle,
                    "height": -delta,
                    "distance": distance,
                    "expected": expected
                })

        strongest_pothole = None
        strongest_object = None

        if potholes:
            strongest_pothole = max(
                potholes,
                key=lambda p: p["depth"]
            )

        if objects:
            strongest_object = max(
                objects,
                key=lambda p: p["height"]
            )

        if strongest_pothole and strongest_object:

            if strongest_pothole["depth"] >= strongest_object["height"]:

                return {
                    "type": "pothole",
                    "depth": strongest_pothole["depth"],
                    "angle": strongest_pothole["angle"],
                    "distance": strongest_pothole["distance"],
                    "expected": strongest_pothole["expected"],
                }

            return {
                "type": "object",
                "height": strongest_object["height"],
                "angle": strongest_object["angle"],
                "distance": strongest_object["distance"],
                "expected": strongest_object["expected"],
            }

        if strongest_pothole:

            return {
                "type": "pothole",
                "depth": strongest_pothole["depth"],
                "angle": strongest_pothole["angle"],
                "distance": strongest_pothole["distance"],
                "expected": strongest_pothole["expected"],
            }

        if strongest_object:

            return {
                "type": "object",
                "height": strongest_object["height"],
                "angle": strongest_object["angle"],
                "distance": strongest_object["distance"],
                "expected": strongest_object["expected"],
            }

        return None