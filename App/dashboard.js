/* ─────────────────────────────────────────────────────────────────
   RoadSense Dashboard — dashboard.js
   ───────────────────────────────────────────────────────────────── */

// ── State ──────────────────────────────────────────────────────────
let allRows    = [];
let sortCol    = "id";
let sortAsc    = false;
let sevFilter  = "";
let chartSev   = null;
let chartDepth = null;
let chartTime  = null;
let map        = null;
let markers    = [];

// ── Navigation ─────────────────────────────────────────────────────
document.querySelectorAll(".nav-item").forEach(el => {
  el.addEventListener("click", e => {
    e.preventDefault();
    const screen = el.dataset.screen;

    document.querySelectorAll(".nav-item").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".screen").forEach(x => x.classList.remove("active"));

    el.classList.add("active");
    document.getElementById(`screen-${screen}`).classList.add("active");

    if (screen === "analytics") refreshAnalytics();
    if (screen === "map") { initMap(); refreshMap(); }
    if (screen === "database") refreshDatabase();
  });
});

// ── Server-Sent Events ─────────────────────────────────────────────
function connectSSE() {
  const es = new EventSource("/stream");

  es.addEventListener("update", e => {
    const evt = JSON.parse(e.data);
    if (evt.type === "new_potholes") {
      evt.data.forEach(ph => addFeedItem(ph));
      refreshStats();
      // If on analytics / database / map, update those too
      const active = document.querySelector(".screen.active").id;
      if (active === "screen-analytics") refreshAnalytics();
      if (active === "screen-database")  refreshDatabase();
      if (active === "screen-map")       refreshMap();
    }
  });

  es.addEventListener("heartbeat", () => {
    pollStatus();
  });

  es.onerror = () => {
    setTimeout(connectSSE, 3000);
    es.close();
  };
}

// ── Status polling ─────────────────────────────────────────────────
function pollStatus() {
  fetch("/api/status")
    .then(r => r.json())
    .then(s => {
      setDot("dot-esp32", "val-esp32", s.connected,    "Connected", "Offline");
      setDot("dot-lidar", "val-lidar", s.lidar_active, "Active",   "Idle");
      setDot("dot-gps",   "val-gps",   s.gps_active,   "Active",   "No Fix");
    })
    .catch(() => {});
}

function setDot(dotId, valId, on, onLabel, offLabel) {
  const dot = document.getElementById(dotId);
  const val = document.getElementById(valId);
  dot.className = "status-dot " + (on ? "on" : "off");
  val.textContent = on ? onLabel : offLabel;
}

// ── Stats / KPIs ───────────────────────────────────────────────────
function refreshStats() {
  fetch("/api/stats")
    .then(r => r.json())
    .then(s => {
      setText("kpi-total",  s.total);
      setText("kpi-high",   s.high);
      setText("kpi-medium", s.medium);
      setText("kpi-low",    s.low);

      if (s.latest) renderLatest(s.latest);
    })
    .catch(() => {});
}

function renderLatest(ph) {
  document.getElementById("latest-empty").classList.add("hidden");
  document.getElementById("latest-content").classList.remove("hidden");

  const badge = document.getElementById("latest-sev-badge");
  badge.textContent = ph.severity;
  badge.className = "latest-sev sev-" + ph.severity;

  setText("latest-depth", ph.depth_mm.toFixed(1));
  setText("latest-width", ph.width_mm.toFixed(1));
  setText("latest-lat",   ph.latitude  != null ? ph.latitude.toFixed(5)  : "N/A");
  setText("latest-lon",   ph.longitude != null ? ph.longitude.toFixed(5) : "N/A");
  setText("latest-ts",    ph.timestamp);
}

