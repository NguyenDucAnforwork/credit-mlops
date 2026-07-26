#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

RUN_ID="${RUN_ID:-20260726}"
COMPOSE_VERSION="${COMPOSE_VERSION:-v5.3.1}"
STDOUT="docs/evidence/phase6_compose_smoke_${RUN_ID}.txt"
RUNTIME="docs/evidence/phase6_compose_smoke_runtime_${RUN_ID}.txt"

"$SCRIPT_DIR/sync_to_vm.sh"

"$SCRIPT_DIR/run.sh" "mkdir -p docs/evidence; start=\$(date +%s); {
  set -euo pipefail
  mkdir -p \"\$HOME/.docker/cli-plugins\"
  if ! docker compose version >/dev/null 2>&1; then
    arch=\$(uname -m)
    case \"\$arch\" in
      x86_64) compose_arch=x86_64 ;;
      aarch64|arm64) compose_arch=aarch64 ;;
      *) echo \"unsupported_compose_arch=\$arch\"; exit 2 ;;
    esac
    curl -fL --retry 3 -o \"\$HOME/.docker/cli-plugins/docker-compose\" \
      \"https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-\${compose_arch}\"
    chmod +x \"\$HOME/.docker/cli-plugins/docker-compose\"
  fi

  docker compose version
  if [ ! -f .env ]; then
    printf '# VM-only default env for Codex Compose smoke. No secrets.\\n' > .env
  fi

  export COMPOSE_PROJECT_NAME=credit_mlops_codex_smoke
  docker compose config --quiet
  docker compose build api ui
  docker compose up -d postgres redis api ui

  for i in \$(seq 1 45); do
    api_status=\$(docker compose ps api --format '{{.Health}}' 2>/dev/null || true)
    ui_status=\$(docker compose ps ui --format '{{.Health}}' 2>/dev/null || true)
    postgres_status=\$(docker compose ps postgres --format '{{.Health}}' 2>/dev/null || true)
    redis_status=\$(docker compose ps redis --format '{{.Health}}' 2>/dev/null || true)
    echo \"health_poll_\${i}=api:\${api_status:-unknown},ui:\${ui_status:-unknown},postgres:\${postgres_status:-unknown},redis:\${redis_status:-unknown}\"
    if [ \"\$api_status\" = healthy ] && [ \"\$ui_status\" = healthy ] && [ \"\$postgres_status\" = healthy ] && [ \"\$redis_status\" = healthy ]; then
      break
    fi
    sleep 4
  done

  docker compose ps
  curl -fsS http://127.0.0.1:8000/health
  echo
  curl -fsS http://127.0.0.1:8501/_stcore/health
  echo
  docker compose down -v --remove-orphans
} 2>&1 | tee $STDOUT; status=\${PIPESTATUS[0]}; end=\$(date +%s); printf 'compose_smoke_exit=%s\\nruntime_seconds=%s\\n' \"\$status\" \"\$((end-start))\" | tee $RUNTIME; exit \"\$status\""

"$SCRIPT_DIR/fetch_artifacts.sh"
