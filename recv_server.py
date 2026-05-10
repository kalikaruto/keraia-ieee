# recv_server.py — Laptop/server-side UDP listener for pothole events
# Run this on the machine whose IP you set as RECV_IP in combined_main.py
#
# Pothole event format: POTHOLE,<lat>,<lon>,<depth_mm>,<width_mm>

import socket

PORT = 5001

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
print(f"Listening for pothole events on UDP port {PORT}...")

try:
    while True:
        data, addr = sock.recvfrom(256)
        msg = data.decode("utf-8", errors="ignore").strip()

        if not msg.startswith("POTHOLE,"):
            print(f"[{addr[0]}] Unknown: {msg}")
            continue

        parts = msg.split(",")
        if len(parts) != 5:
            print(f"[{addr[0]}] Malformed: {msg}")
            continue

        _, lat, lon, depth, width = parts
        print(
            f"[POTHOLE] lat={lat}  lon={lon}  "
            f"depth={float(depth):.0f}mm  width={float(width):.0f}mm"
            f"  from {addr[0]}"
        )

except KeyboardInterrupt:
    print("Stopped.")
finally:
    sock.close()
