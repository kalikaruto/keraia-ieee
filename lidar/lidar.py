# rplidar.py
from machine import UART, Pin, PWM
import time

class RPLidar:
    def __init__(self, uart_id=2, baudrate=115200, tx=17, rx=16, motor_pin=18):
        self.uart = UART(uart_id, baudrate=baudrate, tx=tx, rx=rx)
        self.motor = PWM(Pin(motor_pin), freq=1000)
        self.buf = bytearray()
        self.idx = 0

    # ---------- motor ----------
    def start_motor(self, duty=1023):
        self.motor.duty(duty)

    def stop_motor(self):
        self.motor.duty(0)

    # ---------- commands ----------
    def start_scan(self):
        self.uart.write(b'\xA5\x20')
        time.sleep(0.1)
        self.uart.read(7)  # discard descriptor

    def stop(self):
        self.uart.write(b'\xA5\x25')
        time.sleep(0.05)

    # ---------- buffer ----------
    def _fill_buffer(self):
        data = self.uart.read()
        if data:
            self.buf.extend(data)

        # compact buffer periodically
        if self.idx > 512:
            self.buf = self.buf[self.idx:]
            self.idx = 0

    # ---------- packet sync ----------
    def _next_packet(self):
        while True:
            while len(self.buf) - self.idx < 5:
                self._fill_buffer()

            b0 = self.buf[self.idx]
            b1 = self.buf[self.idx + 1]

            start = b0 & 0x01
            inv   = (b0 >> 1) & 0x01

            # valid packet condition
            if start == (inv ^ 1):
                pkt = self.buf[self.idx:self.idx+5]
                self.idx += 5
                return pkt
            else:
                self.idx += 1

    # ---------- iterator ----------
    def iter_measurements(self):
        while True:
            pkt = self._next_packet()
            if not pkt:
                continue

            b0, b1, b2, b3, b4 = pkt

            quality = b0 >> 2
            strength = quality >> 2  # scale 0–63 → 0–15

            angle = ((b1 >> 1) | (b2 << 7)) / 64.0
            if angle >= 360:
                continue

            distance_mm = (b3 | (b4 << 8)) / 4.0
            if distance_mm == 0 or distance_mm > 6000:
                continue

            distance_cm = distance_mm / 10.0

            yield angle, distance_cm, strength

