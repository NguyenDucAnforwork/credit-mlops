# Reproduce

Last updated: 2026-07-26 16:26:10 Asia/Bangkok

All heavy work runs on the VM. Do not install project dependencies, run tests, train models, Docker, Terraform, or `gcloud` locally.

```bash
git switch feat/onemount-property-intelligence
make remote-doctor
make remote-bootstrap
make remote-sync
make remote-verify
```

Phase 1 ETL fixture verification:

```bash
make remote-sync
scripts/remote/run.sh 'uv run pytest tests/test_property_etl.py -q'
```

HF metadata capture is VM-only:

```bash
scripts/remote/run.sh 'uv run python -c "from property_intelligence.sources import fetch_hf_dataset_metadata; print(fetch_hf_dataset_metadata())"'
```

HF footer manifest smoke:

```bash
scripts/remote/run.sh 'uv run python -c "from property_intelligence.sources import fetch_hf_dataset_metadata, build_hf_shard_manifest; print(build_hf_shard_manifest(fetch_hf_dataset_metadata(), measure_footers=True))"'
```

Full raw snapshot download on VM:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_snapshot.py'
scripts/remote/fetch_artifacts.sh
```

Full HF silver/gold ETL on VM:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_etl.py'
scripts/remote/fetch_artifacts.sh
```

HF layer contract validation:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_validate.py'
scripts/remote/fetch_artifacts.sh
```

Non-GIS AVM baseline:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_avm_baseline.py'
scripts/remote/fetch_artifacts.sh
```

Non-GIS tabular AVM:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_avm_tabular.py'
scripts/remote/fetch_artifacts.sh
```

Non-GIS AVM interval calibration:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_avm_intervals.py'
scripts/remote/fetch_artifacts.sh
```

Non-GIS AVM cohort interval calibration:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_avm_cohort_intervals.py'
scripts/remote/fetch_artifacts.sh
```

Non-GIS AVM quantile interval calibration:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_avm_quantile_intervals.py'
scripts/remote/fetch_artifacts.sh
```

Non-GIS comparable fallback benchmark:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_comparables_benchmark.py'
scripts/remote/fetch_artifacts.sh
```

Property API scaffold smoke:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_api_smoke.py'
scripts/remote/fetch_artifacts.sh
```

AVM promotion gate dry-run:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_avm_promotion_gate.py'
scripts/remote/fetch_artifacts.sh
```

Synthetic property monitoring drift:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_monitoring_drift.py'
scripts/remote/fetch_artifacts.sh
```

Warm property API TestClient load benchmark:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_api_load_benchmark.py'
scripts/remote/fetch_artifacts.sh
```

Warm property API uvicorn HTTP load benchmark:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_api_http_benchmark.py'
scripts/remote/fetch_artifacts.sh
```

The same benchmark records startup warm-up evidence after the property index warm-up change.

AVM artifact packaging and artifact-backed API benchmark:

```bash
scripts/remote/sync_to_vm.sh
scripts/remote/run.sh 'uv run python scripts/property_avm_artifact.py'
scripts/remote/run.sh 'AVM_ARTIFACT_PATH=artifacts/models/property_avm_hgb_quantile_20260726.joblib uv run python scripts/property_api_http_benchmark.py'
scripts/remote/fetch_artifacts.sh
```

The joblib artifact remains on the VM under `artifacts/models/`; only JSON/stdout evidence is copied back.

Property Intelligence UI helper and syntax checks:

```bash
scripts/remote/sync_to_vm.sh
scripts/remote/run.sh 'uv run pytest tests/test_ui_property_workflow.py -q && uv run python -m py_compile ui/streamlit_app.py ui/property_workflow.py'
scripts/remote/run.sh 'uv run pytest -q'
scripts/remote/fetch_artifacts.sh
```

Delayed-label AVM monitoring:

```bash
make remote-sync
scripts/remote/run.sh 'uv run python scripts/property_delayed_label_monitoring.py'
scripts/remote/fetch_artifacts.sh
```

Additional targets required by the contract:

```bash
make remote-etl-smoke
make remote-train-smoke
make remote-reproduce-smoke
make remote-reproduce-full
make remote-up
make remote-cloud-smoke
```

Cloud reproduction is blocked until the VM service account has sufficient OAuth scopes/IAM for project `driven-reef-452414-b5`.

Docker reproduction is blocked until user `ducan` can access `/var/run/docker.sock` and a Compose command is available on the VM.
