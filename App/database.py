"""
database.py — SQLite interface for pothole detection data.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "potholes.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS potholes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            latitude  REAL,
            longitude REAL,
            depth_mm  REAL    NOT NULL,
            width_mm  REAL    NOT NULL,
            cx        REAL,
            severity  TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def compute_severity(depth_mm: float) -> str:
    if depth_mm < 30:
        return "LOW"
    elif depth_mm < 60:
        return "MEDIUM"
    else:
        return "HIGH"


def insert_pothole(latitude, longitude, depth_mm, width_mm, cx) -> dict:
    severity  = compute_severity(depth_mm)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn   = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO potholes (timestamp, latitude, longitude, depth_mm, width_mm, cx, severity)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (timestamp, latitude, longitude, depth_mm, width_mm, cx, severity),
    )
    row_id = cursor.lastrowid
    conn.commit()

    row = conn.execute("SELECT * FROM potholes WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    return dict(row)


def get_all_potholes() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM potholes ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) FROM potholes").fetchone()[0]
    high  = conn.execute("SELECT COUNT(*) FROM potholes WHERE severity='HIGH'").fetchone()[0]
    med   = conn.execute("SELECT COUNT(*) FROM potholes WHERE severity='MEDIUM'").fetchone()[0]
    low   = conn.execute("SELECT COUNT(*) FROM potholes WHERE severity='LOW'").fetchone()[0]

    avg_depth = conn.execute("SELECT AVG(depth_mm) FROM potholes").fetchone()[0] or 0
    max_depth = conn.execute("SELECT MAX(depth_mm) FROM potholes").fetchone()[0] or 0
    max_width = conn.execute("SELECT MAX(width_mm) FROM potholes").fetchone()[0] or 0

    latest = conn.execute(
        "SELECT * FROM potholes ORDER BY id DESC LIMIT 1"
    ).fetchone()

    # Road Health Index = 100 - avg(severity_score)
    # LOW=1, MEDIUM=2, HIGH=3
    score_row = conn.execute(
        """
        SELECT AVG(CASE severity
                   WHEN 'LOW'    THEN 1
                   WHEN 'MEDIUM' THEN 2
                   WHEN 'HIGH'   THEN 3
                   ELSE 0 END)
        FROM potholes
        """
    ).fetchone()[0]
    road_health = round(100 - ((score_row or 0) / 3.0) * 100, 1) if total else 100.0

    conn.close()

    return {
        "total":       total,
        "high":        high,
        "medium":      med,
        "low":         low,
        "avg_depth":   round(avg_depth, 1),
        "max_depth":   round(max_depth, 1),
        "max_width":   round(max_width, 1),
        "road_health": road_health,
        "latest":      dict(latest) if latest else None,
    }


def get_timeline() -> list:
    """Return detections per minute for the last 60 minutes."""
    conn  = get_connection()
    rows  = conn.execute(
        """
        SELECT strftime('%Y-%m-%d %H:%M', timestamp) AS minute,
               COUNT(*) AS count
        FROM   potholes
        GROUP  BY minute
        ORDER  BY minute ASC
        LIMIT  60
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_depth_histogram() -> dict:
    """Bucket depths into 10 mm bands for a bar chart."""
    conn = get_connection()
    rows = conn.execute("SELECT depth_mm FROM potholes").fetchall()
    conn.close()

    buckets = {}
    for r in rows:
        band = int(r[0] // 10) * 10
        label = f"{band}–{band+10}"
        buckets[label] = buckets.get(label, 0) + 1
    return buckets
