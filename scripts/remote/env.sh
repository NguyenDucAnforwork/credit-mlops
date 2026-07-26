#!/usr/bin/env bash
set -euo pipefail

SSH_HOST="${SSH_HOST:-lfm}"
REMOTE_WORKSPACE="${REMOTE_WORKSPACE:-/home/ducan/credit-mlops-codex}"
FEATURE_BRANCH="${FEATURE_BRANCH:-feat/onemount-property-intelligence}"
GCP_PROJECT_ID="${GCP_PROJECT_ID:-driven-reef-452414-b5}"
GCP_REGION="${GCP_REGION:-asia-southeast1}"
GCP_ZONE="${GCP_ZONE:-asia-southeast1-a}"
GCP_VM_NAME="${GCP_VM_NAME:-lfm}"

remote_quote() {
  printf "%q" "$1"
}
