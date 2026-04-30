#!/usr/bin/env bash
# commit-msg: strip IDE footers, then enforce vX.Y.Z on first line (this repo only).
# Installed by install.sh into .git/hooks/commit-msg.

msg_file="${1:?}"

python3 - "$msg_file" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    text = path.read_text(encoding="utf-8")
except OSError:
    sys.exit(0)

lines = []
for line in text.splitlines(keepends=True):
    stripped = line.strip()
    low = stripped.lower()
    if low.startswith("made with:") and "cursor" in low:
        continue
    lines.append(line)

path.write_text("".join(lines), encoding="utf-8")
PY

first_line=$(head -n1 "$msg_file")

# Allow merge commits and revert commits to bypass the rule.
case "$first_line" in
    "Merge "*|"Revert "*) exit 0 ;;
esac

if ! [[ "$first_line" =~ ^v[0-9]+\.[0-9]+\.[0-9]+: ]]; then
    echo "✗ Commit rejected: message must start with a version number." >&2
    echo "  Expected format: 'vX.Y.Z: <summary>'" >&2
    echo "  Got:             '$first_line'" >&2
    echo "" >&2
    echo "  Pick the next version by bumping from the latest in 'git log'." >&2
    exit 1
fi
