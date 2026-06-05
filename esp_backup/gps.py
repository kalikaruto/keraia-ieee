# gps.py

from machine import UART

from config import GPS as GPSConfig


class GPS:

    def __init__(self):

        self.uart = UART(
            GPSConfig.UART_ID,
            baudrate=GPSConfig.BAUDRATE,
            tx=GPSConfig.TX,
            rx=GPSConfig.RX,
            timeout=GPSConfig.TIMEOUT
        )

        self.latitude = None
        self.longitude = None

        self.altitude = None

        self.speed = 0.0
        self.course = 0.0

        self.satellites = 0

        self.hdop = None

        self.fix = False

        self.timestamp = None
        self.date = None

    # -------------------------------------------------
    # INTERNALS
    # -------------------------------------------------

    def _convert_coordinate(self, raw, direction):

        if not raw:
            return None

        try:

            if direction in ("N", "S"):

                degrees = int(raw[:2])
                minutes = float(raw[2:])

            else:

                degrees = int(raw[:3])
                minutes = float(raw[3:])

            value = degrees + (minutes / 60)

            if direction in ("S", "W"):
                value *= -1

            return value

        except:
            return None

    def _parse_gga(self, parts):

        try:

            self.latitude = self._convert_coordinate(
                parts[2],
                parts[3]
            )

            self.longitude = self._convert_coordinate(
                parts[4],
                parts[5]
            )

            self.fix = parts[6] != "0"

            self.satellites = (
                int(parts[7])
                if parts[7]
                else 0
            )

            self.hdop = (
                float(parts[8])
                if parts[8]
                else None
            )

            self.altitude = (
                float(parts[9])
                if parts[9]
                else None
            )

        except:
            pass

    def _parse_rmc(self, parts):

        try:

            self.timestamp = parts[1]

            self.fix = parts[2] == "A"

            self.latitude = self._convert_coordinate(
                parts[3],
                parts[4]
            )

            self.longitude = self._convert_coordinate(
                parts[5],
                parts[6]
            )

            self.speed = (
                float(parts[7])
                if parts[7]
                else 0.0
            )

            self.course = (
                float(parts[8])
                if parts[8]
                else 0.0
            )

            self.date = parts[9]

        except:
            pass

    # -------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------

    def update(self):

        if not self.uart.any():
            return False

        line = self.uart.readline()

        if not line:
            return False

        try:

            line = line.decode("utf-8").strip()

        except:
            return False

        parts = line.split(",")

        if (
            line.startswith("$GPGGA")
            or
            line.startswith("$GNGGA")
        ):

            self._parse_gga(parts)

            return True

        if (
            line.startswith("$GPRMC")
            or
            line.startswith("$GNRMC")
        ):

            self._parse_rmc(parts)

            return True

        return False

    def has_fix(self):
        return self.fix

    def location(self):

        return (
            self.latitude,
            self.longitude
        )

    def datetime(self):

        if not self.date or not self.timestamp:
            return None

        try:

            d = self.date
            t = self.timestamp

            day = int(d[0:2])
            month = int(d[2:4])

            year = 2000 + int(d[4:6])

            hour = int(t[0:2])
            minute = int(t[2:4])

            second = int(float(t[4:]))

            return (
                year,
                month,
                day,
                hour,
                minute,
                second
            )

        except:
            return None

    def summary(self):

        return {
            "fix": self.fix,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "satellites": self.satellites,
            "hdop": self.hdop,
            "speed_knots": self.speed,
            "course": self.course,
            "datetime": self.datetime()
        }
