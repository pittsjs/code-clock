#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from db import (
    _conn,
    get_app_totals,
    get_daily_totals,
    get_project_totals,
    get_projects_timeline,
    get_stats_summary,
    get_today_by_app,
    init_db,
    save_session,
)

console = Console()


def _fmt(secs: int) -> str:
    if secs <= 0:
        return "—"
    h = secs // 3600
    m = (secs % 3600) // 60
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def _bar(value: int, max_value: int, width: int = 18) -> str:
    if max_value <= 0:
        return ""
    filled = int(value / max_value * width)
    return "[green]" + "█" * filled + "[/green]" + "[dim]" + "░" * (width - filled) + "[/dim]"


# ---------------------------------------------------------------------------


@click.group()
def cli():
    """Coding time tracker."""
    init_db()


@cli.command()
def today():
    """Show today's coding summary."""
    rows = get_today_by_app()
    total = sum(r["total"] for r in rows)

    if not rows:
        console.print("[dim]No coding sessions recorded today yet.[/dim]")
        return

    console.print(
        Panel(
            f"[bold green]{_fmt(total)}[/bold green] coded today",
            title=f"[bold]{date.today().strftime('%A, %B %d')}[/bold]",
            border_style="green",
            expand=False,
        )
    )

    table = Table(box=box.SIMPLE_HEAD, show_footer=False, padding=(0, 1))
    table.add_column("App", style="cyan")
    table.add_column("Time", justify="right", style="green")
    table.add_column("", min_width=22)

    max_val = rows[0]["total"] if rows else 1
    for row in rows:
        pct = row["total"] / total * 100 if total else 0
        table.add_row(row["app"], _fmt(row["total"]), f"{_bar(row['total'], max_val)} {pct:.0f}%")

    console.print(table)


