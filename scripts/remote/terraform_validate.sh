#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUN_ID="${RUN_ID:-20260726}"
STDOUT="docs/evidence/phase6_terraform_validate_${RUN_ID}.txt"
RUNTIME="docs/evidence/phase6_terraform_validate_runtime_${RUN_ID}.txt"
TF_VERSION="${TF_VERSION:-1.9.8}"

cd "$REPO_ROOT"

echo "=== local secret/path scan ==="
CHANGED_FILES="$(
  {
    git diff --name-only HEAD --
    git ls-files -o --exclude-standard
  } | sort -u
)"

if printf '%s\n' "$CHANGED_FILES" | rg '(^|/)(data|models|mlruns|\.terraform|terraform\.tfstate|terraform\.tfstate\.backup|\.env|secrets?|credentials?|service-account|\.parquet|\.pkl|\.joblib|\.db|\.sqlite|\.duckdb)(/|$)|\.(parquet|pkl|joblib|db|sqlite|duckdb)$'; then
  echo "Refusing Terraform validation with forbidden local changed artifact path." >&2
  exit 66
fi

if printf '%s\n' "$CHANGED_FILES" \
    | rg -v '^reports/nannyml/.*\.html$' \
    | xargs -r rg -n -I '(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|-----BEGIN (RSA |EC |OPENSSH |PRIVATE )?PRIVATE KEY-----|xox[baprs]-[0-9A-Za-z-]+|ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{20,}|ya29\.[0-9A-Za-z_-]+)' ; then
  echo "Refusing Terraform validation because a secret-like pattern was found." >&2
  exit 67
fi

"$SCRIPT_DIR/sync_to_vm.sh"

"$SCRIPT_DIR/run.sh" "set -euo pipefail; \
  if ! command -v terraform >/dev/null 2>&1; then \
    mkdir -p \"\$HOME/.local/bin\" \"\$HOME/.cache/codex-tools\"; \
    cd \"\$HOME/.cache/codex-tools\"; \
    curl -fsSLo terraform.zip \"https://releases.hashicorp.com/terraform/$TF_VERSION/terraform_${TF_VERSION}_linux_amd64.zip\"; \
    python3 - <<'PY'
import zipfile
from pathlib import Path
zipfile.ZipFile('terraform.zip').extractall(Path.home() / '.local' / 'bin')
PY
    chmod +x \"\$HOME/.local/bin/terraform\"; \
    cd /home/ducan/credit-mlops-codex; \
  fi; \
  mkdir -p docs/evidence; start=\$(date +%s); \
  { terraform -chdir=infra/terraform fmt -check -recursive && \
    terraform -chdir=infra/terraform init -backend=false -no-color && \
    terraform -chdir=infra/terraform validate -no-color; } 2>&1 | tee $STDOUT; \
  status=\${PIPESTATUS[0]}; \
  end=\$(date +%s); \
  printf 'terraform_validate_exit=%s\nruntime_seconds=%s\n' \"\$status\" \"\$((end-start))\" | tee $RUNTIME; \
  exit \"\$status\""

rsync -az lfm:/home/ducan/credit-mlops-codex/infra/terraform/.terraform.lock.hcl infra/terraform/.terraform.lock.hcl
"$SCRIPT_DIR/fetch_artifacts.sh"
