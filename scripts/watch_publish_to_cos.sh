#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# coscli reads /home/ubuntu/.cos.yaml by default. Set COSCLI if installed elsewhere.

# Usage: ./scripts/watch_publish_to_cos.sh [poll_seconds]
INTERVAL="${1:-30}"
LAST_SIGNATURE=""

while true; do
  SIGNATURE="$(find -L content -type f -printf '%T@:%s:%p\n' 2>/dev/null | LC_ALL=C sort | sha256sum | cut -d' ' -f1)"
  if [[ -n "$SIGNATURE" && "$SIGNATURE" != "$LAST_SIGNATURE" ]]; then
    echo "[$(date -Is)] content changed; waiting for sync settle..."
    sleep 5
    NEW_SIGNATURE="$(find -L content -type f -printf '%T@:%s:%p\n' 2>/dev/null | LC_ALL=C sort | sha256sum | cut -d' ' -f1)"
    if [[ "$NEW_SIGNATURE" != "$SIGNATURE" ]]; then
      echo "[$(date -Is)] content still changing; will retry next cycle"
      sleep "$INTERVAL"
      continue
    fi
    if ./scripts/publish_to_cos.sh; then
      LAST_SIGNATURE="$NEW_SIGNATURE"
      echo "[$(date -Is)] COS and GitHub Pages publication complete"
    else
      echo "[$(date -Is)] publication failed; will retry on the next cycle" >&2
    fi
  fi
  sleep "$INTERVAL"
done
