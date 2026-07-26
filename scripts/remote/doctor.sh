#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_HOST" "REMOTE_WORKSPACE=$(remote_quote "$REMOTE_WORKSPACE") GCP_PROJECT_ID=$(remote_quote "$GCP_PROJECT_ID") bash -s" <<'REMOTE'
set -euo pipefail
echo "=== SSH ==="
printf "SSH_OK\n"
whoami
hostname
pwd

echo "=== WORKSPACE ==="
if [ -d "$REMOTE_WORKSPACE" ]; then
  echo "$REMOTE_WORKSPACE exists"
else
  echo "MISSING: $REMOTE_WORKSPACE"
fi
if [ -f "$REMOTE_WORKSPACE/.codex_remote_workspace" ]; then
  echo "sentinel: ok"
else
  echo "MISSING: $REMOTE_WORKSPACE/.codex_remote_workspace"
fi

echo "=== OS ==="
cat /etc/os-release | sed -n '1,8p'
echo "=== CPU ==="
nproc
lscpu | sed -n '1,12p'
echo "=== MEMORY ==="
free -h
echo "=== DISK ==="
df -h /
echo "=== TOOLS ==="
for tool in git docker docker-compose gcloud terraform uv python3 rsync curl; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf "%-16s %s\n" "$tool" "$(command -v "$tool")"
  else
    printf "%-16s MISSING\n" "$tool"
  fi
done
echo "=== DOCKER ==="
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}' 2>/dev/null || echo "Docker unavailable or permission denied"
echo "=== GCP ==="
gcloud auth list 2>&1 || true
gcloud config get-value project 2>&1 || true
gcloud services list --project "$GCP_PROJECT_ID" --limit=1 >/dev/null 2>&1 && echo "gcloud services access: ok" || echo "gcloud services access: blocked"
REMOTE
