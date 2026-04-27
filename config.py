import os

CODING_APPS = {
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

DB_PATH = os.path.expanduser("~/.coding_tracker.db")
LOG_PATH = os.path.expanduser("~/.coding_tracker.log")
DASHBOARD_PATH = os.path.expanduser("~/.coding_tracker_dashboard.html")
