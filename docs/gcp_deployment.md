# GCP Deployment

Last updated: 2026-07-26 23:16:14 Asia/Bangkok

## Target

- Project: `driven-reef-452414-b5`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- VM: `lfm`

## Current Status

Not deployed. Terraform source exists and validates on the VM, but no plan/apply or resource creation has been run.

VM-originating GCP checks found active account `582914829900-compute@developer.gserviceaccount.com` and configured project `driven-reef-452414-b5`. `gcloud services list --project driven-reef-452414-b5 --limit=5` now succeeds. `gcloud projects describe driven-reef-452414-b5` still exits 1 because Cloud Resource Manager API is disabled/permissioned for consumer project `582914829900`.

The reusable 2026-07-26 read-only cloud smoke now runs through `make remote-cloud-smoke` and exits nonzero while prerequisites are blocked. Latest result: `gcp_readonly_smoke_exit=1`, runtime 10 seconds. Auth and project config pass, and Service Usage visibility works. Project describe fails on Cloud Resource Manager access, Artifact Registry list fails because Artifact Registry API is disabled, Cloud Run services list fails because Cloud Run Admin API is disabled, and Scheduler jobs list fails because Cloud Scheduler API is disabled. No API enablement, resource creation, Terraform plan/apply, image push, or deployment was attempted.

The 2026-07-26 AVM interval, comparable fallback, API scaffold, AVM promotion dry-run, monitoring, TestClient load, uvicorn HTTP load, startup warm-up, AVM artifact packaging, dependency remediation, `httpx2` TestClient warning remediation, type-check smoke, and Docker image build/smoke milestones did not execute Terraform plan/apply, image push, MLflow alias mutation, or deployments. GCP state remained unchanged during those milestones.

The 2026-07-26 Terraform scaffold milestone added `infra/terraform` with project APIs, Artifact Registry, GCS, BigQuery, Secret Manager placeholder, Cloud Run service, Cloud Run ETL job, Scheduler, IAM service accounts, and optional disabled-by-default Cloud SQL/PostGIS resources. VM validation used Terraform 1.9.8 and Google provider 6.50.0 with `init -backend=false`; `terraform_validate_exit=0`, runtime 2 seconds. No `terraform plan`, `terraform apply`, `gcloud`, Docker build, image push, or cloud deployment was run.

## Required Fix

Enable/authorize Cloud Resource Manager for the VM service account/consumer project path and grant sufficient IAM for project inspection, Artifact Registry, GCS, BigQuery, Cloud Run, Scheduler, Secret Manager, Cloud SQL, logging, monitoring, and Terraform-managed resources. Do not create downloaded long-lived service-account keys.

## Cost

Not measured. No GCP resources were created by this phase.

## Docker Prerequisite

Docker-based deployment preparation is partially unblocked on the VM. User `ducan` can access the Docker daemon, individual UI/API/monitor image builds plus API/UI/monitor plain-container smokes passed, and the core Compose stack for Postgres/Redis/API/UI passed on 2026-07-26.

Source hardening completed on 2026-07-26: `.dockerignore` excludes `.env`, generated data layers, remote model directories, Terraform state/plans, and generated evidence/report paths. API and monitoring Dockerfiles no longer copy `.env`. The VM source guard passed before daemon access was refreshed.

Container dependency alignment completed partially on 2026-07-26: main requirements audit passes and UI Docker dependencies import, but monitoring image requirements still resolve vulnerable `lightgbm 4.5.0` through NannyML. This blocks a clean monitoring image security claim even after Docker access is restored.

Latest Docker evidence: UI image `94df2d30ecb0` built in 55 seconds, API image `b4e4dcd3afd7` built in 286 seconds, and monitoring image `ab3038d25eeb` built in 298 seconds. API `/health` returned `status=ok` with `model_version=fallback_local`; UI Streamlit health returned `ok`; monitoring imports passed. Compose v5.3.1 then started an isolated Postgres/Redis/API/UI stack, all four services reached Docker health `healthy`, API/UI HTTP health passed, and teardown removed containers/network/volume. Dockerized API load passed after mounting VM property data into the API container: AVM p95 283.01 ms and lending p95 33.93 ms with 0% errors at 1,000 requests/concurrency 10. Monitoring profile, image push, and Cloud Run smoke remain incomplete.
