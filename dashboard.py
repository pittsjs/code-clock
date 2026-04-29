"""Generates a self-contained interactive HTML dashboard with Chart.js charts."""

import json
import sqlite3
from datetime import date, timedelta

from config import DASHBOARD_PATH, DB_PATH
from db import get_app_totals, get_daily_totals, get_project_totals, get_stats_summary


def _fmt(secs: int) -> str:
    """Format seconds as 'Xh Ym' or 'Ym'."""
    secs = int(round(secs))
    h = secs // 3600
    m = (secs % 3600) // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


# Apps with less than this many seconds in a window are treated as noise
# (e.g. accidentally focusing Terminal for 10s) and hidden from the charts.
_APP_MIN_SECS = 60


def _app_totals_window(days: int) -> list[dict]:
    """App totals for the last N days. Returns [{app, secs}, ...] sorted desc.

    Filters out apps with < _APP_MIN_SECS so the doughnut legend only shows
    apps the user meaningfully used in the window.
    """
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT app, SUM(duration_secs) AS total
        FROM sessions
        WHERE date(started_at) >= ?
        GROUP BY app
        HAVING total >= ?
        ORDER BY total DESC
        """,
        (since, _APP_MIN_SECS),
    ).fetchall()
    conn.close()
    return [{"app": r["app"], "secs": r["total"]} for r in rows]


def _daily_by_app(days: int = 30) -> tuple[list[str], list[str], dict[str, list[int]]]:
    """Per-day totals split by app.

    Returns (dates, apps, series) where series[app] is a list of seconds per
    date, padded with 0 for days the app wasn't used.
    """
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT date(started_at) AS day, app, SUM(duration_secs) AS total
        FROM sessions
        WHERE date(started_at) >= ?
        GROUP BY day, app
        ORDER BY day
        """,
        (since,),
    ).fetchall()
    conn.close()

    dates = sorted({r["day"] for r in rows})
    # Order apps by total time desc so the largest stacks render first.
    app_totals: dict[str, int] = {}
    for r in rows:
        app_totals[r["app"]] = app_totals.get(r["app"], 0) + r["total"]
    # Drop apps that barely registered in the entire window — same noise
    # filter as the doughnut so the stacked-bar legend stays clean.
    apps = sorted(
        (a for a, t in app_totals.items() if t >= _APP_MIN_SECS),
        key=lambda a: app_totals[a],
        reverse=True,
    )

    series = {app: [0] * len(dates) for app in apps}
    date_idx = {d: i for i, d in enumerate(dates)}
    for r in rows:
        if r["app"] in series:
            series[r["app"]][date_idx[r["day"]]] = r["total"]
    return dates, apps, series


