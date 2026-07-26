# GCP Terraform Scaffold

This directory contains source-only Terraform for the Property Intelligence demo. Run it only from the VM workspace `/home/ducan/credit-mlops-codex`.

Current scope:

- Required project APIs.
- Artifact Registry repository for images.
- GCS bucket for property snapshots.
- BigQuery dataset for silver/gold tables.
- Secret Manager placeholder for the MLflow tracking URI.
- Cloud Run service for FastAPI.
- Cloud Run Job for ETL.
- Cloud Scheduler job to trigger ETL.
- Service accounts and IAM bindings.
- Optional Cloud SQL PostgreSQL scaffold for future PostGIS use, disabled by default with `enable_cloud_sql = false`.

Do not run `terraform apply` until VM GCP OAuth scopes/IAM and cost approval are confirmed. Cloud SQL remains disabled by default because it can create ongoing cost.

Validation from the VM:

```bash
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
```
