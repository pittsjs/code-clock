#!/usr/bin/env bash
# Commit-msg hook: every commit on this repo must start with "vX.Y.Z:".
# Installed by install.sh into .git/hooks/commit-msg.

msg_file="$1"
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
