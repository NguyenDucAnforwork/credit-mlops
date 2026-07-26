# Reproduce

Last updated: 2026-07-26 14:27:30 Asia/Bangkok

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
