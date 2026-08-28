#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Prevent overlapping COS/GitHub publications if the watcher is restarted.
exec 9>"$ROOT/.publish.lock"
flock -n 9 || {
  echo "another XLinsWiki publication is already running" >&2
  exit 0
}

# coscli reads /home/ubuntu/.cos.yaml by default. Set COSCLI if installed elsewhere.
# Usage: ./scripts/publish_to_cos.sh

# The source vault is authoritative. Assign missing stable publication metadata
# before either local/Caddy or GitHub Pages builds consume the Markdown.
python3 scripts/ensure_publish_metadata.py /home/ubuntu/xlinswiki/context/03-Published

# Build the canonical local/Caddy output and COS media publication first.
# The checked-in quartz.config.yaml is the GitHub Pages configuration; use the
# separate default configuration for the CVM build so local links and metadata
# point at xlinswiki.cn, then restore the GitHub configuration afterwards.
CONFIG_BACKUP="$(mktemp)"
cp quartz.config.yaml "$CONFIG_BACKUP"
restore_config() {
  cp "$CONFIG_BACKUP" quartz.config.yaml
  rm -f "$CONFIG_BACKUP"
}
trap restore_config EXIT
cp quartz.config.default.yaml quartz.config.yaml
python3 scripts/patch_explorer_hierarchy.py
npm run quartz -- build
./scripts/build_font_subset.sh
npm run quartz -- build
python3 scripts/sync_cos.py

# The GitHub Pages branch receives only Markdown; its Actions workflow rewrites
# relative media references to the same COS objects before building.
./scripts/sync_to_github_pages.sh
