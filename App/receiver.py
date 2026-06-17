"""
receiver.py — TCP listener that accepts JSON from the ESP32 and stores
each pothole in SQLite.  Runs in a background thread; pushes updates to
Flask-SSE subscribers via a simple in-process queue.
"""

import socket
import threading
import json
import queue
import time
from database import insert_pothole

# ── shared queue consumed by Flask /stream endpoint ──────────────────────────
event_queue: queue.Queue = queue.Queue(maxsize=200)

# ── connection state (readable from Flask routes) ─────────────────────────────
state = {
    "connected":   False,
    "lidar_active": False,
    "gps_active":  False,
    "last_payload": None,
}

# ── ESP32 address (matches main.py) ───────────────────────────────────────────
ESP32_HOST = "192.168.4.1"
# ESP32_HOST = "127.0.0.1"
ESP32_PORT = 5000

# How long (seconds) to wait before retrying a failed connection
RECONNECT_DELAY = 3


def _handle_payload(raw: str):
    """Parse a newline-delimited JSON string from the ESP32."""
    raw = raw.strip()
    if not raw:
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[receiver] JSON parse error: {exc}  raw={raw!r}")
        return

    state["last_payload"]  = data
    state["lidar_active"]  = True

    potholes = data.get("potholes", [])
    inserted = []

    for ph in potholes:
        lat  = ph.get("latitude")
        lon  = ph.get("longitude")
        depth = ph.get("depth", 0.0)
        width = ph.get("width", 0.0)
        cx    = ph.get("cx", 0.0)

        # GPS fix indicator — use None / sentinel values from ESP32 gracefully
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            state["gps_active"] = True
        else:
            lat = None
            lon = None

        row = insert_pothole(lat, lon, depth, width, cx)
        inserted.append(row)
        print(f"[receiver] stored pothole id={row['id']} depth={row['depth_mm']} sev={row['severity']}")

    if inserted:
        try:
            event_queue.put_nowait({"type": "new_potholes", "data": inserted})
        except queue.Full:
            pass  # drop event if nobody is consuming


def _receiver_loop():
    """
    Continuously connects to the ESP32 TCP server, reads newline-delimited
    JSON messages, and processes them.
    """
    buffer = ""

    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)

        try:
            print(f"[receiver] connecting to ESP32 at {ESP32_HOST}:{ESP32_PORT} …")
            sock.connect((ESP32_HOST, ESP32_PORT))
            state["connected"] = True
            print("[receiver] connected ✓")

            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    print("[receiver] ESP32 closed connection")
                    break

                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    _handle_payload(line)

        except (ConnectionRefusedError, socket.timeout, OSError) as exc:
            print(f"[receiver] connection error: {exc}")

        finally:
            state["connected"]   = False
            state["lidar_active"] = False
            sock.close()

        print(f"[receiver] retrying in {RECONNECT_DELAY}s …")
        time.sleep(RECONNECT_DELAY)


def start():
    """Spawn the receiver in a daemon thread."""
    t = threading.Thread(target=_receiver_loop, daemon=True)
    t.start()
    print("[receiver] background thread started")
