"""
BNO08x I2C Driver for Raspberry Pi Pico (MicroPython)
======================================================
Features:
  • 9-DoF raw values  (accel m/s², gyro rad/s, mag µT)
  • Rotation Vector   → Roll / Pitch / Yaw (degrees)
  • Live calibration status with on-screen guidance
  • Calibration save/load to flash (cal_data.bin)

Wiring  (Pico GPIO → BNO08x breakout):
  3.3V → 3V3, CS, BT, RST
  GND  → GND, PS0, PS1, DI
  GP14 → SDA   (I2C1, needs 2.2k–4.7k pull-up)
  GP15 → SCL   (I2C1, needs 2.2k–4.7k pull-up)
"""

import machine, time, struct, math

# ── Configuration ─────────────────────────────────────────────────────────────
I2C_ID   = 1
SDA_PIN  = 14
SCL_PIN  = 15
NRST_PIN = None
I2C_FREQ = 400_000
BNO_ADDR = 0x4A        # DI/SA0 = GND → 0x4A,  3.3V → 0x4B

# ── SHTP channels ─────────────────────────────────────────────────────────────
CH_CONTROL = 2
CH_REPORTS = 3

# ── Report IDs ────────────────────────────────────────────────────────────────
RPT_ACCEL       = 0x01
RPT_GYRO        = 0x02
RPT_MAG         = 0x03
RPT_ROTATION    = 0x05   # Rotation Vector (quaternion, uses accel+gyro+mag)
RPT_SET_FEATURE = 0xFD
RPT_TIMEBASE    = 0xFB

# ── Q-points (datasheet §1.4.4) ───────────────────────────────────────────────
Q_ACCEL  = 8    # m/s²
Q_GYRO   = 9    # rad/s
Q_MAG    = 4    # µTesla
Q_QUAT   = 14   # quaternion components (rotation vector)

ACC_LABELS = {0: "Unreliable ✗", 1: "Low       ~",
              2: "Medium    ○", 3: "High      ✓"}

CAL_FILE = "cal_data.bin"


# ── Helpers ───────────────────────────────────────────────────────────────────

def qf(raw, q):
    return raw * (2 ** -q)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def euler_from_quat(i, j, k, r):
    """
    Convert unit quaternion (i,j,k,r) to roll/pitch/yaw in degrees.
    Convention: roll=X, pitch=Y, yaw=Z  (same as Android frame).
    """
    # Roll (rotation around X)
    sinr_cosp = 2.0 * (r*i + j*k)
    cosr_cosp = 1.0 - 2.0 * (i*i + j*j)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (rotation around Y)
    sinp = 2.0 * (r*j - k*i)
    sinp = clamp(sinp, -1.0, 1.0)
    pitch = math.asin(sinp)

    # Yaw (rotation around Z)
    siny_cosp = 2.0 * (r*k + i*j)
    cosy_cosp = 1.0 - 2.0 * (j*j + k*k)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


# ── SHTP framing ──────────────────────────────────────────────────────────────

class SHTP:
    def __init__(self, i2c, addr):
        self._i2c  = i2c
        self._addr = addr
        self._seq  = [0] * 6

    def write(self, ch, data):
        pkt = struct.pack("<HBB", len(data) + 4, ch, self._seq[ch] & 0xFF) + bytes(data)
        self._seq[ch] += 1
        self._i2c.writeto(self._addr, pkt)

    def read(self, n=128):
        try:
            raw = self._i2c.readfrom(self._addr, n)
        except OSError:
            return None, None
        if len(raw) < 4:
            return None, None
        length = struct.unpack_from("<H", raw, 0)[0] & 0x7FFF
        if length < 4 or length > len(raw):
            return None, None
        return raw[2], raw[4:length]   # (channel, payload)


# ── BNO08x Driver ─────────────────────────────────────────────────────────────

