#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUN_ID="${RUN_ID:-20260726}"
STDOUT="docs/evidence/phase7_type_smoke_stdout_${RUN_ID}.txt"
RUNTIME="docs/evidence/phase7_type_smoke_runtime_${RUN_ID}.txt"

cd "$REPO_ROOT"

echo "=== local secret/path scan ==="
CHANGED_FILES="$(
  {
    git diff --name-only HEAD --
    git ls-files -o --exclude-standard
  } | sort -u
)"

if printf '%s\n' "$CHANGED_FILES" | rg '(^|/)(data|models|mlruns|\.terraform|terraform\.tfstate|terraform\.tfstate\.backup|\.env|secrets?|credentials?|service-account|\.parquet|\.pkl|\.joblib|\.db|\.sqlite|\.duckdb)(/|$)|\.(parquet|pkl|joblib|db|sqlite|duckdb)$'; then
  echo "Refusing type smoke with forbidden local changed artifact path." >&2
  exit 66
fi

if printf '%s\n' "$CHANGED_FILES" \
    | rg -v '^reports/nannyml/.*\.html$' \
    | xargs -r rg -n -I '(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|-----BEGIN (RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----|xox[baprs]-[0-9A-Za-z-]+|ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{20,}|ya29\.[0-9A-Za-z_-]+)' ; then
  echo "Refusing type smoke because a secret-like pattern was found." >&2
  exit 67
fi

"$SCRIPT_DIR/sync_to_vm.sh"

"$SCRIPT_DIR/run.sh" "mkdir -p docs/evidence; start=\$(date +%s); \
  uvx mypy==1.18.2 --ignore-missing-imports --follow-imports=silent \
    src/property_intelligence api \
    scripts/property_api_smoke.py \
    scripts/property_monitoring_drift.py \
    scripts/property_avm_promotion_gate.py | tee $STDOUT; \
  status=\${PIPESTATUS[0]}; \
  end=\$(date +%s); \
  printf 'type_smoke_exit=%s\nruntime_seconds=%s\n' \"\$status\" \"\$((end-start))\" | tee $RUNTIME; \
  exit \"\$status\""

"$SCRIPT_DIR/fetch_artifacts.sh"
