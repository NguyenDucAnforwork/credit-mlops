#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUN_ID="${RUN_ID:-20260726}"
EVIDENCE="docs/evidence/remote_reproduce_smoke_${RUN_ID}.txt"
RUNTIME="docs/evidence/remote_reproduce_smoke_runtime_${RUN_ID}.txt"

cd "$REPO_ROOT"

echo "=== local secret/path scan ==="
CHANGED_FILES="$(
  {
    git diff --name-only HEAD --
    git ls-files -o --exclude-standard
  } | sort -u
)"

if printf '%s\n' "$CHANGED_FILES" | rg '(^|/)(data|models|mlruns|\.terraform|terraform\.tfstate|terraform\.tfstate\.backup|\.env|secrets?|credentials?|service-account|\.parquet|\.pkl|\.joblib|\.db|\.sqlite|\.duckdb)(/|$)|\.(parquet|pkl|joblib|db|sqlite|duckdb)$'; then
  echo "Refusing smoke run with forbidden local changed artifact path." >&2
  exit 66
fi

if printf '%s\n' "$CHANGED_FILES" \
    | rg -v '^reports/nannyml/.*\.html$' \
    | xargs -r rg -n -I '(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|-----BEGIN (RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----|xox[baprs]-[0-9A-Za-z-]+|ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{20,}|ya29\.[0-9A-Za-z_-]+)' ; then
  echo "Refusing smoke run because a secret-like pattern was found." >&2
  exit 67
fi

"$SCRIPT_DIR/sync_to_vm.sh"

"$SCRIPT_DIR/run.sh" "mkdir -p docs/evidence; start=\$(date +%s); {
  echo '=== smoke: imports and syntax ==='
  uv run python -m py_compile \
    api/main.py \
    api/property_service.py \
    scripts/property_avm_artifact.py \
    scripts/property_api_http_benchmark.py \
    ui/streamlit_app.py \
    ui/property_workflow.py
  echo '=== smoke: focused contract tests ==='
  uv run pytest -q \
    tests/test_property_etl.py \
    tests/test_hf_etl.py \
    tests/test_contracts_property.py \
    tests/test_comparables.py \
    tests/test_avm.py \
    tests/test_lifecycle_avm.py \
    tests/test_property_monitoring.py \
    tests/test_api.py \
    tests/test_ui_property_workflow.py
  echo '=== smoke: blockers intentionally skipped ==='
  echo 'docker=skipped: VM docker socket/compose access blocked'
  echo 'gcp=skipped: VM access token scope insufficient'
} | tee $EVIDENCE; status=\${PIPESTATUS[0]}; end=\$(date +%s); printf 'remote_reproduce_smoke_exit=%s\nruntime_seconds=%s\n' \"\$status\" \"\$((end-start))\" | tee $RUNTIME; exit \"\$status\""

"$SCRIPT_DIR/fetch_artifacts.sh"
