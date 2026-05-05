import socket
import numpy as np
import matplotlib.pyplot as plt
from collections import deque

PICO_IP = "10.1.16.231"
PORT = 5000

# --- Connect to Pico ---
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((PICO_IP, PORT))
sock.settimeout(5.0)
print(f"Connected to Pico at {PICO_IP}:{PORT}")

recv_buffer = ""


def receive_scan():
    global recv_buffer
    try:
        chunk = sock.recv(4096).decode(errors='ignore')
        recv_buffer += chunk
    except socket.timeout:
        return None
    except Exception as e:
        print(f"Recv error: {e}")
        return None

    if "---\n" not in recv_buffer:
        return None

    parts = recv_buffer.split("---\n", 1)
    scan_str = parts[0]
    recv_buffer = parts[1]

    points = []
    for line in scan_str.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            q, a, d = line.split(",")
            points.append((float(q), float(a), float(d)))
        except:
            continue
    return points if points else None


def process_scan(scan):
    x_coords, y_coords = [], []
    for (_, angle, distance) in scan:
        if angle > 180:
            angle -= 360
        if -45 <= angle <= 45:
            radians = np.radians(angle)
            y_val = -distance * np.cos(radians)  # flipped
            x_val = distance * np.sin(radians)
            x_coords.append(x_val)
            y_coords.append(y_val)
    return np.array(x_coords), np.array(y_coords)


def detect_potholes(x_coords, y_coords, threshold_mm=50, min_width_mm=30):
    if len(y_coords) < 5:
        return []

    baseline = np.median(y_coords)
    potholes = []
    in_hole = False
    hole_x = []
    hole_y = []

    order = np.argsort(x_coords)
    xs = x_coords[order]
    ys = y_coords[order]

    for xi, yi in zip(xs, ys):
        if yi < baseline - threshold_mm:  # pothole = less negative than baseline
            in_hole = True
            hole_x.append(xi)
            hole_y.append(yi)
        else:
            if in_hole:
                width = max(hole_x) - min(hole_x)
                if width >= min_width_mm:
                    potholes.append({
                        "center_x": np.mean(hole_x),
                        "depth_mm": baseline - np.mean(hole_y),
                        "width_mm": width,
                        "baseline_mm": baseline,
                    })
                hole_x, hole_y = [], []
                in_hole = False

    return potholes


# --- Plot Setup ---
plt.ion()
fig, (ax_main, ax_depth) = plt.subplots(2, 1, figsize=(12, 8))
fig.suptitle("RPLidar — Live Pothole Detection via WiFi", fontsize=13)

# Top plot
scatter = ax_main.scatter([], [], c=[], cmap='RdYlGn', s=4, vmin=-3000, vmax=0)
pothole_scatter = ax_main.scatter([], [], c='red', s=80, marker='X', zorder=5)
baseline_line, = ax_main.plot([], [], 'b--', linewidth=1)
ax_main.set_xlim(-1500, 1500)
ax_main.set_ylim(-3000, 0)          # flipped: 0 at top, -3000 at bottom
ax_main.set_xlabel("Width (mm)")
ax_main.set_ylabel("Depth (mm)")
ax_main.set_title("Surface Map — 90° Cone")
ax_main.grid(True)
ax_main.legend()

# Bottom plot
depth_line, = ax_depth.plot([], [], 'g-', linewidth=1, label='Surface')
ax_depth.axhline(y=0, color='blue', linestyle='--', linewidth=1, label='Baseline')
pothole_fills = []
ax_depth.set_xlim(-1500, 1500)
ax_depth.set_ylim(-500, 500)
ax_depth.set_xlabel("Width (mm)")
ax_depth.set_ylabel("Depth offset from baseline (mm)")
ax_depth.set_title("Depth Profile  [dip = pothole, bump = object]")
ax_depth.grid(True)
ax_depth.legend()

# status_text = ax_main.text(
#     0.02, 0.05, '', transform=ax_main.transAxes,
#     fontsize=9, verticalalignment='bottom',
#     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
# )

print("Receiving scans... (Ctrl+C to stop)")

try:
    while True:
        scan = receive_scan()
        if scan is None:
            plt.pause(0.01)
            continue

        x_coords, y_coords = process_scan(scan)
        if len(x_coords) == 0:
            plt.pause(0.01)
            continue

        potholes = detect_potholes(x_coords, y_coords)
        baseline = np.median(y_coords)
        depth_offsets = y_coords - baseline

        # Update scatter
        scatter.set_offsets(np.c_[x_coords, y_coords])
        scatter.set_array(y_coords)

        # Update pothole markers
        if potholes:
            ph_x = [p["center_x"] for p in potholes]
            ph_y = [baseline - p["depth_mm"] for p in potholes]
            pothole_scatter.set_offsets(np.c_[ph_x, ph_y])
        else:
            pothole_scatter.set_offsets(np.empty((0, 2)))

        # Update baseline
        baseline_line.set_data([-1500, 1500], [baseline, baseline])

        # Update depth profile
        order = np.argsort(x_coords)
        depth_line.set_data(x_coords[order], depth_offsets[order])

        # Remove old pothole shading
        for pf in pothole_fills:
            pf.remove()
        pothole_fills.clear()

        for p in potholes:
            half_w = p["width_mm"] / 2
            cx = p["center_x"]
            pf = ax_depth.axvspan(
                cx - half_w, cx + half_w,
                alpha=0.3, color='red', label='_nolegend_'
            )
            pothole_fills.append(pf)

        # Status
        status = f"Points: {len(x_coords)}  |  Potholes: {len(potholes)}  |  Baseline: {baseline:.0f} mm"
        if potholes:
            biggest = max(potholes, key=lambda p: p["depth_mm"])
            status += f"\nLargest — depth: {biggest['depth_mm']:.0f} mm  width: {biggest['width_mm']:.0f} mm"
        # status_text.set_text(status)

        fig.canvas.draw()
        fig.canvas.flush_events()

except KeyboardInterrupt:
    print("Stopped.")
finally:
    sock.close()
    print("Socket closed.")
