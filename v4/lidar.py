"""
rplidar.py — MicroPython RPLidar library (no WiFi)
===================================================
Usage:
    from machine import UART, Pin
    from rplidar import RPLidar

    uart = UART(2, baudrate=115200, tx=17, rx=16)
    lidar = RPLidar(uart)

    for scan in lidar.iter_scans():
        for (quality, angle, distance) in scan:
            print(quality, angle, distance)

    lidar.stop()
    lidar.disconnect()
"""

import time

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------
_SYNC_BYTE      = 0xA5
_SYNC_BYTE2     = 0x5A
_CMD_STOP       = 0x25
_CMD_RESET      = 0x40
_CMD_SCAN       = 0x20
_CMD_FORCE_SCAN = 0x21
_CMD_GET_INFO   = 0x50
_CMD_GET_HEALTH = 0x52

_DESCRIPTOR_LEN = 7
_INFO_LEN       = 20
_HEALTH_LEN     = 3
_SCAN_LEN       = 5

_STATUS = {0: 'Good', 1: 'Warning', 2: 'Error'}


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------
class RPLidarException(Exception):
    pass


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class RPLidar:
    """
    Parameters
    ----------
    port : UART
        A pre-configured MicroPython UART instance.
    timeout : float
        Read timeout in seconds (default 1.0).
    """

    def __init__(self, port, timeout=1.0):
        self._uart       = port
        self._timeout_ms = int(timeout * 1000)
        self._scanning   = False

    # ------------------------------------------------------------------
    # Public API  (rplidar-roboticia compatible)
    # ------------------------------------------------------------------

    def disconnect(self):
        """Stop scanning and release resources."""
        self.stop()
        self._uart = None

    def reset(self):
        """Hard-reset the sensor (~2 s recovery time)."""
        self._send(bytes([_SYNC_BYTE, _CMD_RESET]))
        time.sleep_ms(2000)
        self._flush(500)
        self._scanning = False

    def get_info(self):
        """
        Returns
        -------
        dict: model, firmware, hardware, serialnumber
        """
        self._send(bytes([_SYNC_BYTE, _CMD_GET_INFO]))
        try:
            self._read_descriptor(500)
            raw = self._read_bytes(_INFO_LEN, 500)
        except RPLidarException:
            return {'model': 0, 'firmware': (0, 0),
                    'hardware': 0, 'serialnumber': '0' * 32}
        return {
            'model':        raw[0],
            'firmware':     (raw[2], raw[1]),
            'hardware':     raw[3],
            'serialnumber': ''.join('{:02X}'.format(b) for b in raw[4:20]),
        }

    def get_health(self):
        """
        Returns
        -------
        (status : str, error_code : int)
            status is 'Good', 'Warning', or 'Error'.
        """
        self._send(bytes([_SYNC_BYTE, _CMD_GET_HEALTH]))
        try:
            self._read_descriptor(500)
            raw = self._read_bytes(_HEALTH_LEN, 500)
        except RPLidarException:
            return ('Good', 0)
        return (_STATUS.get(raw[0], 'Error'), raw[1] | (raw[2] << 8))

    def start(self, scan='normal'):
        """
        Start the scan.

        Parameters
        ----------
        scan : str
            'normal' (default) or 'force'.
        """
        cmd = _CMD_FORCE_SCAN if scan == 'force' else _CMD_SCAN
        self._send(bytes([_SYNC_BYTE, cmd]))
        self._read_descriptor(2000)
        self._scanning = True

    def stop(self):
        """Stop scanning and put sensor into idle state."""
        if not self._scanning:
            return
        self._send(bytes([_SYNC_BYTE, _CMD_STOP]))
        time.sleep_ms(150)
        self._flush(200)
        self._scanning = False

    def iter_measurements(self, max_buf_meas=500):
        """
        Generator — yields one measurement at a time.

        Yields
        ------
        (new_scan : bool, quality : int, angle : float, distance : float)
        """
        if not self._scanning:
            self.start()

        buf = bytearray()

        while True:
            chunk = self._uart.read(128)
            if chunk:
                buf += chunk

            if len(buf) > max_buf_meas * _SCAN_LEN:
                buf = bytearray()
                continue

            while len(buf) >= _SCAN_LEN:
                result = _parse(buf[:_SCAN_LEN])
                if result is not None:
                    buf = buf[_SCAN_LEN:]
                    yield result
                else:
                    buf = buf[1:]

    def iter_scans(self, max_buf_meas=500, min_len=5):
        """
        Generator — yields one complete 360 degree scan at a time.

        Yields
        ------
        list of (quality : int, angle : float, distance : float)

        Parameters
        ----------
        max_buf_meas : int
            Drop buffer if it exceeds this many un-parsed measurements.
        min_len : int
            Minimum measurements required before yielding a scan.
        """
        scan = []
        for new_scan, quality, angle, distance in \
                self.iter_measurements(max_buf_meas):
            if new_scan and len(scan) >= min_len:
                yield scan
                scan = []
            if distance > 0:
                scan.append((quality, angle, distance))

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.disconnect()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _send(self, data):
        self._uart.write(data)

    def _flush(self, duration_ms=200):
        deadline = time.ticks_add(time.ticks_ms(), duration_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if not self._uart.read(128):
                time.sleep_ms(10)

    def _read_bytes(self, n, timeout_ms=None):
        timeout_ms = timeout_ms or self._timeout_ms
        buf = bytearray()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while len(buf) < n:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise RPLidarException(
                    'Read timeout ({}/{} bytes)'.format(len(buf), n))
            chunk = self._uart.read(n - len(buf))
            if chunk:
                buf += chunk
            else:
                time.sleep_ms(5)
        return bytes(buf)

    def _read_descriptor(self, timeout_ms=None):
        timeout_ms = timeout_ms or self._timeout_ms
        buf = bytearray()
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            b = self._uart.read(1)
            if not b:
                time.sleep_ms(5)
                continue
            buf += b
            if len(buf) > _DESCRIPTOR_LEN:
                buf = buf[-_DESCRIPTOR_LEN:]
            if (len(buf) == _DESCRIPTOR_LEN
                    and buf[0] == _SYNC_BYTE
                    and buf[1] == _SYNC_BYTE2):
                return buf[6]
        raise RPLidarException('Descriptor timeout')


# ---------------------------------------------------------------------------
# Module-level packet parser
# ---------------------------------------------------------------------------
def _parse(raw):
    """
    Parse a 5-byte scan packet.
    Returns (new_scan, quality, angle, distance) or None if invalid.
    """
    s     = raw[0] & 0x01
    s_bar = (raw[0] >> 1) & 0x01
    if s == s_bar:
        return None
    if not (raw[1] & 0x01):
        return None
    quality  = raw[0] >> 2
    angle    = (((raw[1] >> 1) | (raw[2] << 7)) & 0x7FFF) / 64.0
    distance = (raw[3] | (raw[4] << 8)) / 4.0
    return bool(s), quality, angle, distance
