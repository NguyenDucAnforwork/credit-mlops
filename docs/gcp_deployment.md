# GCP Deployment

Last updated: 2026-07-27 00:05:00 Asia/Bangkok

## Target

- Project: `driven-reef-452414-b5`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- VM: `lfm`

## Current Status

Not deployed. Terraform initialization and planning now pass on the VM; no apply, image push, or resource creation has been run.

VM-originating GCP checks now use active account `credit-mlops-deployer@driven-reef-452414-b5.iam.gserviceaccount.com` and configured project `driven-reef-452414-b5`. Project describe, Artifact Registry list, Cloud Run service list, and Scheduler job list all pass in the read-only smoke.

The 2026-07-27 read-only cloud smoke runs through `make remote-cloud-smoke` and passes: `gcp_readonly_smoke_exit=0`, runtime 10 seconds. Required API visibility and read-only resource checks pass. Evidence: `docs/evidence/phase6_gcp_readonly_smoke_20260726.txt` and `docs/evidence/phase6_gcp_readonly_smoke_runtime_20260726.txt`.

The 2026-07-26 AVM interval, comparable fallback, API scaffold, AVM promotion dry-run, monitoring, TestClient load, uvicorn HTTP load, startup warm-up, AVM artifact packaging, dependency remediation, `httpx2` TestClient warning remediation, type-check smoke, and Docker image build/smoke milestones did not execute Terraform plan/apply, image push, MLflow alias mutation, or deployments. GCP state remained unchanged during those milestones.

The 2026-07-27 remote Terraform phase used Terraform 1.9.8 and Google provider 6.50.0. `terraform init` and `terraform plan` both passed in 3 seconds. The plan is `30 to add, 0 to change, 0 to destroy`; Cloud SQL remains disabled. Evidence: `docs/evidence/phase6_terraform_init_plan_20260727.txt` and `docs/evidence/phase6_terraform_init_plan_runtime_20260727.txt`.

## Remaining Deployment Blockers

- Immutable production API and job images are now pushed to Artifact Registry and referenced by their immutable digests in Terraform.
- The plan has not been applied, so there is no Cloud Run URL, ETL execution, API smoke, scheduler execution, or rollback evidence.
- The deployer can perform the read-only smoke, but apply-time IAM for every planned resource and cost approval still need confirmation.
- MLflow tracking URI and runtime secret values are not provisioned; no secret was created or committed.
- Secret Manager values were not created or populated. The final digest-based Terraform plan passed with 29 resources to add, 0 to change, and 0 to destroy.
- Do not create downloaded long-lived service-account keys.

## Cost

No exact monthly estimate is derivable from `terraform plan` alone. The plan creates usage-priced GCS, BigQuery, Artifact Registry, Secret Manager, Cloud Run, and Scheduler resources; Cloud SQL is disabled, and Cloud Run is configured with min instances 0. A numeric estimate requires approved storage, query, image-retention, request, CPU/memory, job-runtime, and scheduler-volume assumptions. Only the Artifact Registry repository was created in this phase; no other planned resources were created.

The targeted registry phase created one Artifact Registry repository and measured 1665.702MB stored after image pushes. This is the only cloud resource created in this phase; exact monthly billing still depends on current Artifact Registry storage/egress pricing and retention assumptions.

## Docker Prerequisite

Docker-based deployment preparation is partially unblocked on the VM. User `ducan` can access the Docker daemon, individual UI/API/monitor image builds plus API/UI/monitor plain-container smokes passed, and the core Compose stack for Postgres/Redis/API/UI passed on 2026-07-26.

Source hardening completed on 2026-07-26: `.dockerignore` excludes `.env`, generated data layers, remote model directories, Terraform state/plans, and generated evidence/report paths. API and monitoring Dockerfiles no longer copy `.env`. The VM source guard passed before daemon access was refreshed.

Container dependency alignment completed partially on 2026-07-26: main requirements audit passes and UI Docker dependencies import, but monitoring image requirements still resolve vulnerable `lightgbm 4.5.0` through NannyML. This blocks a clean monitoring image security claim even after Docker access is restored.

Latest Docker evidence: UI image `94df2d30ecb0` built in 55 seconds, API image `b4e4dcd3afd7` built in 286 seconds, and monitoring image `ab3038d25eeb` built in 298 seconds. API `/health` returned `status=ok` with `model_version=fallback_local`; UI Streamlit health returned `ok`; monitoring imports passed. Compose v5.3.1 then started an isolated Postgres/Redis/API/UI stack, all four services reached Docker health `healthy`, API/UI HTTP health passed, and teardown removed containers/network/volume. Dockerized API load passed after mounting VM property data into the API container: AVM p95 283.01 ms and lending p95 33.93 ms with 0% errors at 1,000 requests/concurrency 10. Monitoring profile, image push, and Cloud Run smoke remain incomplete.
