#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

cd "$SCRIPT_DIR"

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ "$branch" != "main" ]; then
  echo "Not on main (branch=$branch), skipping stats push"
  exit 0
fi

git fetch origin main 2>/dev/null || true
if git rev-parse -q --verify refs/remotes/origin/main >/dev/null 2>&1; then
  git pull --rebase --autostash origin main || {
    echo "stats push: git pull --rebase origin main failed" >&2
    exit 1
  }
fi

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

# Immediately refresh profile README — uses GitHub CLI if available (launchd often has no PATH).
GH_BIN="$(command -v gh 2>/dev/null || true)"
[ -z "$GH_BIN" ] && [ -x /opt/homebrew/bin/gh ] && GH_BIN=/opt/homebrew/bin/gh
[ -z "$GH_BIN" ] && [ -x /usr/local/bin/gh ] && GH_BIN=/usr/local/bin/gh

_profile_repo="${PROFILE_STATS_DISPATCH_REPO:-pittsjs/pittsjs}"
_event="${PROFILE_STATS_DISPATCH_EVENT:-coding-stats-updated}"
if [ "${PROFILE_STATS_DISABLE_DISPATCH:-0}" != "1" ] && [ -n "$GH_BIN" ]; then
  if printf '%s\n' "{\"event_type\":\"${_event}\"}" | "$GH_BIN" api \
      --method POST \
      "repos/${_profile_repo}/dispatches" \
      --input - >/dev/null 2>&1; then
    echo "Dispatched profile workflow (${_profile_repo})"
  fi
fi
