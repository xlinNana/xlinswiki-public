#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${XLINSWIKI_PUBLISHED_DIR:-/home/ubuntu/xlinswiki/context/03-Published}"
DEST="$ROOT/content-github"
REMOTE="${XLINSWIKI_GITHUB_REMOTE:-github}"
BRANCH="${XLINSWIKI_GITHUB_BRANCH:-main}"

cd "$ROOT"

if [[ ! -d "$SOURCE" ]]; then
  echo "GitHub publication source does not exist: $SOURCE" >&2
  exit 2
fi

# Keep only Markdown in the GitHub publication tree. Binary attachments remain
# in Tencent COS and are converted to COS URLs by the workflow before building.
mkdir -p "$DEST"
find "$DEST" -type f ! -name '*.md' -delete
find "$DEST" -depth -type d -empty -delete

# Mirror the published Markdown tree, including deletions, without following
# the content symlink itself or copying any attachments.
find "$DEST" -type f -name '*.md' -delete
while IFS= read -r -d '' source_file; do
  relative="${source_file#"$SOURCE"/}"
  target="$DEST/$relative"
  mkdir -p "$(dirname "$target")"
  cp -- "$source_file" "$target"
done < <(find "$SOURCE" -type f -name '*.md' -print0)

# Stage the complete publication tree first. `git diff --quiet` alone does not
# detect newly created untracked Markdown files.
git add -A -- content-github
if git diff --cached --quiet -- content-github; then
  echo "GitHub publication content unchanged"
  exit 0
fi

commit_message="Sync published Markdown to GitHub Pages"
git commit -m "$commit_message" -- content-github

# The Pages repository is intentionally maintained as an independent generated
# publication branch. The local Quartz checkout has shallow/upstream-derived
# ancestry that GitHub cannot always receive, so publish the exact current tree
# as a fresh root commit rather than pushing that ancestry.
git fetch "$REMOTE" "$BRANCH"
old_remote="$(git rev-parse "$REMOTE/$BRANCH")"
publication_tree="$(git rev-parse HEAD^{tree})"
publication_commit="$(printf '%s\n' "$commit_message" | git commit-tree "$publication_tree")"
git push --force-with-lease="refs/heads/$BRANCH:$old_remote" \
  "$REMOTE" "$publication_commit:refs/heads/$BRANCH"

echo "GitHub Pages publication pushed: ${publication_commit:0:7}"
