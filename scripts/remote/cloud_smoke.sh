#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$SCRIPT_DIR/env.sh"

RUN_ID="${RUN_ID:-20260726}"
STDOUT="docs/evidence/phase6_gcp_readonly_smoke_${RUN_ID}.txt"
RUNTIME="docs/evidence/phase6_gcp_readonly_smoke_runtime_${RUN_ID}.txt"

"$SCRIPT_DIR/sync_to_vm.sh"

set +e
"$SCRIPT_DIR/run.sh" "mkdir -p docs/evidence; start=\$(date +%s); set +e; {
  set +e
  overall=0
  echo \"gcp_readonly_started=\$(date -Is)\"
  echo '=== auth list ==='
  gcloud auth list
  cmd_status=\$?
  echo \"auth_exit=\$cmd_status\"
  [ \"\$cmd_status\" -eq 0 ] || overall=1

  echo '=== project config ==='
  gcloud config get-value project
  cmd_status=\$?
  echo \"project_config_exit=\$cmd_status\"
  [ \"\$cmd_status\" -eq 0 ] || overall=1

  echo '=== services list cloudrun/artifactregistry/serviceusage/resource manager ==='
  gcloud services list --project ${GCP_PROJECT_ID} \
    --filter='name:(run.googleapis.com OR artifactregistry.googleapis.com OR serviceusage.googleapis.com OR cloudresourcemanager.googleapis.com)' \
    --format='table(name,title,state)'
  cmd_status=\$?
  echo \"services_filter_exit=\$cmd_status\"
  [ \"\$cmd_status\" -eq 0 ] || overall=1

  echo '=== project describe ==='
  gcloud projects describe ${GCP_PROJECT_ID} --format='value(projectNumber,lifecycleState)'
  cmd_status=\$?
  echo \"project_describe_exit=\$cmd_status\"
  [ \"\$cmd_status\" -eq 0 ] || overall=1

  echo '=== artifact repos ==='
  gcloud artifacts repositories list --project ${GCP_PROJECT_ID} --location ${GCP_REGION} --format='table(name,format,location)'
  cmd_status=\$?
  echo \"artifact_repos_exit=\$cmd_status\"
  [ \"\$cmd_status\" -eq 0 ] || overall=1

  echo '=== cloud run services ==='
  gcloud run services list --project ${GCP_PROJECT_ID} --region ${GCP_REGION} --format='table(metadata.name,status.url)'
  cmd_status=\$?
  echo \"cloud_run_services_exit=\$cmd_status\"
  [ \"\$cmd_status\" -eq 0 ] || overall=1

  echo '=== scheduler jobs ==='
  gcloud scheduler jobs list --project ${GCP_PROJECT_ID} --location ${GCP_REGION} --format='table(name,state)'
  cmd_status=\$?
  echo \"scheduler_jobs_exit=\$cmd_status\"
  [ \"\$cmd_status\" -eq 0 ] || overall=1

  exit \"\$overall\"
} 2>&1 | tee $STDOUT; status=\${PIPESTATUS[0]}; set -e; end=\$(date +%s); printf 'gcp_readonly_smoke_exit=%s\\nruntime_seconds=%s\\n' \"\$status\" \"\$((end-start))\" | tee $RUNTIME; exit \"\$status\""
status=$?
set -e
"$SCRIPT_DIR/fetch_artifacts.sh"
exit "$status"
