import os

CODING_APPS = {
    "Claude",
    "Cursor",
    "Code",                 # VS Code process name on macOS
    "Visual Studio Code",
    "Terminal",
    "iTerm2",
    "iTerm",
    "Alacritty",
    "Warp",
    "Ghostty",
    "Hyper",
    "PyCharm",
    "PyCharm CE",
    "IntelliJ IDEA",
    "WebStorm",
    "Xcode",
    "Nova",
    "Sublime Text",
    "TextMate",
    "MacVim",
    "Emacs",
}

# Human-friendly display names for process names
APP_DISPLAY_NAMES = {
    "Code": "VS Code",
    "Visual Studio Code": "VS Code",
    "iTerm": "iTerm2",
    "PyCharm CE": "PyCharm",
}

POLL_INTERVAL_SECS = 10
IDLE_THRESHOLD_SECS = 300   # 5 min of non-coding = end of session

# --- Project detection ------------------------------------------------------

# Window titles that name a pane, tab, or terminal geometry rather than a
# project. Matched case-insensitively against the extracted name; anything
# listed here is recorded as "no project" instead.
PROJECT_TITLE_BLOCKLIST = {
    "cursor agents",
    "agents",
    "settings",
    "welcome",
    "extension",
    "keyboard shortcuts",
    "get started",
    "untitled",
}

# Terminal titles are often just a window geometry ("80×24"). Reject those.
PROJECT_TITLE_REJECT_PATTERN = r"^\d+\s*[x×]\s*\d+$"

# Claude's window title is only ever the literal string "Claude" — it carries
# no project. Claude Code does record its working directory on disk, one
# directory per project, with the path's slashes rewritten as dashes:
#   ~/.claude/projects/-Users-you-github-myrepo/<session>.jsonl
# The most recently written session log is the project in use, so that is what
# we attribute Claude time to.
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")

# Ignore Claude session logs older than this — a stale directory means Claude
# is open but idle, not that the old project is active.
CLAUDE_PROJECT_MAX_AGE_SECS = 900

# --- Export privacy ---------------------------------------------------------
# `export` writes stats.json, which is typically committed to a PUBLIC repo so
# a profile README can read it. Project names come from window titles and local
# paths, so they leak private and client repo names by default. Export is
# therefore deny-by-default: a project is published only if it is named below.
#
# Local reporting (`today`, `week`, `projects`, the dashboard) is unaffected —
# it always shows real names. Only the exported file is redacted.

# Set True to publish every project name, disabling redaction entirely.
EXPORT_PUBLISH_ALL_PROJECTS = False

# Real project name -> the label to publish for it. Doubles as the allowlist:
# a project absent from this map is never published under its real name.
EXPORT_PROJECT_ALIASES = {
    "code-clock": "code-clock",
    "pittsjs": "pittsjs",
}

# What to call everything else. Redacted projects are merged into this single
# bucket so their total time still counts. Set to None to drop them entirely.
EXPORT_REDACT_LABEL = "Private project"

# Don't publish a "top project" derived from less time than this. Prevents a
# stray two-minute window from being reported as the week's main work.
EXPORT_MIN_TOP_PROJECT_SECS = 1800

DB_PATH = os.path.expanduser("~/.coding_tracker.db")
LOG_PATH = os.path.expanduser("~/.coding_tracker.log")
DASHBOARD_PATH = os.path.expanduser("~/.coding_tracker_dashboard.html")

# After a session is saved, wait this long (no new saves) before running push_stats.sh.
STATS_PUSH_DEBOUNCE_SECS = 90
