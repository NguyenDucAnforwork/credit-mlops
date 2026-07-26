#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

REPO_URL="$(git remote get-url origin)"

ssh "$SSH_HOST" "REMOTE_WORKSPACE=$(remote_quote "$REMOTE_WORKSPACE") REPO_URL=$(remote_quote "$REPO_URL") FEATURE_BRANCH=$(remote_quote "$FEATURE_BRANCH") bash -s" <<'REMOTE'
set -euo pipefail

case "$REMOTE_WORKSPACE" in
  /home/ducan/credit-mlops-codex) ;;
  *) echo "Refusing unexpected REMOTE_WORKSPACE=$REMOTE_WORKSPACE" >&2; exit 65 ;;
esac

mkdir -p "$(dirname "$REMOTE_WORKSPACE")"
if [ ! -d "$REMOTE_WORKSPACE/.git" ] && [ ! -f "$REMOTE_WORKSPACE/.codex_remote_workspace" ]; then
  git clone "$REPO_URL" "$REMOTE_WORKSPACE" || {
    echo "Git clone failed. Creating dedicated rsync workspace instead." >&2
    mkdir -p "$REMOTE_WORKSPACE"
  }
fi
touch "$REMOTE_WORKSPACE/.codex_remote_workspace"

cd "$REMOTE_WORKSPACE"
if [ -d .git ]; then
  git fetch origin || true
  if git show-ref --verify --quiet "refs/remotes/origin/$FEATURE_BRANCH"; then
    git checkout "$FEATURE_BRANCH" || git checkout -b "$FEATURE_BRANCH" "origin/$FEATURE_BRANCH"
  elif git show-ref --verify --quiet "refs/heads/$FEATURE_BRANCH"; then
    git checkout "$FEATURE_BRANCH"
  fi
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv in the remote user environment."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "MISSING: uv after user-level install attempt." >&2
  exit 69
fi

if [ ! -f pyproject.toml ]; then
  echo "Workspace is ready but source has not been synced yet; skipping dependency sync."
  exit 0
fi

uv sync --frozen --all-extras --dev
REMOTE