@cli.command()
@click.option("--days", default=7, show_default=True, help="Number of days to show")
def week(days):
    """Show daily coding totals for the last N days."""
    rows = get_daily_totals(days)
    data = {r["day"]: r["total"] for r in rows}
    all_days = [(date.today() - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    total = sum(data.values())
    max_val = max(data.values()) if data else 1

    table = Table(
        title=f"Last {days} days",
        box=box.SIMPLE_HEAD,
        padding=(0, 1),
    )
    table.add_column("Date", style="dim")
    table.add_column("Day")
    table.add_column("Time", justify="right", style="green")
    table.add_column("", min_width=22)

    for d in all_days:
        secs = data.get(d, 0)
        day_name = date.fromisoformat(d).strftime("%a")
        is_today = d == date.today().isoformat()
        style = "bold" if is_today else ""
        time_str = _fmt(secs) if secs else "[dim]—[/dim]"
        table.add_row(d, day_name, time_str, _bar(secs, max_val), style=style)

    console.print(table)

    avg = total // days if days else 0
    console.print(
        f"[dim]Total [bold green]{_fmt(total)}[/bold green]  ·  "
        f"Avg [bold]{_fmt(avg)}[/bold]/day[/dim]"
    )


@cli.command()
@click.option("--days", default=30, show_default=True, help="Lookback period in days")
def projects(days):
    """Show per-project time breakdown."""
    rows = get_project_totals(days)

    if not rows:
        console.print(f"[dim]No project data in the last {days} days.[/dim]")
        return

    total = sum(r["total"] for r in rows)
    max_val = rows[0]["total"] if rows else 1

    table = Table(
        title=f"Projects — last {days} days",
        box=box.SIMPLE_HEAD,
        padding=(0, 1),
    )
    table.add_column("Project", style="cyan")
    table.add_column("Time", justify="right", style="green")
    table.add_column("", min_width=22)

    for row in rows:
        pct = row["total"] / total * 100 if total else 0
        table.add_row(
            row["project"],
            _fmt(row["total"]),
            f"{_bar(row['total'], max_val)} {pct:.0f}%",
        )

    console.print(table)


@cli.command()
@click.option("--days", default=30, show_default=True, help="Lookback period in days")
def timeline(days):
    """Show per-project breakdown with daily detail."""
    from datetime import date as _date
    rows = get_projects_timeline(days)

    if not rows:
        console.print(f"[dim]No project data in the last {days} days.[/dim]")
        return

    # Group rows by project
    projects: dict[str, list] = {}
    for r in rows:
        projects.setdefault(r["project"], []).append(r)

    # Sort projects by total time desc
    projects = dict(
        sorted(projects.items(), key=lambda kv: sum(r["total"] for r in kv[1]), reverse=True)
    )

    max_total = max(sum(r["total"] for r in v) for v in projects.values()) or 1

    for project, days_data in projects.items():
        total = sum(r["total"] for r in days_data)
        proj_bar_len = int(total / max_total * 16)
        console.print(
            f"[cyan bold]{project}[/cyan bold]  "
            f"[green]{_fmt(total)} total[/green]"
        )

        day_max = max(r["total"] for r in days_data) or 1
        for r in days_data:
            d = _date.fromisoformat(r["day"])
            day_label = d.strftime("%a %b %d")
            bar_len = int(r["total"] / day_max * 16)
            bar = "[green]" + "█" * bar_len + "[/green][dim]" + "░" * (16 - bar_len) + "[/dim]"
            console.print(f"  [dim]{day_label}[/dim]  [green]{_fmt(r['total']):>7}[/green]  {bar}")

        console.print()


@cli.command()
def dashboard():
    """Generate and open the HTML dashboard in your browser."""
    from dashboard import generate_dashboard

    path = generate_dashboard()
    console.print(f"[green]Dashboard ready:[/green] {path}")
    subprocess.run(["open", path])


@cli.command()
@click.option("--days", default=7, show_default=True, help="Stats period in days")
@click.option("--output", "-o", default=None, help="Write to file instead of stdout")
def export(days, output):
    """Export stats as JSON — useful for GitHub profile integration."""
    summary = get_stats_summary(days)
    daily = get_daily_totals(days)
    projects_data = get_project_totals(days)
    apps_data = get_app_totals(days)

    payload = {
        "generated_at": date.today().isoformat(),
        "period_days": days,
        "summary": {
            "total_hours": round(summary["total_secs"] / 3600, 1),
            "daily_avg_hours": round(
                summary["total_secs"] / 3600 / max(summary["days_active"], 1), 1
            ),
            "days_active": summary["days_active"],
            "streak_days": summary["streak"],
            "top_project": summary["top_project"],
        },
        "daily": [
            {"date": r["day"], "hours": round(r["total"] / 3600, 2)} for r in daily
        ],
        "projects": [
            {"name": r["project"], "hours": round(r["total"] / 3600, 2)}
            for r in projects_data
        ],
        "apps": [
            {"name": r["app"], "hours": round(r["total"] / 3600, 2)} for r in apps_data
        ],
    }

    out = json.dumps(payload, indent=2)
    if output:
        with open(output, "w") as f:
            f.write(out)
        console.print(f"[green]Exported to[/green] {output}")
    else:
        print(out)


# Bundle ID → friendly app name mapping for Screen Time import.
# Screen Time stores apps by bundle identifier; we translate to the same
# names used by the live tracker so reports stay consistent.
_SCREEN_TIME_BUNDLES = {
    "com.todesktop.230313mzl4w4u92": "Cursor",
    "com.anthropic.claudefordesktop": "Claude",
    "com.apple.Terminal": "Terminal",
    "com.googlecode.iterm2": "iTerm2",
    "com.warp.Warp-Stable": "Warp",
    "com.mitchellh.ghostty": "Ghostty",
    "com.microsoft.VSCode": "VS Code",
    "com.jetbrains.pycharm": "PyCharm",
    "com.jetbrains.intellij": "IntelliJ IDEA",
    "com.jetbrains.WebStorm": "WebStorm",
    "com.apple.dt.Xcode": "Xcode",
    "com.sublimetext.4": "Sublime Text",
    "com.macromates.TextMate": "TextMate",
}

_APPLE_EPOCH_OFFSET = 978307200  # seconds between 1970-01-01 and 2001-01-01


@cli.command("import-screentime")
@click.option(
    "--days",
    default=None,
    type=int,
    help="Only import sessions from the last N days (default: all available)",
)
def import_screentime(days):
    """Import historical app usage from macOS Screen Time.

    Reads ~/Library/Application Support/Knowledge/knowledgeC.db, which
    macOS keeps for ~30 days. Requires Full Disk Access for your terminal
    in System Settings → Privacy & Security → Full Disk Access.

    Re-running is safe — sessions are deduplicated by (app, start time).
    """
    st_path = os.path.expanduser("~/Library/Application Support/Knowledge/knowledgeC.db")

    if not os.path.exists(st_path):
        console.print("[red]Screen Time database not found.[/red]")
        console.print(f"[dim]Expected at: {st_path}[/dim]")
        sys.exit(1)

    try:
        st = sqlite3.connect(f"file:{st_path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        console.print(f"[red]Cannot read Screen Time database: {e}[/red]")
        console.print(
            "[yellow]This usually means your terminal needs Full Disk Access.[/yellow]\n"
            "[dim]Grant it in System Settings → Privacy & Security → Full Disk Access[/dim]"
        )
        sys.exit(1)

    bundles = list(_SCREEN_TIME_BUNDLES.keys())
    placeholders = ",".join("?" * len(bundles))

    sql = f"""
        SELECT
            ZVALUESTRING AS bundle,
            ZSTARTDATE + {_APPLE_EPOCH_OFFSET} AS start_unix,
            ZENDDATE   + {_APPLE_EPOCH_OFFSET} AS end_unix
        FROM ZOBJECT
        WHERE ZSTREAMNAME = '/app/usage'
          AND ZVALUESTRING IN ({placeholders})
          AND ZENDDATE > ZSTARTDATE
    """
    params = list(bundles)

    if days:
        cutoff_apple = (datetime.now() - timedelta(days=days)).timestamp() - _APPLE_EPOCH_OFFSET
        sql += " AND ZSTARTDATE >= ?"
        params.append(cutoff_apple)

    sql += " ORDER BY ZSTARTDATE"

    rows = st.execute(sql, params).fetchall()
    st.close()

    init_db()

    # Load existing (app, started_at) so reruns are idempotent.
    existing = set()
    with _conn() as conn:
        for r in conn.execute("SELECT app, started_at FROM sessions"):
            existing.add((r[0], r[1]))

    imported = 0
    skipped_dupe = 0
    skipped_short = 0

    for bundle, start_unix, end_unix in rows:
        started = datetime.fromtimestamp(start_unix)
        ended = datetime.fromtimestamp(end_unix)
        app = _SCREEN_TIME_BUNDLES.get(bundle, bundle)

        if (ended - started).total_seconds() < 10:
            skipped_short += 1
            continue

        if (app, started.isoformat()) in existing:
            skipped_dupe += 1
            continue

        save_session(app=app, project=None, started_at=started, ended_at=ended)
        imported += 1

    console.print(f"[green]Imported {imported} sessions[/green]")
    notes = []
    if skipped_dupe:
        notes.append(f"{skipped_dupe} already imported")
    if skipped_short:
        notes.append(f"{skipped_short} too short (<10s)")
    if notes:
        console.print(f"[dim]Skipped: {', '.join(notes)}[/dim]")

    if imported:
        console.print("[dim]Run 'coding-time week --days 30' to see backfilled history.[/dim]")


@cli.command()
def status():
    """Check whether the tracker daemon is running."""
    result = subprocess.run(
        ["launchctl", "list", "com.user.codingtracker"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[green]✓ Tracker daemon is running[/green]")
    else:
        console.print("[red]✗ Tracker daemon is not running[/red]")
        plist = os.path.expanduser(
            "~/Library/LaunchAgents/com.user.codingtracker.plist"
        )
        console.print(f"[dim]Run: launchctl load {plist}[/dim]")


@cli.command()
@click.pass_context
def stats(ctx):
    """Quick overview: today + last 7 days."""
    ctx.invoke(today)
    console.print()
    ctx.invoke(week)


if __name__ == "__main__":
    cli()
