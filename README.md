# code-clock ⏱

**Automatically track how much time you spend coding — across every editor, with no plugins.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

<!-- Add a GIF or screenshot here once you have one running -->
<!-- ![demo](assets/demo.gif) -->

## What it does

code-clock runs silently in the background and watches which app you're focused on. When it's a coding tool (Cursor, VS Code, Terminal, iTerm2, etc.), it records the session. When you switch away for more than 5 minutes, the session ends.

No account. No cloud. No plugins. Everything stays on your machine.

```
$ coding-time today

╭─── Sunday, April 27 ─────────────────╮
│  3h 42m coded today                  │
╰───────────────────────────────────────╯

  App       Time    
  Cursor    2h 55m  ██████████████░░░░ 79%
  Terminal    47m   ████░░░░░░░░░░░░░░ 21%

$ coding-time week

  Last 7 days
  Date        Day   Time    
  2026-04-21  Mon   1h 20m  ███████░░░░░░░░░░░░░
  2026-04-22  Tue   4h 05m  ████████████████████
  2026-04-23  Wed      —
  2026-04-24  Thu   2h 11m  ██████████░░░░░░░░░░
  2026-04-25  Fri   3h 42m  ██████████████████░░
  2026-04-26  Sat   1h 03m  █████░░░░░░░░░░░░░░░
  2026-04-27  Sun   3h 42m  ██████████████████░░

  Total 16h 03m  ·  Average 2h 17m/day
```

## Features

- **Zero-config tracking** — install once, forget about it
- **Works across all editors** — Cursor, VS Code, Terminal, iTerm2, Warp, Ghostty, JetBrains, Xcode, and more
- **Project detection** — infers the project name from window titles automatically
- **Beautiful CLI** — daily summary, weekly view, per-project breakdown
- **HTML dashboard** — bar charts, doughnut charts, streak tracking
- **JSON export** — structured stats ready for GitHub Actions / profile READMEs
- **Lightweight** — ~15 MB RAM, near-zero CPU, no internet required

## Why not WakaTime?

WakaTime is great. But it requires installing a plugin in every editor, creating an account, and sending your data to a third-party server. code-clock is fully local, works with any app that has a window title, and takes 30 seconds to set up.

## Requirements

- macOS (uses `osascript` + launchd)
- Python 3.10+

## Installation

```bash
git clone https://github.com/pittsjs/code-clock.git
cd code-clock
bash install.sh
```

Open a new terminal tab — the `coding-time` command is ready.

> **First run:** macOS will ask for Accessibility permission so the tracker can read which app is in focus. Allow it in **System Settings → Privacy & Security → Accessibility**.

## Usage

```bash
coding-time today       # today's coding time by app
coding-time week        # last 7 days with a bar chart
coding-time week --days 14
coding-time projects    # time per project (last 30 days)
coding-time projects --days 7
coding-time dashboard   # open HTML dashboard in browser
coding-time export      # print JSON stats to stdout
coding-time export -o stats.json   # write to file
coding-time status      # check if the daemon is running
```

## HTML Dashboard

`coding-time dashboard` generates a dark-mode HTML report and opens it in your browser:

- Daily hours bar chart (30 days)
- Top projects horizontal bar chart
- App breakdown doughnut chart
- Streak and weekly summary KPIs

## GitHub Integration

The `export` command outputs structured JSON:

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
  "daily": [...],
  "projects": [...],
  "apps": [...]
}
```

You can use this with a GitHub Action to automatically update your profile README with your latest coding stats. A ready-made workflow is on the roadmap.

## How it works

A launchd daemon (`tracker.py`) polls the frontmost macOS app every 10 seconds using AppleScript:

```applescript
tell application "System Events"
    set frontApp to name of first process whose frontmost is true
    ...
end tell
```

If the app is in the configured list of coding tools, the time is counted. Sessions are flushed to a local SQLite database (`~/.coding_tracker.db`) when you switch apps or after 5 minutes of inactivity.

## Supported apps

Cursor, VS Code, Terminal, iTerm2, Warp, Ghostty, Alacritty, Hyper, PyCharm, IntelliJ IDEA, WebStorm, Xcode, Nova, Sublime Text, TextMate, MacVim, Emacs

Adding more is one line in [`config.py`](config.py).

## Roadmap

- [ ] GitHub Actions workflow to auto-update profile README
- [ ] Shareable stats card (SVG badge / image)
- [ ] Per-language breakdown (from file extensions in window titles)
- [ ] Daily goal + streak notifications
- [ ] Linux support (via `xdotool`)
- [ ] Web UI with persistent history

## Contributing

PRs welcome. The codebase is small and easy to navigate:

| File | Purpose |
|---|---|
| `tracker.py` | Background daemon |
| `db.py` | SQLite read/write |
| `cli.py` | CLI commands |
| `dashboard.py` | HTML report generator |
| `config.py` | App list + settings |

## License

[MIT](LICENSE)
