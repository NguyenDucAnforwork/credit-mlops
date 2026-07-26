#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

mkdir -p reports/generated reports/figures docs/evidence

rsync -az --prune-empty-dirs \
  --include='*/' \
  --include='reports/generated/*.json' \
  --include='reports/generated/*.csv' \
  --include='reports/generated/*.md' \
  --include='reports/figures/*.png' \
  --include='docs/evidence/*.txt' \
  --include='docs/evidence/*.json' \
  --exclude='*' \
  "$SSH_HOST:$REMOTE_WORKSPACE/" ./
