import machine, time, struct, math

# ── Configuration defaults ─────────────────────────────────────────────
I2C_ID   = 0
SDA_PIN  = 21
SCL_PIN  = 22
I2C_FREQ = 100_000
BNO_ADDR = 0x4A

CH_CONTROL = 2
CH_REPORTS = 3

RPT_ACCEL    = 0x01
RPT_GYRO     = 0x02
RPT_MAG      = 0x03
RPT_ROTATION = 0x05
RPT_SET_FEATURE = 0xFD
RPT_TIMEBASE    = 0xFB

Q_ACCEL = 8
Q_GYRO  = 9
Q_MAG   = 4
Q_QUAT  = 14

def qf(raw, q):
    return raw * (2 ** -q)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def euler_from_quat(i, j, k, r):
    sinr_cosp = 2.0 * (r*i + j*k)
    cosr_cosp = 1.0 - 2.0 * (i*i + j*j)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (r*j - k*i)
    sinp = clamp(sinp, -1.0, 1.0)
    pitch = math.asin(sinp)

    siny_cosp = 2.0 * (r*k + i*j)
    cosy_cosp = 1.0 - 2.0 * (j*j + k*k)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

class SHTP:
    def __init__(self, i2c, addr):
        self._i2c = i2c
        self._addr = addr
        self._seq = [0]*6

    def write(self, ch, data):
        pkt = struct.pack("<HBB", len(data)+4, ch, self._seq[ch]&0xFF) + bytes(data)
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
        return raw[2], raw[4:length]

class BNO08x:
    def __init__(self):
        self._i2c = machine.I2C(
            I2C_ID,
            sda=machine.Pin(SDA_PIN, machine.Pin.OPEN_DRAIN, pull=machine.Pin.PULL_UP),
            scl=machine.Pin(SCL_PIN, machine.Pin.OPEN_DRAIN, pull=machine.Pin.PULL_UP),
            freq=I2C_FREQ
        )
        self._shtp = SHTP(self._i2c, BNO_ADDR)

        self.accel = (0.0,0.0,0.0)
        self.gyro  = (0.0,0.0,0.0)
        self.mag   = (0.0,0.0,0.0)
        self.quaternion = (0.0,0.0,0.0,1.0)

        self._init()

    def _init(self):
        if BNO_ADDR not in self._i2c.scan():
            raise RuntimeError("BNO085 not found")

        time.sleep_ms(300)

        for rid in (RPT_ACCEL, RPT_GYRO, RPT_MAG, RPT_ROTATION):
            self._enable(rid, 10000)
            time.sleep_ms(20)

    def _enable(self, report_id, interval_us):
        payload = struct.pack("<BBBHIiI",
            RPT_SET_FEATURE, report_id,
            0, 0,
            interval_us,
            0, 0)
        self._shtp.write(CH_CONTROL, payload)

    def _parse(self, payload):
        if not payload or len(payload) < 2:
            return

        rid = payload[0]

        # ── Raw sensors (need ≥ 10 bytes) ──
        if rid in (RPT_ACCEL, RPT_GYRO, RPT_MAG):
            if len(payload) < 10:
                return

            x, y, z = struct.unpack_from("<hhh", payload, 4)

            if rid == RPT_ACCEL:
                self.accel = (qf(x,Q_ACCEL), qf(y,Q_ACCEL), qf(z,Q_ACCEL))
            elif rid == RPT_GYRO:
                self.gyro  = (qf(x,Q_GYRO),  qf(y,Q_GYRO),  qf(z,Q_GYRO))
            elif rid == RPT_MAG:
                self.mag   = (qf(x,Q_MAG),   qf(y,Q_MAG),   qf(z,Q_MAG))

        # ── Rotation vector (need ≥ 14 bytes) ──
        elif rid == RPT_ROTATION:
            if len(payload) < 14:
                return

            qi, qj, qk, qr = struct.unpack_from("<hhhh", payload, 4)

            self.quaternion = (
                qf(qi,Q_QUAT),
                qf(qj,Q_QUAT),
                qf(qk,Q_QUAT),
                qf(qr,Q_QUAT)
            )

    def update(self, timeout_ms=50):
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            ch, payload = self._shtp.read()

            if ch is None or payload is None:
                break

            if ch != CH_REPORTS:
                continue

            # Handle timebase packets
            if payload and payload[0] == RPT_TIMEBASE:
                if len(payload) > 5:
                    self._parse(payload[5:])
                continue

            # Normal sensor reports
            self._parse(payload)
    @property
    def euler(self):
        i, j, k, r = self.quaternion
        return euler_from_quat(i, j, k, r)

