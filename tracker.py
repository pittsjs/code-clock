#!/usr/bin/env python3
"""Background daemon — polls the frontmost macOS app every POLL_INTERVAL_SECS seconds
and writes coding sessions to the SQLite database."""

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

from config import (
    APP_DISPLAY_NAMES,
    CODING_APPS,
    IDLE_THRESHOLD_SECS,
    LOG_PATH,
    POLL_INTERVAL_SECS,
    STATS_PUSH_DEBOUNCE_SECS,
)
from db import init_db, save_session

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_PUSH_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "push_stats.sh")
_STATS_OUT_LOG = os.path.expanduser("~/.coding_tracker_stats_stdout.log")
_STATS_ERR_LOG = os.path.expanduser("~/.coding_tracker_stats_stderr.log")

_stats_push_timer: threading.Timer | None = None
_stats_push_lock = threading.Lock()

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def get_active_window() -> tuple[str, str]:
    """Returns (app_name, window_title) using native macOS APIs."""
    try:
        from AppKit import NSWorkspace
        from Foundation import NSRunLoop, NSDate
        import ApplicationServices as AX

        # Pump the run loop so NSWorkspace sees the latest frontmost app.
        NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))

        ws = NSWorkspace.sharedWorkspace()
        app = ws.frontmostApplication()
        if app is None:
            return "", ""

        app_name = app.localizedName()
        pid = app.processIdentifier()

        # Get window title via Accessibility API (requires Accessibility permission)
        ax_app = AX.AXUIElementCreateApplication(pid)
        err, windows = AX.AXUIElementCopyAttributeValue(ax_app, "AXWindows", None)
        if err == 0 and windows:
            err, title = AX.AXUIElementCopyAttributeValue(windows[0], "AXTitle", None)
            if err == 0 and title:
                return app_name, title

        return app_name, ""
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
        _schedule_stats_push()
    _session_app = _session_project = _session_start = _last_active = None


def _cancel_stats_push_timer():
    global _stats_push_timer
    with _stats_push_lock:
        if _stats_push_timer is not None:
            _stats_push_timer.cancel()
            _stats_push_timer = None


def _run_stats_push_background():
    if not os.path.isfile(_PUSH_SCRIPT):
        return
    try:
        out = open(_STATS_OUT_LOG, "a", encoding="utf-8")
        err = open(_STATS_ERR_LOG, "a", encoding="utf-8")
    except OSError as exc:
        logging.warning("stats push logs: %s", exc)
        out = err = subprocess.DEVNULL
    try:
        subprocess.Popen(
            ["/bin/bash", _PUSH_SCRIPT],
            cwd=_REPO_ROOT,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        if out is not subprocess.DEVNULL:
            out.close()
        if err is not subprocess.DEVNULL and err is not out:
            err.close()
    except OSError as exc:
        logging.warning("stats push could not start: %s", exc)
        if out is not subprocess.DEVNULL:
            try:
                out.close()
            except OSError:
                pass
        if err is not subprocess.DEVNULL:
            try:
                err.close()
            except OSError:
                pass


def _schedule_stats_push():
    global _stats_push_timer

    def _fire():
        global _stats_push_timer
        with _stats_push_lock:
            _stats_push_timer = None
        _run_stats_push_background()

    with _stats_push_lock:
        if _stats_push_timer is not None:
            _stats_push_timer.cancel()
        _stats_push_timer = threading.Timer(STATS_PUSH_DEBOUNCE_SECS, _fire)
        _stats_push_timer.daemon = True
        _stats_push_timer.start()


def _shutdown(sig, frame):
    _cancel_stats_push_timer()
    _flush()
    _cancel_stats_push_timer()
    if os.path.isfile(_PUSH_SCRIPT):
        try:
            out = open(_STATS_OUT_LOG, "a", encoding="utf-8")
            err = open(_STATS_ERR_LOG, "a", encoding="utf-8")
        except OSError as exc:
            logging.warning("final stats push logs: %s", exc)
            out = err = subprocess.DEVNULL
        try:
            subprocess.run(
                ["/bin/bash", _PUSH_SCRIPT],
                cwd=_REPO_ROOT,
                stdout=out,
                stderr=err,
                timeout=180,
                check=False,
            )
        finally:
            if out is not subprocess.DEVNULL:
                out.close()
            if err is not subprocess.DEVNULL:
                err.close()
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
