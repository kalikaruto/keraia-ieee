#!/usr/bin/env python3
"""
simulator.py — Simulates the ESP32 TCP server so you can run the dashboard
               without physical hardware.

Usage:
    python simulator.py

The simulator:
  * Listens on 127.0.0.1:5000 (same port as ESP32 firmware)
  * Accepts one dashboard connection
  * Sends randomised JSON payloads every 2–4 seconds
  * Mirrors the exact payload format from main.py / build_payload()

Point receiver.py at 127.0.0.1 instead of 192.168.4.1 when using this.
(Edit ESP32_HOST in receiver.py before starting the dashboard.)
"""

import json
import math
import random
import socket
import time

HOST = "127.0.0.1"
PORT = 5000

# Varanasi area — same as the project coordinates
BASE_LAT = 25.3176
BASE_LON = 82.9739


def random_pothole():
    depth = round(random.uniform(10, 110), 1)
    width = round(random.uniform(35, 220), 1)
    cx    = round(random.uniform(-90, 90), 1)
    lat   = round(BASE_LAT + random.uniform(-0.003, 0.003), 6)
    lon   = round(BASE_LON + random.uniform(-0.003, 0.003), 6)
    return {"cx": cx, "depth": depth, "width": width,
            "latitude": lat, "longitude": lon}


def build_payload():
    n_points = random.randint(80, 200)
    baseline = round(random.uniform(140, 165), 1)
    n_holes  = random.choices([0, 1, 2, 3], weights=[3, 5, 2, 1])[0]
    potholes = [random_pothole() for _ in range(n_holes)]
    return json.dumps({
        "n":        n_points,
        "baseline": baseline,
        "potholes": potholes,
    }) + "\n"


def run():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print(f"[sim] listening on {HOST}:{PORT} — waiting for dashboard …")

    while True:
        conn, addr = srv.accept()
        print(f"[sim] dashboard connected from {addr}")
        try:
            while True:
                payload = build_payload()
                conn.sendall(payload.encode())
                n = json.loads(payload)["potholes"]
                print(f"[sim] sent {len(n)} pothole(s)")
                time.sleep(random.uniform(2, 4))
        except (BrokenPipeError, ConnectionResetError, OSError):
            print("[sim] dashboard disconnected, waiting for reconnect …")
            conn.close()


if __name__ == "__main__":
    run()
