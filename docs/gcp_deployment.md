# GCP Deployment

Last updated: 2026-07-26 16:16:20 Asia/Bangkok

## Target

- Project: `driven-reef-452414-b5`
- Region: `asia-southeast1`
- Zone: `asia-southeast1-a`
- VM: `lfm`

## Current Status

Not deployed.

VM-originating GCP checks found active account `582914829900-compute@developer.gserviceaccount.com`, but project describe and service listing are blocked by `ACCESS_TOKEN_SCOPE_INSUFFICIENT`.

The 2026-07-26 AVM interval, comparable fallback, API scaffold, AVM promotion dry-run, monitoring, TestClient load, uvicorn HTTP load, startup warm-up, and AVM artifact packaging milestones did not execute Terraform, `gcloud`, Docker builds, MLflow alias mutation, or deployments. GCP state remains unchanged.

## Required Fix

Grant the VM sufficient OAuth scopes and IAM for project inspection, Service Usage, Artifact Registry, GCS, BigQuery, Cloud Run, Scheduler, Secret Manager, Cloud SQL, logging, monitoring, and Terraform-managed resources. Do not create downloaded long-lived service-account keys.

## Cost

Not measured. No GCP resources were created by this phase.

## Docker Prerequisite

Docker-based deployment preparation is also blocked on the VM because user `ducan` cannot access `/var/run/docker.sock`, and `docker compose` is not available.
