#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from db import (
    get_app_totals,
    get_daily_totals,
    get_project_totals,
    get_stats_summary,
    get_today_by_app,
    init_db,
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
