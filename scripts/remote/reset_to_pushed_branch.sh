#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

ssh "$SSH_HOST" "REMOTE_WORKSPACE=$(remote_quote "$REMOTE_WORKSPACE") FEATURE_BRANCH=$(remote_quote "$FEATURE_BRANCH") bash -s" <<'REMOTE'
set -euo pipefail
case "$REMOTE_WORKSPACE" in
  /home/ducan/credit-mlops-codex) ;;
  ""|/|/home/ducan) echo "Refusing unsafe REMOTE_WORKSPACE=$REMOTE_WORKSPACE" >&2; exit 65 ;;
  *) echo "Refusing unexpected REMOTE_WORKSPACE=$REMOTE_WORKSPACE" >&2; exit 65 ;;
esac
test -f "$REMOTE_WORKSPACE/.codex_remote_workspace"
cd "$REMOTE_WORKSPACE"
if [ ! -d .git ]; then
  echo "Remote workspace is rsync-only; skipping git reset."
  exit 0
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Refusing reset: tracked remote changes are present." >&2
  git status --short
  exit 66
fi
git fetch origin "$FEATURE_BRANCH"
git checkout "$FEATURE_BRANCH" || git checkout -b "$FEATURE_BRANCH" "origin/$FEATURE_BRANCH"
git reset --hard "origin/$FEATURE_BRANCH"
REMOTE
