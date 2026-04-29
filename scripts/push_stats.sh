#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

cd "$SCRIPT_DIR"

"$PYTHON" cli.py export -o stats.json

git add stats.json

if git diff --cached --quiet; then
  echo "Stats unchanged, nothing to push"
  exit 0
fi

# Derive next version by bumping the patch on the most recent vX.Y.Z
# tag found in commit subjects. Keeps every commit on main versioned.
LAST_VER=$(git log --pretty=%s -100 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
if [ -z "$LAST_VER" ]; then
  NEXT_VER="v1.0.0"
else
  NEXT_VER=$(echo "$LAST_VER" | awk -F. '{print $1"."$2"."$3+1}')
fi

git commit -m "$NEXT_VER: update stats [skip ci]"
git push
echo "Stats pushed to GitHub as $NEXT_VER"
