class Calibration:

    @staticmethod
    def angle_diff(a, b):

        d = a - b

        while d > 180:
            d -= 360

        while d < -180:
            d += 360

        return d

    @staticmethod
    def calibrate(
        lidar,
        tangent_angle,
        search_window,
        scans
    ):

        values = []

        print("Calibrating...")

        completed = 0

        for scan in lidar.iter_scans():

            completed += 1

            for quality, angle, distance in scan:

                if distance <= 0:
                    continue

                diff = Calibration.angle_diff(
                    angle,
                    tangent_angle
                )

                if abs(diff) > search_window:
                    continue

                values.append(distance)

            if completed >= scans:
                break

        values.sort()

        n = len(values)

        if n == 0:
            raise RuntimeError(
                "Calibration failed."
            )

        if n % 2:

            return values[n // 2]

        return (
            values[n // 2 - 1]
            + values[n // 2]
        ) / 2