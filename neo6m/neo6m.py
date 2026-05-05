# neo6m.py
# MicroPython NEO-6M GPS library for Raspberry Pi Pico / RP2040
# Default: UART0 → TX=GP0, RX=GP1

from machine import UART, Pin

class NEO6M:
    def __init__(
        self,
        uart=None,
        uart_id=2,
        baudrate=9600,
        tx_pin=33,
        rx_pin=34,
        bits=8,
        parity=None,
        stop=1
    ):
        if uart is not None:
            self.uart = uart
        else:
            self.uart = UART(uart_id, baudrate)
            self.uart.init(
                baudrate,
                bits=bits,
                parity=parity,
                stop=stop,
                tx=Pin(tx_pin),
                rx=Pin(rx_pin)
            )

        self.buffer = ""
        self.latitude = None
        self.longitude = None
        self.valid_fix = False
        print("GPS UART:", uart_id, tx_pin, rx_pin)

    # ── Internal: Convert NMEA to decimal degrees ─────────────────────
    def _convert_to_decimal(self, raw, direction):
        if not raw or not direction:
            return None

        try:
            if direction in ("N", "S"):
                degrees = int(raw[0:2])
                minutes = float(raw[2:])
            else:
                degrees = int(raw[0:3])
                minutes = float(raw[3:])

            decimal = degrees + (minutes / 60)

            if direction in ("S", "W"):
                decimal = -decimal

            return decimal

        except:
            return None

    # ── Internal: Parse GPGLL sentence ────────────────────────────────
    def _parse_gpgll(self, line):
        try:
            parts = line.split(",")

            # Minimum valid GPGLL structure
            # $GPGLL,lat,N,lon,E,time,status,...
            if len(parts) < 7:
                return

            # A = valid fix
            if parts[6] != "A":
                self.valid_fix = False
                return

            lat = self._convert_to_decimal(parts[1], parts[2])
            lon = self._convert_to_decimal(parts[3], parts[4])

            if lat is not None and lon is not None:
                self.latitude = lat
                self.longitude = lon
                self.valid_fix = True

        except:
            self.valid_fix = False

    # ── Public: Update GPS buffer and parse ───────────────────────────
    def update(self, max_chars=256):
        count = 0

        while self.uart.any() and count < max_chars:
            try:
                char = self.uart.read(1).decode("utf-8", "ignore")
            except:
                return

            count += 1

            if char == "\n":
                line = self.buffer.strip()
                self.buffer = ""

                if line.startswith("$GPGLL") or line.startswith("$GNGLL"):
                    self._parse_gpgll(line)

            else:
                self.buffer += char


    # ── Public: Return location tuple ─────────────────────────────────
    def location(self):
        return self.latitude, self.longitude

    # ── Public: GPS fix state ─────────────────────────────────────────
    def has_fix(self):
        return self.valid_fix

    # ── Public: Reset stored state ────────────────────────────────────
    def reset(self):
        self.latitude = None
        self.longitude = None
        self.valid_fix = False
        self.buffer = ""