class BNO08x:

    def __init__(self, i2c_id=I2C_ID, sda=SDA_PIN, scl=SCL_PIN,
                 addr=BNO_ADDR, nrst=NRST_PIN, freq=I2C_FREQ):

        if nrst is not None:
            rst = machine.Pin(nrst, machine.Pin.OUT, value=1)
            time.sleep_ms(10); rst.value(0)
            time.sleep_ms(10); rst.value(1)
            time.sleep_ms(300)

        self._i2c  = machine.I2C(i2c_id,
                                  sda=machine.Pin(sda),
                                  scl=machine.Pin(scl),
                                  freq=freq)
        self._shtp = SHTP(self._i2c, addr)
        self._addr = addr

        # Raw sensor data
        self.accel      = (0.0, 0.0, 0.0)   # m/s²
        self.gyro       = (0.0, 0.0, 0.0)   # rad/s
        self.mag        = (0.0, 0.0, 0.0)   # µT
        self.quaternion = (0.0, 0.0, 0.0, 1.0)  # i, j, k, real

        # Accuracy (0–3)
        self.accel_acc = 0
        self.gyro_acc  = 0
        self.mag_acc   = 0
        self.rot_acc   = 0

        self._init()

    # ── Boot ──────────────────────────────────────────────────────────────────

    def _init(self):
        found = self._i2c.scan()
        if self._addr not in found:
            raise RuntimeError(
                f"BNO08x not found at {hex(self._addr)}. "
                f"Bus has: {[hex(d) for d in found]}\n"
                "Check: CS=3.3V, BT=3.3V, RST=3.3V, PS0=GND, PS1=GND, DI=GND"
            )
        print(f"  BNO08x at {hex(self._addr)}  ✓")
        print("  Waiting for boot …", end="")
        deadline = time.ticks_add(time.ticks_ms(), 400)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            self._shtp.read(); time.sleep_ms(10)
        print(" ok")

        # Enable sensors at 100 Hz
        for rid in (RPT_ACCEL, RPT_GYRO, RPT_MAG, RPT_ROTATION):
            self._enable(rid, 10_000)   # 10 000 µs = 100 Hz
            time.sleep_ms(20)
        print("  Sensors enabled @ 100 Hz  ✓\n")

    def _enable(self, report_id, interval_us=10_000):
        """Set Feature Command — datasheet §1.4.5 Figure 1-33."""
        payload = struct.pack("<BBBHIiI",
            RPT_SET_FEATURE, report_id,
            0, 0,            # flags, sensitivity
            interval_us,     # report interval
            0, 0)            # batch interval, sensor config
        self._shtp.write(CH_CONTROL, payload)

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse(self, payload):
        if not payload or len(payload) < 2:
            return
        rid = payload[0]

        # ── Raw motion sensors (10-byte reports) ──
        if rid in (RPT_ACCEL, RPT_GYRO, RPT_MAG):
            if len(payload) < 10:
                return
            acc = payload[2] & 0x03
            x, y, z = struct.unpack_from("<hhh", payload, 4)
            if rid == RPT_ACCEL:
                self.accel      = (qf(x,Q_ACCEL), qf(y,Q_ACCEL), qf(z,Q_ACCEL))
                self.accel_acc  = acc
            elif rid == RPT_GYRO:
                self.gyro       = (qf(x,Q_GYRO),  qf(y,Q_GYRO),  qf(z,Q_GYRO))
                self.gyro_acc   = acc
            elif rid == RPT_MAG:
                self.mag        = (qf(x,Q_MAG),   qf(y,Q_MAG),   qf(z,Q_MAG))
                self.mag_acc    = acc

        # ── Rotation Vector (quaternion, 14-byte report) ──
        elif rid == RPT_ROTATION:
            if len(payload) < 14:
                return
            acc = payload[2] & 0x03
            # bytes 4-11: i, j, k, real  (each int16, Q14)
            qi, qj, qk, qr = struct.unpack_from("<hhhh", payload, 4)
            self.quaternion = (qf(qi,Q_QUAT), qf(qj,Q_QUAT),
                               qf(qk,Q_QUAT), qf(qr,Q_QUAT))
            self.rot_acc    = acc

    def update(self, timeout_ms=100):
        """Poll all pending SHTP packets. Call before reading values."""
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            ch, payload = self._shtp.read()
            if ch is None or not payload:
                break
            if ch == CH_REPORTS:
                if payload[0] == RPT_TIMEBASE and len(payload) > 5:
                    self._parse(payload[5:])
                else:
                    self._parse(payload)

    # ── Euler angles ──────────────────────────────────────────────────────────

    @property
    def euler(self):
        """(roll, pitch, yaw) in degrees, derived from the Rotation Vector."""
        i, j, k, r = self.quaternion
        return euler_from_quat(i, j, k, r)

    # ── Calibration save / load ───────────────────────────────────────────────

    def save_calibration(self, filename=CAL_FILE):
        """
        Save current accuracy flags to a file so you know calibration was good.
        For full calibration persistence the BNO08x has an internal FRS record
        that the chip manages automatically across power cycles.
        This file just logs the last known accuracy levels.
        """
        with open(filename, "wb") as f:
            f.write(bytes([self.accel_acc, self.gyro_acc,
                           self.mag_acc,   self.rot_acc]))
        print(f"  Calibration state saved to {filename}")

    def load_calibration(self, filename=CAL_FILE):
        try:
            with open(filename, "rb") as f:
                data = f.read(4)
            print(f"  Last saved calibration: "
                  f"accel={data[0]} gyro={data[1]} "
                  f"mag={data[2]} rot={data[3]}")
        except OSError:
            print("  No saved calibration found.")


