"""Generates a self-contained HTML dashboard with Chart.js charts."""

import json
from datetime import date

from config import DASHBOARD_PATH
from db import get_app_totals, get_daily_totals, get_project_totals, get_stats_summary


def _fmt(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def generate_dashboard() -> str:
    daily = get_daily_totals(30)
    projects = get_project_totals(30)
    apps = get_app_totals(30)
    summary = get_stats_summary(7)

    daily_labels = json.dumps([r["day"][5:] for r in daily])   # MM-DD
    daily_data   = json.dumps([round(r["total"] / 3600, 2) for r in daily])

    proj_labels = json.dumps([r["project"] for r in projects[:12]])
    proj_data   = json.dumps([round(r["total"] / 3600, 2) for r in projects[:12]])

    app_labels = json.dumps([r["app"] for r in apps])
    app_data   = json.dumps([round(r["total"] / 3600, 2) for r in apps])

    total_hrs   = round(summary["total_secs"] / 3600, 1)
    streak      = summary["streak"]
    top_project = summary["top_project"] or "—"
    days_active = summary["days_active"]
    generated   = date.today().strftime("%B %d, %Y")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coding Time Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    padding: 28px 24px;
    max-width: 1100px;
    margin: 0 auto;
  }}
  h1 {{ font-size: 1.6rem; color: #e6edf3; }}
  .subtitle {{ color: #8b949e; font-size: 0.85rem; margin: 4px 0 28px; }}

  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 14px;
    margin-bottom: 28px;
  }}
  .kpi {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 18px 20px;
  }}
  .kpi-value {{ font-size: 2rem; font-weight: 700; color: #58a6ff; line-height: 1; }}
  .kpi-value.accent {{ color: #3fb950; }}
  .kpi-label {{
    font-size: 0.72rem;
    color: #8b949e;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}

  .charts-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }}
  .card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
  }}
  .card.wide {{ grid-column: 1 / -1; }}
  .card-title {{
    font-size: 0.75rem;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 18px;
  }}
  canvas {{ width: 100% !important; max-height: 230px; }}

  @media (max-width: 640px) {{
    .charts-grid {{ grid-template-columns: 1fr; }}
    .card.wide {{ grid-column: auto; }}
  }}
</style>
</head>
<body>

<h1>Coding Time</h1>
<div class="subtitle">Generated {generated} &nbsp;·&nbsp; 30-day window</div>

<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-value">{total_hrs}h</div>
    <div class="kpi-label">This week</div>
  </div>
  <div class="kpi">
    <div class="kpi-value accent">{streak}</div>
    <div class="kpi-label">Day streak 🔥</div>
  </div>
  <div class="kpi">
    <div class="kpi-value">{days_active}<span style="font-size:1rem;color:#8b949e">/7</span></div>
    <div class="kpi-label">Active days</div>
  </div>
  <div class="kpi">
    <div class="kpi-value" style="font-size:1.25rem;padding-top:4px">{top_project}</div>
    <div class="kpi-label">Top project</div>
  </div>
</div>

<div class="charts-grid">

  <div class="card wide">
    <div class="card-title">Daily coding hours — last 30 days</div>
    <canvas id="dailyChart"></canvas>
  </div>

  <div class="card">
    <div class="card-title">Top projects (30d)</div>
    <canvas id="projChart"></canvas>
  </div>

  <div class="card">
    <div class="card-title">Time by app (30d)</div>
    <canvas id="appChart"></canvas>
  </div>

</div>

<script>
const GRID_COLOR = '#21262d';
const TICK_COLOR = '#8b949e';

new Chart(document.getElementById('dailyChart'), {{
  type: 'bar',
  data: {{
    labels: {daily_labels},
    datasets: [{{
      data: {daily_data},
      backgroundColor: '#1f6feb',
      borderRadius: 4,
      borderSkipped: false,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: TICK_COLOR, maxTicksLimit: 12 }}, grid: {{ color: GRID_COLOR }} }},
      y: {{ ticks: {{ color: TICK_COLOR }}, grid: {{ color: GRID_COLOR }}, beginAtZero: true }}
    }}
  }}
}});

new Chart(document.getElementById('projChart'), {{
  type: 'bar',
  data: {{
    labels: {proj_labels},
    datasets: [{{
      data: {proj_data},
      backgroundColor: '#238636',
      borderRadius: 4,
      borderSkipped: false,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: TICK_COLOR }}, grid: {{ color: GRID_COLOR }}, beginAtZero: true }},
      y: {{ ticks: {{ color: TICK_COLOR }}, grid: {{ color: GRID_COLOR }} }}
    }}
  }}
}});

new Chart(document.getElementById('appChart'), {{
  type: 'doughnut',
  data: {{
    labels: {app_labels},
    datasets: [{{
      data: {app_data},
      backgroundColor: ['#1f6feb','#238636','#9e6a03','#da3633','#8957e5','#0969da'],
      borderWidth: 0,
      hoverOffset: 6,
    }}]
  }},
  options: {{
    responsive: true,
    cutout: '62%',
    plugins: {{
      legend: {{
        position: 'bottom',
        labels: {{ color: TICK_COLOR, boxWidth: 12, padding: 14 }}
      }}
    }}
  }}
}});
</script>
</body>
</html>"""

    with open(DASHBOARD_PATH, "w") as f:
        f.write(html)

    return DASHBOARD_PATH