// ── Activity Feed ──────────────────────────────────────────────────
function addFeedItem(ph) {
  const feed = document.getElementById("activity-feed");

  // Remove empty state on first item
  const empty = feed.querySelector(".empty-state");
  if (empty) empty.remove();

  const div = document.createElement("div");
  div.className = `feed-item ${ph.severity}`;

  const ts = ph.timestamp ? ph.timestamp.split(" ")[1] : "—";
  div.innerHTML = `
    <span class="feed-sev ${ph.severity}">${ph.severity}</span>
    <span class="feed-info">${ph.depth_mm.toFixed(1)} mm · ${ph.width_mm.toFixed(1)} mm</span>
    <span class="feed-ts">${ts}</span>
  `;

  feed.insertBefore(div, feed.firstChild);

  // Cap feed length
  while (feed.children.length > 50) {
    feed.removeChild(feed.lastChild);
  }
}

// ── Database screen ────────────────────────────────────────────────
function refreshDatabase() {
  fetch("/api/potholes")
    .then(r => r.json())
    .then(rows => {
      allRows = rows;
      renderTable();
    })
    .catch(() => {});
}

function renderTable() {
  let rows = [...allRows];

  // Severity filter
  if (sevFilter) rows = rows.filter(r => r.severity === sevFilter);

  // Search
  const q = document.getElementById("db-search").value.trim().toLowerCase();
  if (q) {
    rows = rows.filter(r =>
      String(r.id).includes(q) ||
      (r.timestamp || "").toLowerCase().includes(q) ||
      (r.severity  || "").toLowerCase().includes(q)
    );
  }

  // Sort
  rows.sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (va == null) va = "";
    if (vb == null) vb = "";
    if (typeof va === "string") return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  });

  const tbody = document.getElementById("db-tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-state">No records match</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.id}</td>
      <td>${r.timestamp || "—"}</td>
      <td>${(+r.depth_mm).toFixed(1)}</td>
      <td>${(+r.width_mm).toFixed(1)}</td>
      <td><span class="sev-badge sev-${r.severity}">${r.severity}</span></td>
      <td>${r.latitude  != null ? (+r.latitude).toFixed(5)  : "—"}</td>
      <td>${r.longitude != null ? (+r.longitude).toFixed(5) : "—"}</td>
      <td>${r.cx != null ? (+r.cx).toFixed(1) : "—"}</td>
    </tr>
  `).join("");
}

function sortTable(col) {
  if (sortCol === col) sortAsc = !sortAsc;
  else { sortCol = col; sortAsc = false; }
  renderTable();
}

function filterTable() { renderTable(); }

function setSevFilter(btn, sev) {
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  sevFilter = sev;
  renderTable();
}

// ── Analytics ──────────────────────────────────────────────────────
function refreshAnalytics() {
  fetch("/api/analytics")
    .then(r => r.json())
    .then(d => {
      const s = d.stats;
      setText("an-avg-depth", s.avg_depth);
      setText("an-max-depth", s.max_depth);
      setText("an-max-width", s.max_width);
      setText("an-health",    s.road_health);

      renderSeverityChart(s);
      renderDepthChart(d.histogram);
      renderTimelineChart(d.timeline);
    })
    .catch(() => {});
}

function renderSeverityChart(s) {
  const ctx = document.getElementById("chart-severity").getContext("2d");
  if (chartSev) chartSev.destroy();

  chartSev = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["High", "Medium", "Low"],
      datasets: [{
        data: [s.high, s.medium, s.low],
        backgroundColor: ["#d43f3f", "#d47a10", "#1a8a4a"],
        borderWidth: 2,
        borderColor: "#ffffff",
        hoverOffset: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "62%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { font: { family: "'IBM Plex Mono'", size: 11 }, padding: 16 }
        }
      }
    }
  });
}

function renderDepthChart(histogram) {
  const ctx = document.getElementById("chart-depth").getContext("2d");
  if (chartDepth) chartDepth.destroy();

  const labels = Object.keys(histogram).sort((a, b) => {
    const getStart = s => parseInt(s.split("–")[0]);
    return getStart(a) - getStart(b);
  });
  const values = labels.map(l => histogram[l]);

  chartDepth = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Count",
        data: values,
        backgroundColor: "#1d5af5",
        borderRadius: 3,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { font: { family: "'IBM Plex Mono'", size: 10 } },
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
          ticks: { font: { family: "'IBM Plex Mono'", size: 10 }, precision: 0 },
          grid: { color: "#eee" },
        }
      }
    }
  });
}

function renderTimelineChart(timeline) {
  const ctx = document.getElementById("chart-timeline").getContext("2d");
  if (chartTime) chartTime.destroy();

  const labels = timeline.map(t => t.minute);
  const values = timeline.map(t => t.count);

  chartTime = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Detections",
        data: values,
        borderColor: "#1d5af5",
        backgroundColor: "rgba(29,90,245,0.07)",
        tension: 0.3,
        fill: true,
        pointRadius: 3,
        pointBackgroundColor: "#1d5af5",
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { font: { family: "'IBM Plex Mono'", size: 9 }, maxTicksLimit: 12 },
          grid: { display: false },
        },
        y: {
          beginAtZero: true,
          ticks: { font: { family: "'IBM Plex Mono'", size: 10 }, precision: 0 },
          grid: { color: "#eee" },
        }
      }
    }
  });
}

// ── Map ────────────────────────────────────────────────────────────
function initMap() {
  if (map) return;

  map = L.map("map", { zoomControl: true }).setView([25.3176, 82.9739], 15);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);
}

function refreshMap() {
  if (!map) return;

  fetch("/api/potholes")
    .then(r => r.json())
    .then(rows => {
      // Clear old markers
      markers.forEach(m => map.removeLayer(m));
      markers = [];

      const valid = rows.filter(r => r.latitude != null && r.longitude != null);

      if (!valid.length) return;

      const bounds = [];

      valid.forEach(ph => {
        const color = ph.severity === "HIGH" ? "#d43f3f"
                    : ph.severity === "MEDIUM" ? "#d47a10"
                    : "#1a8a4a";

        const circleIcon = L.divIcon({
          className: "",
          html: `<div style="
            width:14px; height:14px;
            border-radius:50%;
            background:${color};
            border:2px solid #fff;
            box-shadow:0 1px 4px rgba(0,0,0,0.3);
          "></div>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });

        const m = L.marker([ph.latitude, ph.longitude], { icon: circleIcon });

        m.bindPopup(`
          <span class="popup-sev sev-${ph.severity}" style="
            background:${ph.severity === 'HIGH' ? '#fdf0f0' : ph.severity === 'MEDIUM' ? '#fdf6ed' : '#eef8f2'};
            color:${color};
            border:1px solid ${color}44;
            padding:2px 7px; border-radius:2px; font-size:11px;
          ">${ph.severity}</span>
          <div class="popup-row" style="margin-top:8px"><b>Depth:</b> ${(+ph.depth_mm).toFixed(1)} mm</div>
          <div class="popup-row"><b>Width:</b> ${(+ph.width_mm).toFixed(1)} mm</div>
          <div class="popup-row"><b>Time:</b> ${ph.timestamp || "—"}</div>
        `);

        m.addTo(map);
        markers.push(m);
        bounds.push([ph.latitude, ph.longitude]);
      });

      if (bounds.length) {
        try { map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 }); }
        catch(e) {}
      }
    })
    .catch(() => {});
}

// ── Export CSV ─────────────────────────────────────────────────────
function exportCSV() {
  window.location.href = "/api/export/csv";
}

// ── Simulate ───────────────────────────────────────────────────────
function simulate() {
  fetch("/api/simulate", { method: "POST" })
    .then(r => r.json())
    .then(d => {
      if (d.inserted) addFeedItem(d.inserted);
      refreshStats();
    })
    .catch(() => {});
}

// ── Helpers ────────────────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val != null ? val : "—";
}

// ── Boot ───────────────────────────────────────────────────────────
(function init() {
  refreshStats();
  pollStatus();
  connectSSE();

  // Periodic status polling (every 5 s)
  setInterval(pollStatus, 5000);
})();