# ── Calibration guidance ──────────────────────────────────────────────────────

def calibration_guide(bno: BNO08x):
    """
    Interactive calibration routine with live feedback.
    Walk the user through each sensor until all reach accuracy ≥ 2 (Medium).
    Based on datasheet §3.2, Figure 3-2.
    """
    print("\n" + "=" * 52)
    print("  CALIBRATION GUIDE  (Ctrl-C to skip)")
    print("=" * 52)
    print("Target: all sensors reach Medium (○) or High (✓)\n")

    steps = [
        ("GYROSCOPE",
         "Place sensor FLAT and STILL on a stable surface.\n"
         "  Keep it motionless for ~3 seconds.",
         lambda b: b.gyro_acc),
        ("ACCELEROMETER",
         "Tilt the sensor into 4–6 different orientations.\n"
         "  Hold each position for ~1 second.\n"
         "  Example: flat, on each of 4 edges, upside-down.",
         lambda b: b.accel_acc),
        ("MAGNETOMETER",
         "Move sensor in a slow figure-8 through the air.\n"
         "  Rotate through all 3 axes over ~10 seconds.\n"
         "  Keep away from metal objects & electronics.",
         lambda b: b.mag_acc),
    ]

    for name, instruction, acc_fn in steps:
        print(f"─── {name} ───")
        print(f"  {instruction}\n")
        try:
            timeout = time.ticks_add(time.ticks_ms(), 15_000)  # 15 s max
            while time.ticks_diff(timeout, time.ticks_ms()) > 0:
                bno.update(50)
                lvl = acc_fn(bno)
                bar = "█" * lvl + "░" * (3 - lvl)
                print(f"  [{bar}] {ACC_LABELS[lvl]}    \r", end="")
                if lvl >= 2:
                    print(f"\n  {name} calibrated!  ✓\n")
                    break
                time.sleep_ms(200)
            else:
                print(f"\n  Timed out — continuing anyway.\n")
        except KeyboardInterrupt:
            print("\n  Skipped.\n")
            break

    bno.save_calibration()
    print("Calibration complete.\n")


# ── Main display loop ─────────────────────────────────────────────────────────

def main():
    print("BNO08x 9-DoF + Euler angles  –  Pico / MicroPython")
    print("=" * 52)

    bno = BNO08x()
    bno.load_calibration()

    # Offer calibration if any sensor is unreliable
    bno.update(200)
    if min(bno.accel_acc, bno.gyro_acc, bno.mag_acc) == 0:
        print("\nSome sensors are Unreliable — running calibration guide.")
        print("(Press Ctrl-C at any step to skip it)\n")
        try:
            calibration_guide(bno)
        except KeyboardInterrupt:
            print("Calibration skipped.\n")

    print("Reading  (Ctrl-C to stop)\n")
    print(f"{'Sensor':<14} {'X':>9} {'Y':>9} {'Z':>9}  Status")
    print("─" * 52)

    while True:
        bno.update(100)

        ax, ay, az = bno.accel
        gx, gy, gz = bno.gyro
        mx, my, mz = bno.mag
        roll, pitch, yaw = bno.euler

        # All accuracy flags
        aa = ACC_LABELS[bno.accel_acc]
        ga = ACC_LABELS[bno.gyro_acc]
        ma = ACC_LABELS[bno.mag_acc]
        ra = ACC_LABELS[bno.rot_acc]

        print(f"Accel m/s²    {ax:+8.3f}  {ay:+8.3f}  {az:+8.3f}  {aa}")
        print(f"Gyro  rad/s   {gx:+8.3f}  {gy:+8.3f}  {gz:+8.3f}  {ga}")
        print(f"Mag   µT      {mx:+8.3f}  {my:+8.3f}  {mz:+8.3f}  {ma}")
        print(f"Euler deg   Roll={roll:+7.2f}  Pitch={pitch:+7.2f}  Yaw={yaw:+7.2f}  {ra}")
        print("─" * 52)
        time.sleep_ms(200)


if __name__ == "__main__":
    main()
