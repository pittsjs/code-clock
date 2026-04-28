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

git commit -m "chore: update stats [skip ci]"
git push
echo "Stats pushed to GitHub"
