# Deployment Summary

- Project: `driven-reef-452414-b5`
- Region: `asia-southeast1`
- Validation timestamp: 2026-07-27 (Asia/Bangkok)
- Terraform: `0 to add, 1 to change, 0 to destroy`; the one change is harmless Cloud Run provider normalization of zero scaling fields.

# Architecture

```text
Cloud Scheduler (03:00 Asia/Bangkok) -> authenticated Cloud Run ETL Job
Cloud Run ETL Job -> versioned GCS parquet -> BigQuery property_* tables
Authenticated client -> Cloud Run API -> Secret Manager -> DagsHub MLflow
```

# Resources

- API: `credit-mlops-demo-api`, `https://credit-mlops-demo-api-ocj3bsu27q-as.a.run.app`
- ETL job: `credit-mlops-demo-etl`
- Scheduler: `credit-mlops-demo-etl-daily`, `0 3 * * *`, `Asia/Bangkok`
- BigQuery: `property_intelligence_demo`
- Storage: `driven-reef-452414-b5-property-snapshots-demo`
- Artifact Registry: `credit-mlops`
- Runtime service account: `credit-mlops-run-demo@driven-reef-452414-b5.iam.gserviceaccount.com`
- Scheduler service account: `credit-mlops-scheduler-demo@driven-reef-452414-b5.iam.gserviceaccount.com`
- Secret Manager supplies MLflow URI, username, and password; payloads were not read or recorded.
- API image digest: `sha256:ea8eee11bcb7e79210c90406c76441c91d5b6d07b96625a2a912ba7405665c38`
- ETL image digest: `sha256:e5ca3820cd41e98d5de0e66fef006b097dff694c05212251a29953332526a8be`

# Validation Results

- Terraform plan: `0 add, 1 change, 0 destroy`; only harmless scaling normalization remains.
- API readiness: Ready; authenticated `/health` returned HTTP 200 and MLflow model `credit_score_model@champion v3` loaded.
- Valid AVM request: HTTP 200 with the expected valuation interval, confidence, comparables, model and snapshot fields.
- Invalid AVM request (`area_m2=0`): HTTP 422 validation response, not a 5xx.
- ETL run 1: `credit-mlops-demo-etl-fdrgb`, successful in 3m42.48s.
- ETL run 2: `credit-mlops-demo-etl-zrd8l`, completed successfully with consistent versioned outputs.
- Scheduler trigger: `credit-mlops-demo-etl-2pk9v` initially hit a measured memory limit at 2 CPU/8Gi; after the job was raised to 4 CPU/16Gi, `credit-mlops-demo-etl-2pk9v` completed successfully in 2m29.37s.
- Storage: three versioned parquet objects, 745.13 MiB total.
- BigQuery: `property_silver` 893,830 rows; `property_gold` 638,123 rows; `property_quarantine` 106,170 rows.
- Focused remote tests: `35 passed in 6.32s` (`tests/test_hf_etl.py`, `tests/test_api.py`, `tests/test_deployment.py`).
- No credentials or secret payloads were printed in validation output or reviewed logs.

# Security

Secrets remain in Secret Manager and are injected as runtime references. Existing runtime and scheduler service accounts are used without IAM changes. Images are pinned by digest. No service-account keys were created.

# Known Limitations

- The source dataset has no latitude/longitude, so GIS/radius comparables are unavailable; the tested AVM response honestly reported no comparable support and low confidence.
- The AVM is explicitly an experimental listing-based fallback, not a production valuation.
- Terraform still reports only the harmless Cloud Run scaling normalization described above.

# Estimated Cost

Demo-scale usage is dominated by the ETL job. The API is 1 vCPU/1Gi with zero minimum instances and max two instances; ETL is 4 vCPU/16Gi, up to one hour, once daily. Storage holds approximately 745 MiB. Actual cost depends on runtime, traffic, BigQuery scans, image retention, and regional pricing; no fixed bill was inferred.

# Reproduction

```bash
scripts/remote/sync_to_vm.sh
scripts/remote/run.sh 'terraform -chdir=infra/terraform plan -no-color'
scripts/remote/run.sh 'gcloud run jobs execute credit-mlops-demo-etl --region=asia-southeast1 --wait'
scripts/remote/run.sh 'gcloud scheduler jobs run credit-mlops-demo-etl-daily --location=asia-southeast1'
scripts/remote/run.sh 'uv run pytest -q tests/test_hf_etl.py tests/test_api.py tests/test_deployment.py'
```
