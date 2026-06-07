"""
app.py — Flask web server for the Pothole Infrastructure Dashboard.
"""

import csv
import io
import json
import time

from flask import (
    Flask, Response, jsonify, render_template,
    request, stream_with_context
)

import database as db
import receiver

# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.before_request
def startup():
    db.init_db()
    receiver.start()


# ─────────────────────────────────────────────────────────────────────────────
# HTML views
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ─────────────────────────────────────────────────────────────────────────────
# REST API
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    return jsonify(db.get_stats())


@app.route("/api/potholes")
def api_potholes():
    rows     = db.get_all_potholes()
    severity = request.args.get("severity", "").upper()
    search   = request.args.get("search", "").lower()

    if severity in ("LOW", "MEDIUM", "HIGH"):
        rows = [r for r in rows if r["severity"] == severity]

    if search:
        rows = [
            r for r in rows
            if search in str(r.get("id", ""))
            or search in (r.get("timestamp") or "").lower()
            or search in (r.get("severity") or "").lower()
        ]

    return jsonify(rows)


@app.route("/api/analytics")
def api_analytics():
    return jsonify({
        "stats":     db.get_stats(),
        "timeline":  db.get_timeline(),
        "histogram": db.get_depth_histogram(),
    })


@app.route("/api/status")
def api_status():
    return jsonify({
        "connected":    receiver.state["connected"],
        "lidar_active": receiver.state["lidar_active"],
        "gps_active":   receiver.state["gps_active"],
    })


@app.route("/api/export/csv")
def export_csv():
    rows = db.get_all_potholes()
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "timestamp", "latitude", "longitude",
                    "depth_mm", "width_mm", "cx", "severity"],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    csv_data = output.getvalue()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=infrastructure_report.csv"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Server-Sent Events  — real-time push to browser
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/stream")
def stream():
    @stream_with_context
    def event_generator():
        # Send an initial heartbeat immediately
        yield "event: heartbeat\ndata: {}\n\n"
        last_heartbeat = time.time()

        while True:
            try:
                event = receiver.event_queue.get(timeout=1.0)
                payload = json.dumps(event)
                yield f"event: update\ndata: {payload}\n\n"
            except Exception:
                pass

            # Heartbeat every 5 s so browsers don't time out
            if time.time() - last_heartbeat >= 5:
                yield "event: heartbeat\ndata: {}\n\n"
                last_heartbeat = time.time()

    return Response(event_generator(), mimetype="text/event-stream",
                    headers={
                        "Cache-Control":   "no-cache",
                        "X-Accel-Buffering": "no",
                    })


# ─────────────────────────────────────────────────────────────────────────────
# Simulator endpoint — injects fake data for demos without ESP32
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/simulate", methods=["POST"])
def simulate():
    import random
    lat_base, lon_base = 25.3176, 82.9739
    depth = round(random.uniform(10, 100), 1)
    width = round(random.uniform(35, 200), 1)
    cx    = round(random.uniform(-80, 80), 1)
    lat   = lat_base + random.uniform(-0.002, 0.002)
    lon   = lon_base + random.uniform(-0.002, 0.002)

    row = db.insert_pothole(lat, lon, depth, width, cx)

    try:
        receiver.event_queue.put_nowait({"type": "new_potholes", "data": [row]})
    except Exception:
        pass

    return jsonify({"status": "ok", "inserted": row})


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db.init_db()
    receiver.start()
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
