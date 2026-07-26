#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

case "$REMOTE_WORKSPACE" in
  /home/ducan/credit-mlops-codex) ;;
  ""|/|/home/ducan) echo "Refusing unsafe REMOTE_WORKSPACE=$REMOTE_WORKSPACE" >&2; exit 65 ;;
  *) echo "Refusing unexpected REMOTE_WORKSPACE=$REMOTE_WORKSPACE" >&2; exit 65 ;;
esac

ssh "$SSH_HOST" "test -f $(remote_quote "$REMOTE_WORKSPACE/.codex_remote_workspace")"

rsync -az --delete \
  --exclude='.git/' \
  --exclude='.codex_remote_workspace' \
  --exclude='.env' \
  --exclude='.env.*' \
  --include='.env.example' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='node_modules/' \
  --exclude='data/raw/' \
  --exclude='data/bronze/' \
  --exclude='data/silver/' \
  --exclude='data/gold/' \
  --exclude='data/quarantine/' \
  --exclude='data/processed/' \
  --exclude='artifacts/models/' \
  --exclude='mlruns/' \
  --exclude='mlartifacts/' \
  --exclude='terraform.tfstate' \
  --exclude='terraform.tfstate.*' \
  --exclude='*.tfplan' \
  --exclude='secrets/' \
  ./ "$SSH_HOST:$REMOTE_WORKSPACE/"

ssh "$SSH_HOST" "touch $(remote_quote "$REMOTE_WORKSPACE/.codex_remote_workspace")"
