# GCP Deployment

Last updated: 2026-07-26 21:46:09 Asia/Bangkok

## Target

- Project: `driven-reef-452414-b5`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- VM: `lfm`

## Current Status

Not deployed. Terraform source exists and validates on the VM, but no plan/apply or resource creation has been run.

VM-originating GCP checks found active account `582914829900-compute@developer.gserviceaccount.com`, but project describe and service listing are blocked by `ACCESS_TOKEN_SCOPE_INSUFFICIENT`.

The 2026-07-26 AVM interval, comparable fallback, API scaffold, AVM promotion dry-run, monitoring, TestClient load, uvicorn HTTP load, startup warm-up, AVM artifact packaging, dependency remediation, `httpx2` TestClient warning remediation, and type-check smoke milestones did not execute Terraform, `gcloud`, Docker builds, MLflow alias mutation, or deployments. GCP state remained unchanged during those milestones.

The 2026-07-26 Terraform scaffold milestone added `infra/terraform` with project APIs, Artifact Registry, GCS, BigQuery, Secret Manager placeholder, Cloud Run service, Cloud Run ETL job, Scheduler, IAM service accounts, and optional disabled-by-default Cloud SQL/PostGIS resources. VM validation used Terraform 1.9.8 and Google provider 6.50.0 with `init -backend=false`; `terraform_validate_exit=0`, runtime 2 seconds. No `terraform plan`, `terraform apply`, `gcloud`, Docker build, image push, or cloud deployment was run.

## Required Fix

Grant the VM sufficient OAuth scopes and IAM for project inspection, Service Usage, Artifact Registry, GCS, BigQuery, Cloud Run, Scheduler, Secret Manager, Cloud SQL, logging, monitoring, and Terraform-managed resources. Do not create downloaded long-lived service-account keys.

## Cost

Not measured. No GCP resources were created by this phase.

## Docker Prerequisite

Docker-based deployment preparation is also blocked on the VM because user `ducan` cannot access `/var/run/docker.sock`, and `docker compose` is not available.

Source hardening completed on 2026-07-26: `.dockerignore` excludes `.env`, generated data layers, remote model directories, Terraform state/plans, and generated evidence/report paths. API and monitoring Dockerfiles no longer copy `.env`. The VM source guard passed, but Docker build/runtime evidence remains blocked by socket permissions.
