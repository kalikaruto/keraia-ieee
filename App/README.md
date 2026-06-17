# RoadSense — Pothole Infrastructure Monitoring Dashboard
### IEEE AP-S Student Design Contest

A professional real-time dashboard for the LiDAR-based pothole detection system built on the ESP32.

---

## Architecture

```
ESP32 (AP mode, 192.168.4.1:5000)
        │  TCP, newline-delimited JSON
        ▼
  receiver.py  ──► SQLite (potholes.db)
        │
        ▼
    app.py (Flask, port 8080)
        │  HTTP + SSE
        ▼
  Browser Dashboard
```

---

## Quick Start

### 1. Install dependencies

```bash
cd pothole_dashboard
pip install -r requirements.txt
```

### 2. Run the dashboard

```bash
python app.py
```

Open **http://localhost:8080** in your browser.

### 3. Connect to ESP32

1. Connect your laptop to the ESP32 Wi-Fi access point:
   - **SSID:** `LidarNetwork`
   - **Password:** `lidar1234`
2. The receiver automatically connects to `192.168.4.1:5000`.
3. The **System Status** panel in the sidebar turns green when connected.

---

## Running WITHOUT hardware (demo / development)

Use the included simulator, which perfectly mirrors the ESP32 payload format.

**Step 1** — Edit `receiver.py`, change:
```python
ESP32_HOST = "192.168.4.1"
```
to:
```python
ESP32_HOST = "127.0.0.1"
```

**Step 2** — In terminal 1, start the simulator:
```bash
python simulator.py
```

**Step 3** — In terminal 2, start the dashboard:
```bash
python app.py
```

New potholes will appear every 2–4 seconds in the live feed.

---

## Project Structure

```
pothole_dashboard/
├── app.py            Flask application, REST API, SSE endpoint
├── receiver.py       TCP client, parses ESP32 JSON, stores to SQLite
├── database.py       SQLite interface, schema, analytics queries
├── simulator.py      Fake ESP32 for offline demo
├── requirements.txt
├── potholes.db       Created automatically on first run
├── templates/
│   └── index.html    Single-page dashboard
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── dashboard.js
```

---

## ESP32 Payload Format

The dashboard parses the exact payload emitted by `main.py`:

```json
{
  "n": 450,
  "baseline": 152.4,
  "potholes": [
    {
      "cx": 82.1,
      "depth": 64.5,
      "width": 118.3,
      "latitude": 25.3176,
      "longitude": 82.9739
    }
  ]
}
```

**No changes to the ESP32 firmware are required.**

---

## Severity Rules (applied on the laptop)

| Severity | Depth |
|----------|-------|
| LOW      | < 30 mm |
| MEDIUM   | 30 – 59.9 mm |
| HIGH     | ≥ 60 mm |

---

## Road Health Index

```
Road Health Index = 100 − (average_severity_score / 3) × 100
```

Severity scores: LOW = 1, MEDIUM = 2, HIGH = 3.
A perfect road scores 100; a road full of high-severity potholes approaches 0.

---

## Dashboard Screens

| Screen | Description |
|--------|-------------|
| **Live Monitor** | Real-time KPIs, latest detection card, activity feed |
| **Pothole Database** | Searchable/sortable table with severity filter |
| **Analytics** | Severity pie, depth histogram, detection timeline, aggregate stats |
| **Map View** | Leaflet map with colour-coded markers; click for depth/width/severity popup |

---

## CSV Export

Click **↓ Infrastructure Report** in the sidebar to download `infrastructure_report.csv`:

```
id, timestamp, latitude, longitude, depth_mm, width_mm, cx, severity
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Aggregate KPIs |
| GET | `/api/potholes` | All records (supports `?severity=HIGH&search=…`) |
| GET | `/api/analytics` | Stats + timeline + histogram |
| GET | `/api/status` | ESP32 / LiDAR / GPS connection state |
| GET | `/api/export/csv` | Download CSV report |
| POST | `/api/simulate` | Inject one random pothole (dev/demo) |
| GET | `/stream` | SSE event stream for real-time updates |

---

## Dependencies

| Library | Purpose |
|---------|---------|
| Flask | Web server |
| SQLite3 | Built into Python — no install needed |
| Leaflet 1.9.4 | Interactive map (CDN) |
| Chart.js 4.4 | Charts (CDN) |
| IBM Plex fonts | Typography (Google Fonts CDN) |

Everything runs **offline** except the CDN assets (fonts, Leaflet, Chart.js).
For a fully offline deployment, download those assets and serve them locally.
