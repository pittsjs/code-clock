# code-clock ⏱

**Automatically track how much time you spend coding — across every editor, with no plugins.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

<!-- Add a screenshot or GIF here once you have one -->
<!-- ![demo](assets/demo.gif) -->

## What it does

code-clock runs silently in the background and watches which app you have in focus. When it's a coding tool — Cursor, VS Code, Terminal, or any editor — it records the session. When you switch away for more than 5 minutes, the session ends and gets written to a local database.

**No account. No cloud. No plugins. Your data never leaves your machine.**

```
$ coding-time today

╭─ Monday, April 27 ──╮
│  3h 42m coded today │
╰─────────────────────╯

  App       Time
 ──────────────────────────────────────────
  Cursor    2h 55m  ██████████████░░░░  79%
  Claude      47m   ████░░░░░░░░░░░░░░  21%

$ coding-time week

  Last 7 days
  Date        Day    Time
 ──────────────────────────────────────────────────
  2026-04-21  Mon    1h 20m  ███████░░░░░░░░░░░░░
  2026-04-22  Tue    4h 05m  ████████████████████
  2026-04-23  Wed       —
  2026-04-24  Thu    2h 11m  ██████████░░░░░░░░░░
  2026-04-25  Fri    3h 42m  ██████████████████░░
  2026-04-26  Sat    1h 03m  █████░░░░░░░░░░░░░░░
  2026-04-27  Sun    3h 42m  ██████████████████░░

  Total 16h 03m  ·  Average 2h 17m/day
```

## Features

- **Zero-config tracking** — install once, forget about it. Starts automatically on every login.
- **Works across all editors** — Cursor, VS Code, Claude, Terminal, iTerm2, Warp, JetBrains, Xcode, and more
- **Project detection** — infers the project name from window titles automatically (editors like Cursor and VS Code include the folder name in the title bar; apps like Claude do not, so their time is tracked but not attributed to a project)
- **Beautiful CLI** — daily summary, weekly view, per-project breakdown, all in your terminal
- **HTML dashboard** — dark-mode bar charts, doughnut charts, streak and KPI cards
- **GitHub profile integration** — auto-updates your profile README with a live stats block every day
- **JSON export** — structured stats output for custom dashboards or GitHub Actions
- **Screen Time import** — backfill months of history from macOS Screen Time with a single query
- **Lightweight** — ~15 MB RAM, near-zero CPU, no internet required

## Why not WakaTime?

WakaTime is great. But it requires a plugin in every editor, an account, and sends your data to a third-party server. code-clock is fully local, works with any app that has a window title, and takes 30 seconds to set up.

## Requirements

- macOS 12+
- Python 3.10+

## Installation

```bash
git clone https://github.com/pittsjs/code-clock.git
cd code-clock
bash install.sh
```

Open a new terminal tab — the `coding-time` command is ready.

> **Permissions:** macOS will prompt for **Accessibility** access the first time the tracker runs. Allow it in **System Settings → Privacy & Security → Accessibility**. This is the only permission required.

## Usage

```bash
coding-time today                  # today's coding time, split by app
coding-time week                   # last 7 days with a bar chart
coding-time week --days 14         # extend the lookback window
coding-time projects               # time per project (last 30 days)
coding-time projects --days 7      # shorter window
coding-time dashboard              # generate and open HTML dashboard in browser
coding-time export                 # print JSON stats to stdout
coding-time export -o stats.json   # write to file
coding-time status                 # check if the background daemon is running
```

## HTML Dashboard

`coding-time dashboard` generates a self-contained dark-mode HTML report and opens it in your browser:

- 30-day daily hours bar chart
- Top projects horizontal bar chart
- App split doughnut chart
- Weekly hours, streak, and active days KPIs

## GitHub Profile Integration

code-clock can automatically update your GitHub profile README with a live coding stats block. The setup uses two pieces:

1. **A nightly local job** — `scripts/push_stats.sh` exports your stats to `stats.json` and pushes it to this repo at 23:55 every night (installed automatically by `install.sh`).

2. **A GitHub Action** in your profile repo — fetches `stats.json` and updates your README between these markers:

```markdown
<!--START_SECTION:coding-stats-->
<!--END_SECTION:coding-stats-->
```

The result on your profile:

```
**16.1h** this week · 6/7 days active · 🔥 4 day streak

| Day | Time |                  |
|-----|------|------------------|
| Mon | 5h 28m | ████████████████ |
| Tue | 2h 41m | ████████         |
| ...

> Top project: code-clock · Auto-updated Apr 27, 2026
```

The full workflow file is at [`.github/workflows/update-readme.yml`](.github/workflows/update-readme.yml) — see the [setup guide](#installation) to wire it up for your profile.

## JSON Export Format

```json
{
  "generated_at": "2026-04-27",
  "period_days": 7,
  "summary": {
    "total_hours": 16.1,
    "daily_avg_hours": 2.3,
    "days_active": 6,
    "streak_days": 4,
    "top_project": "code-clock"
  },
  "daily": [{ "date": "2026-04-21", "hours": 1.33 }, "..."],
  "projects": [{ "name": "code-clock", "hours": 8.2 }, "..."],
  "apps": [{ "name": "Cursor", "hours": 12.1 }, "..."]
}
```

## How it works

A launchd daemon (`tracker.py`) polls the frontmost macOS app every 10 seconds using the native `NSWorkspace` API — no Accessibility or Automation permission required for app detection:

```python
from AppKit import NSWorkspace
app = NSWorkspace.sharedWorkspace().frontmostApplication()
app_name = app.localizedName()
```

Window titles (used for project detection) are read via the Accessibility API. Sessions are flushed to a local SQLite database (`~/.coding_tracker.db`) when you switch apps or after 5 minutes of inactivity.

## Supported Apps

Cursor, VS Code, Claude, Terminal, iTerm2, Warp, Ghostty, Alacritty, Hyper, PyCharm, IntelliJ IDEA, WebStorm, Xcode, Nova, Sublime Text, TextMate, MacVim, Emacs

Adding more is one line in [`config.py`](config.py).

## Roadmap

- [x] GitHub Actions workflow to auto-update profile README
- [ ] `coding-time import-screentime` — import macOS Screen Time history as backfill
- [ ] Shareable stats card (SVG / image badge)
- [ ] Per-language breakdown from file extensions in window titles
- [ ] Daily goal + streak notifications
- [ ] Linux support via `xdotool`
- [ ] Web UI with persistent history

## Contributing

PRs welcome. The codebase is intentionally small:

| File | Purpose |
|---|---|
| `tracker.py` | Background daemon — polls frontmost app, flushes sessions |
| `db.py` | SQLite read/write layer |
| `cli.py` | CLI commands (`today`, `week`, `projects`, `dashboard`, `export`) |
| `dashboard.py` | Self-contained HTML report generator |
| `config.py` | Tracked app list and tunable settings |
| `scripts/push_stats.sh` | Nightly stats export and git push |

## License

[MIT](LICENSE)
