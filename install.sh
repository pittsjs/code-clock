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

render_launchd_plist() {
  local template_path="$1"
  local dest_path="$2"
  "$PYTHON" - "$SCRIPT_DIR" "$HOME" "$PYTHON" "$template_path" "$dest_path" <<'PY'
import pathlib
import sys

script_dir, home, py, src, dst = sys.argv[1:6]
text = pathlib.Path(src).read_text(encoding="utf-8")
text = text.replace("__SCRIPT_DIR__", script_dir)
text = text.replace("__HOME__", home)
text = text.replace("__PYTHON__", py)
pathlib.Path(dst).write_text(text, encoding="utf-8")
PY
}

echo "==> Writing launchd plist to $PLIST_DEST"
render_launchd_plist "$SCRIPT_DIR/templates/launchd/com.user.codingtracker.plist" "$PLIST_DEST"

echo "==> Loading daemon..."
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "==> Writing nightly stats plist to $STATS_PLIST_DEST"
render_launchd_plist "$SCRIPT_DIR/templates/launchd/com.user.codingtracker.stats.plist" "$STATS_PLIST_DEST"

echo "==> Loading stats job..."
launchctl unload "$STATS_PLIST_DEST" 2>/dev/null || true
launchctl load "$STATS_PLIST_DEST"

# Git hooks (this repo only)
if [ -d "$SCRIPT_DIR/.git" ]; then
    chmod +x "$SCRIPT_DIR/scripts/commit-msg-hook.sh"
    cp "$SCRIPT_DIR/scripts/commit-msg-hook.sh" "$SCRIPT_DIR/.git/hooks/commit-msg"
    chmod +x "$SCRIPT_DIR/.git/hooks/commit-msg"
    rm -f "$SCRIPT_DIR/.git/hooks/prepare-commit-msg"
    echo "==> Installed commit-msg hook (strip IDE footers; enforce vX.Y.Z prefix)"
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
echo "Tip: install GitHub CLI (\`gh\`) and run \`gh auth login\` once so each"
echo "stats push can trigger your profile README workflow immediately."
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