def generate_dashboard() -> str:
    projects = get_project_totals(30)
    summary = get_stats_summary(7)

    daily_dates, daily_apps, daily_series = _daily_by_app(30)
    daily_labels = [d[5:] for d in daily_dates]

    proj_labels = [r["project"] for r in projects[:10]]
    proj_secs = [r["total"] for r in projects[:10]]

    # Per-window app data (for sortable doughnut)
    app_windows = {
        "day": _app_totals_window(1),
        "week": _app_totals_window(7),
        "month": _app_totals_window(30),
    }

    total_secs = summary["total_secs"]
    streak = summary["streak"]
    top_project = summary["top_project"] or "—"
    days_active = summary["days_active"]
    generated = date.today().strftime("%B %d, %Y")
    week_total_str = _fmt(total_secs)
    daily_avg_str = _fmt(total_secs // 7) if total_secs else "0m"

    # JSON payload for JS — keep formatting in one place via a JS helper.
    payload = {
        "daily": {
            "labels": daily_labels,
            "dates": daily_dates,
            "apps": daily_apps,
            "series": daily_series,
        },
        "projects": {"labels": proj_labels, "secs": proj_secs},
        "appWindows": app_windows,
        "summary": {
            "weekTotal": week_total_str,
            "dailyAvg": daily_avg_str,
            "streak": streak,
            "daysActive": days_active,
            "topProject": top_project,
        },
    }
    payload_json = json.dumps(payload)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coding Time Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    padding: 28px 24px;
    max-width: 1200px;
    margin: 0 auto;
  }
  h1 { font-size: 1.6rem; color: #e6edf3; }
  .header { display: flex; align-items: center; gap: 14px; }
  .streak-pill {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    background: #0f2419;
    border: 1px solid #238636;
    color: #3fb950;
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 0.8rem;
  }
  .streak-num { font-weight: 700; font-size: 0.95rem; }
  .streak-text { color: #8b949e; }
  .subtitle { color: #8b949e; font-size: 0.85rem; margin: 4px 0 24px; }

  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 14px;
    margin-bottom: 18px;
  }
  .kpi {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px 18px;
    cursor: pointer;
    transition: border-color 0.15s ease, background 0.15s ease;
  }
  .kpi:hover { border-color: #58a6ff; background: #0f1722; }
  .kpi.active { border-color: #58a6ff; }
  .kpi-value { font-size: 1.9rem; font-weight: 700; color: #58a6ff; line-height: 1; }
  .kpi-value.accent { color: #3fb950; }
  .kpi-value.small { font-size: 1.05rem; padding-top: 6px; }
  .kpi-label {
    font-size: 0.7rem;
    color: #8b949e;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .layout {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 14px;
    align-items: start;
  }

  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 14px;
  }
  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    gap: 12px;
  }
  .card-title {
    font-size: 0.72rem;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .seg {
    display: inline-flex;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    overflow: hidden;
  }
  .seg button {
    background: none;
    border: none;
    color: #8b949e;
    padding: 5px 12px;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .seg button:hover { color: #c9d1d9; }
  .seg button.active {
    background: #1f6feb;
    color: #fff;
  }

  canvas { width: 100% !important; max-height: 240px; }
  #appCanvas { max-height: 220px; }

  .side {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 18px 20px;
    position: sticky;
    top: 16px;
  }
  .side-title {
    font-size: 0.72rem;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 14px;
    padding-bottom: 12px;
    border-bottom: 1px solid #30363d;
  }
  .side-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    font-size: 0.85rem;
  }
  .side-row + .side-row { border-top: 1px solid #21262d; }
  .side-key { color: #8b949e; }
  .side-val { color: #58a6ff; font-weight: 600; }
  .side-note {
    color: #6e7681;
    font-size: 0.75rem;
    margin-top: 10px;
    line-height: 1.5;
  }

  @media (max-width: 900px) {
    .layout { grid-template-columns: 1fr; }
    .side { position: static; }
  }
</style>
</head>
<body>

<div class="header">
  <h1>Coding Time</h1>
  <div class="streak-pill" title="Current day streak">
    <span class="streak-num">__STREAK__</span>
    <span class="streak-text">day streak 🔥</span>
  </div>
</div>
<div class="subtitle">Generated __GENERATED__ &nbsp;·&nbsp; Click a KPI or chart for details</div>

<div class="kpi-grid">
  <div class="kpi" data-detail="week" onclick="showDetail(this, 'week')">
    <div class="kpi-value">__WEEK_TOTAL__</div>
    <div class="kpi-label">This week</div>
  </div>
  <div class="kpi" data-detail="active" onclick="showDetail(this, 'active')">
    <div class="kpi-value">__DAYS_ACTIVE__<span style="font-size:1rem;color:#8b949e">/7</span></div>
    <div class="kpi-label">Active days</div>
  </div>
  <div class="kpi" data-detail="topproject" onclick="showDetail(this, 'topproject')">
    <div class="kpi-value small">__TOP_PROJECT__</div>
    <div class="kpi-label">Top project</div>
  </div>
</div>

<div class="layout">
  <div>
    <div class="card">
      <div class="card-head">
        <div class="card-title">Time by app</div>
        <div class="seg" id="appSeg">
          <button data-window="day">Day</button>
          <button data-window="week" class="active">Week</button>
          <button data-window="month">Month</button>
        </div>
      </div>
      <canvas id="appCanvas"></canvas>
    </div>

    <div class="card">
      <div class="card-title" style="margin-bottom:14px">Daily coding hours — last 30 days</div>
      <canvas id="dailyCanvas"></canvas>
    </div>

    <div class="card">
      <div class="card-title" style="margin-bottom:14px">Top projects (30d)</div>
      <canvas id="projCanvas"></canvas>
    </div>
  </div>

  <aside class="side" id="sidePanel">
    <div class="side-title">Details</div>
    <div class="side-note">Click any KPI card or chart bar to see details here.</div>
  </aside>
</div>

<script>
const DATA = __PAYLOAD__;

const GRID = '#21262d';
const TICK = '#8b949e';
const COLORS = ['#1f6feb','#3fb950','#d29922','#f85149','#a371f7','#58a6ff','#bf8700','#e85aad'];

// ---------- formatting ----------
function fmtSecs(secs) {
  secs = Math.round(secs);
  if (secs <= 0) return '0m';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h && m) return `${h}h ${String(m).padStart(2,'0')}m`;
  if (h) return `${h}h`;
  return `${m}m`;
}

const tooltipFmt = {
  filter: (ctx) => Number(ctx.raw) > 0,
  callbacks: {
    label: (ctx) => {
      const secs = ctx.raw;
      // Prefer the dataset label (app name on stacked bars), fall back to
      // the slice label (e.g. for the doughnut where each slice is an app).
      const label = ctx.dataset.label || ctx.label || '';
      return ` ${label ? label + ': ' : ''}${fmtSecs(secs)}`;
    }
  }
};

// ---------- side panel ----------
function setSide(title, rows, note) {
  const panel = document.getElementById('sidePanel');
  let html = `<div class="side-title">${title}</div>`;
  for (const [k, v] of rows) {
    html += `<div class="side-row"><span class="side-key">${k}</span><span class="side-val">${v}</span></div>`;
  }
  if (note) html += `<div class="side-note">${note}</div>`;
  panel.innerHTML = html;
}

function highlightKpi(el) {
  document.querySelectorAll('.kpi').forEach(k => k.classList.remove('active'));
  if (el) el.classList.add('active');
}

function showDetail(el, type) {
  highlightKpi(el);
  const s = DATA.summary;
  if (type === 'week') {
    setSide('This Week', [
      ['Total', s.weekTotal],
      ['Daily average', s.dailyAvg],
      ['Active days', `${s.daysActive} of 7`],
    ]);
  } else if (type === 'streak') {
    setSide('Current Streak 🔥', [
      ['Days in a row', s.streak],
    ], 'Code today to keep the streak alive.');
  } else if (type === 'active') {
    const pct = Math.round((s.daysActive / 7) * 100);
    setSide('Active Days', [
      ['This week', `${s.daysActive} of 7`],
      ['Coverage', `${pct}%`],
    ]);
  } else if (type === 'topproject') {
    setSide('Top Project', [
      ['Project', s.topProject],
    ], 'Most-used project this week.');
  }
}

// ---------- charts ----------
// Keep a single canonical app→color mapping so doughnut and stacked
// bar chart use matching swatches.
function buildAppColorMap(allApps) {
  const map = {};
  allApps.forEach((app, i) => { map[app] = COLORS[i % COLORS.length]; });
  return map;
}
// Union of apps across all windows + daily series so colors are stable.
const allAppsSet = new Set();
for (const win of Object.values(DATA.appWindows)) {
  for (const r of win) allAppsSet.add(r.app);
}
for (const a of DATA.daily.apps) allAppsSet.add(a);
const APP_COLORS = buildAppColorMap([...allAppsSet]);

const appChart = new Chart(document.getElementById('appCanvas'), {
  type: 'doughnut',
  data: {
    labels: DATA.appWindows.week.map(r => r.app),
    datasets: [{
      data: DATA.appWindows.week.map(r => r.secs),
      backgroundColor: DATA.appWindows.week.map(r => APP_COLORS[r.app]),
      borderWidth: 0,
      hoverOffset: 10,
      offset: DATA.appWindows.week.map(() => 0),
    }]
  },
  options: {
    responsive: true,
    cutout: '60%',
    plugins: {
      legend: { position: 'bottom', labels: { color: TICK, boxWidth: 12, padding: 14 } },
      tooltip: tooltipFmt,
    },
    onClick: (evt, elements) => {
      const ds = appChart.data.datasets[0];
      const total = ds.data.reduce((a, b) => a + b, 0);
      if (!elements.length) {
        // Clicked empty space → clear highlight.
        ds.offset = ds.data.map(() => 0);
        appChart.update();
        return;
      }
      const i = elements[0].index;
      const app = appChart.data.labels[i];
      const secs = ds.data[i];
      const pct = total ? Math.round((secs / total) * 100) : 0;
      // Pop the selected slice out, push others back in.
      ds.offset = ds.data.map((_, idx) => idx === i ? 18 : 0);
      appChart.update();
      const winLabel = document.querySelector('#appSeg button.active').textContent;
      setSide(`${app}`, [
        [`Time (${winLabel})`, fmtSecs(secs)],
        ['Share', `${pct}%`],
      ]);
      highlightKpi(null);
    }
  }
});

document.querySelectorAll('#appSeg button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#appSeg button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const win = btn.dataset.window;
    const rows = DATA.appWindows[win];
    appChart.data.labels = rows.map(r => r.app);
    appChart.data.datasets[0].data = rows.map(r => r.secs);
    appChart.data.datasets[0].backgroundColor = rows.map(r => APP_COLORS[r.app]);
    appChart.data.datasets[0].offset = rows.map(() => 0);
    appChart.update();
  });
});

// Stacked bar chart — one dataset per app, summed per day.
const dailyDatasets = DATA.daily.apps.map(app => ({
  label: app,
  data: DATA.daily.series[app],
  backgroundColor: APP_COLORS[app],
  borderWidth: 0,
  borderRadius: 0,
}));

const dailyChart = new Chart(document.getElementById('dailyCanvas'), {
  type: 'bar',
  data: { labels: DATA.daily.labels, datasets: dailyDatasets },
  options: {
    responsive: true,
    plugins: {
      legend: { position: 'bottom', labels: { color: TICK, boxWidth: 12, padding: 14 } },
      tooltip: { ...tooltipFmt, mode: 'index', intersect: false }
    },
    onClick: (evt, elements) => {
      if (!elements.length) return;
      const i = elements[0].index;
      const date = DATA.daily.dates[i];
      // Build per-app rows for this day, sorted desc, hide zeros.
      const rows = [];
      let total = 0;
      DATA.daily.apps.forEach(app => {
        const s = DATA.daily.series[app][i];
        if (s > 0) rows.push([app, s]);
        total += s;
      });
      rows.sort((a, b) => b[1] - a[1]);
      const formatted = rows.map(([app, s]) => [app, fmtSecs(s)]);
      formatted.unshift(['Total', fmtSecs(total)]);
      setSide(`📅 ${date}`, formatted);
      highlightKpi(null);
    },
    scales: {
      x: {
        stacked: true,
        ticks: { color: TICK, maxTicksLimit: 12 },
        grid: { color: GRID },
      },
      y: {
        stacked: true,
        ticks: { color: TICK, callback: (v) => fmtSecs(v) },
        grid: { color: GRID },
        beginAtZero: true,
      }
    }
  }
});

const projChart = new Chart(document.getElementById('projCanvas'), {
  type: 'bar',
  data: {
    labels: DATA.projects.labels,
    datasets: [{
      label: '',
      data: DATA.projects.secs,
      backgroundColor: '#3fb950',
      borderRadius: 4,
      borderSkipped: false,
    }]
  },
  options: {
    indexAxis: 'y',
    responsive: true,
    plugins: { legend: { display: false }, tooltip: tooltipFmt },
    onClick: (evt, elements) => {
      if (!elements.length) return;
      const i = elements[0].index;
      setSide(DATA.projects.labels[i], [
        ['Time (30d)', fmtSecs(DATA.projects.secs[i])],
      ]);
      highlightKpi(null);
    },
    scales: {
      x: {
        ticks: { color: TICK, callback: (v) => fmtSecs(v) },
        grid: { color: GRID },
        beginAtZero: true,
      },
      y: { ticks: { color: TICK }, grid: { color: GRID } }
    }
  }
});
</script>
</body>
</html>"""

    html = (
        html.replace("__GENERATED__", generated)
        .replace("__WEEK_TOTAL__", week_total_str)
        .replace("__STREAK__", str(streak))
        .replace("__DAYS_ACTIVE__", str(days_active))
        .replace("__TOP_PROJECT__", top_project)
        .replace("__PAYLOAD__", payload_json)
    )

    with open(DASHBOARD_PATH, "w") as f:
        f.write(html)

    return DASHBOARD_PATH
