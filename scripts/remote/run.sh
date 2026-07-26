#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 '<remote command>'" >&2
  exit 64
fi

REMOTE_COMMAND="$1"
printf '[%s] ssh %s cd %s && <command>\n' "$(date -Iseconds)" "$SSH_HOST" "$REMOTE_WORKSPACE" >&2

ssh "$SSH_HOST" "cd $(remote_quote "$REMOTE_WORKSPACE") && set -euo pipefail && export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\" && $REMOTE_COMMAND"
