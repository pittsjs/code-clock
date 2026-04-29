#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
PLIST_LABEL="com.user.codingtracker"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
STATS_PLIST_LABEL="com.user.codingtracker.stats"
STATS_PLIST_DEST="$HOME/Library/LaunchAgents/$STATS_PLIST_LABEL.plist"

echo "==> Creating virtual environment..."
python3 -m venv "$VENV"
PYTHON="$VENV/bin/python"

echo "==> Installing Python dependencies..."
"$PYTHON" -m pip install -q --upgrade click rich

echo "==> Writing launchd plist to $PLIST_DEST"
cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SCRIPT_DIR}/tracker.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/.coding_tracker_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.coding_tracker_stderr.log</string>
</dict>
</plist>
EOF

echo "==> Loading daemon..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "==> Writing nightly stats plist to $STATS_PLIST_DEST"
cat > "$STATS_PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${STATS_PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/scripts/push_stats.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>WatchPaths</key>
    <array>
        <string>${HOME}/.coding_tracker.db</string>
        <string>${HOME}/.coding_tracker.db-wal</string>
        <string>${HOME}/.coding_tracker.db-shm</string>
    </array>
    <key>ThrottleInterval</key>
    <integer>300</integer>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>13</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>20</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
    </array>
    <key>StandardOutPath</key>
    <string>${HOME}/.coding_tracker_stats_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.coding_tracker_stats_stderr.log</string>
</dict>
</plist>
EOF

echo "==> Loading stats job..."
launchctl unload "$STATS_PLIST_DEST" 2>/dev/null || true
launchctl load "$STATS_PLIST_DEST"

# Install commit-msg hook to enforce vX.Y.Z prefix on every commit.
if [ -d "$SCRIPT_DIR/.git" ]; then
    HOOK_SRC="$SCRIPT_DIR/scripts/commit-msg-hook.sh"
    HOOK_DEST="$SCRIPT_DIR/.git/hooks/commit-msg"
    chmod +x "$HOOK_SRC"
    cp "$HOOK_SRC" "$HOOK_DEST"
    chmod +x "$HOOK_DEST"
    echo "==> Installed commit-msg hook (enforces vX.Y.Z prefix)"
fi

# Add shell alias (always uses the venv python)
ALIAS_LINE="alias coding-time='${VENV}/bin/python ${SCRIPT_DIR}/cli.py'"
SHELL_RC="$HOME/.zshrc"
[ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"

if ! grep -qF "coding-time" "$SHELL_RC" 2>/dev/null; then
    printf '\n# Coding time tracker\n%s\n' "$ALIAS_LINE" >> "$SHELL_RC"
    echo "==> Added 'coding-time' alias to $SHELL_RC"
else
    echo "==> 'coding-time' alias already in $SHELL_RC"
fi

echo ""
echo "✓ Done! Tracker is running in the background."
echo ""
echo "Open a new terminal tab, then try:"
echo "  coding-time today       — today's summary"
echo "  coding-time week        — last 7 days"
echo "  coding-time projects    — per-project breakdown"
echo "  coding-time dashboard   — open HTML dashboard"
echo "  coding-time export      — export JSON (for GitHub)"
echo "  coding-time status      — check daemon health"
echo ""
echo "Note: macOS will prompt for Accessibility permission the first"
echo "time the tracker runs. Allow it in System Settings → Privacy."
