#!/usr/bin/env python3
"""Background daemon — polls the frontmost macOS app every POLL_INTERVAL_SECS seconds
and writes coding sessions to the SQLite database."""

import logging
import signal
import subprocess
import sys
import time
from datetime import datetime

from config import (
    APP_DISPLAY_NAMES,
    CODING_APPS,
    IDLE_THRESHOLD_SECS,
    LOG_PATH,
    POLL_INTERVAL_SECS,
)
from db import init_db, save_session

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# AppleScript that returns "AppName|Window Title" for the frontmost window.
_OSASCRIPT = """
tell application "System Events"
    set frontApp to name of first process whose frontmost is true
    set frontProc to first process whose frontmost is true
    try
        set winTitle to name of first window of frontProc
    on error
        set winTitle to ""
    end try
    return frontApp & "|" & winTitle
end tell
"""


def get_active_window() -> tuple[str, str]:
    """Returns (app_name, window_title). Returns ('', '') on any error."""
    try:
        result = subprocess.run(
            ["osascript", "-e", _OSASCRIPT],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0:
            return "", ""
        parts = result.stdout.strip().split("|", 1)
        app = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else ""
        return app, title
    except Exception as exc:
        logging.warning("get_active_window error: %s", exc)
        return "", ""


def extract_project(app: str, title: str) -> str | None:
    """Best-effort project name from window title."""
    if not title:
        return None

    import re

    # Cursor / VS Code: segments separated by em-dash (—) or spaced hyphen ( - )
    if app in ("Cursor", "Code", "Visual Studio Code"):
        parts = re.split(r"\s[—–-]\s", title)
        # Drop known app-name suffixes
        app_suffixes = {"Cursor", "Visual Studio Code", "Code", "Visual Studio"}
        parts = [p for p in parts if p.strip() not in app_suffixes]
        # Strip leading dirty-indicator (●) and whitespace
        parts = [re.sub(r"^[●•]\s*", "", p).strip() for p in parts if p.strip()]
        # Project is usually the last segment that isn't a filename (no extension)
        no_ext = [p for p in parts if "." not in p and "/" not in p and len(p) > 1]
        if no_ext:
            return no_ext[-1]
        if parts:
            return parts[-1].split("/")[-1]

    # Terminal / iTerm / Warp / Ghostty — title often contains the cwd
    if app in ("Terminal", "iTerm2", "iTerm", "Alacritty", "Warp", "Ghostty", "Hyper"):
        parts = re.split(r"\s[—–-]\s", title)
        last = parts[-1].strip() if parts else title.strip()
        # Path-like → take last component
        if "/" in last:
            return last.rstrip("/").split("/")[-1]
        # Skip generic shell names
        if last and last not in ("bash", "zsh", "fish", "sh", "ssh", "python", "python3", ""):
            return last

    return None


def friendly_name(app: str) -> str:
    return APP_DISPLAY_NAMES.get(app, app)


# --- Session state (module-level so signal handler can flush) ---------------

_session_app: str | None = None
_session_project: str | None = None
_session_start: datetime | None = None
_last_active: datetime | None = None


def _flush():
    global _session_app, _session_project, _session_start, _last_active
    if _session_app and _session_start and _last_active:
        save_session(
            app=friendly_name(_session_app),
            project=_session_project,
            started_at=_session_start,
            ended_at=_last_active,
        )
        dur = int((_last_active - _session_start).total_seconds())
        logging.info(
            "Saved: %s / %s — %ds", _session_app, _session_project, dur
        )
    _session_app = _session_project = _session_start = _last_active = None


def _shutdown(sig, frame):
    _flush()
    logging.info("Tracker stopped (signal %s)", sig)
    sys.exit(0)


# ---------------------------------------------------------------------------

def run():
    global _session_app, _session_project, _session_start, _last_active

    init_db()
    logging.info("Tracker started (pid=%s)", __import__("os").getpid())

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        now = datetime.now()
        app, title = get_active_window()
        is_coding = app in CODING_APPS

        if is_coding:
            project = extract_project(app, title)

            if _session_app is None:
                _session_app = app
                _session_project = project
                _session_start = now
                _last_active = now

            elif app != _session_app:
                # Switched to a different coding app — flush and start fresh
                _flush()
                _session_app = app
                _session_project = project
                _session_start = now
                _last_active = now

            else:
                gap = (now - _last_active).total_seconds()
                if gap > IDLE_THRESHOLD_SECS:
                    # Long gap (screen lock, away, etc.) — treat as new session
                    _flush()
                    _session_app = app
                    _session_project = project
                    _session_start = now
                # Backfill project when we eventually detect it
                if project and not _session_project:
                    _session_project = project
                _last_active = now

        else:
            # Non-coding app in focus — end session after idle threshold
            if _session_app and _last_active:
                gap = (now - _last_active).total_seconds()
                if gap > IDLE_THRESHOLD_SECS:
                    _flush()

        time.sleep(POLL_INTERVAL_SECS)


if __name__ == "__main__":
    run()
