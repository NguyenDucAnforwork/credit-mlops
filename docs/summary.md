# Summary

Last updated: 2026-07-26 14:05:41 Asia/Bangkok

Status: Phase 0 in progress.

The project is being converted from a credit scoring MLOps demo into a Property Intelligence & Lending MLOps Platform. The local repository remains the source of truth, and runtime work is executed on `lfm` in `/home/ducan/credit-mlops-codex`.

## Current Evidence

- SSH to `lfm`: working.
- Feature branch: `feat/onemount-property-intelligence`.
- VM resources: 4 vCPU, 15 GiB RAM, 66 GiB free disk, no GPU.
- GCP access: blocked by `ACCESS_TOKEN_SCOPE_INSUFFICIENT`.
- Remote workspace: created as rsync-backed after VM Git clone failed on local SSH alias `github-nguyenducan`.
- Baseline tests: 76 passed in 7.42 seconds on the VM.
- Current tests: 86 passed in 12.79 seconds on the VM after Phase 1 ETL foundation.
- Baseline data split: version `cac9de3c`, 16,000 train rows, 4,000 test rows.
- ETL fixture: 1,000 inserts, 100 duplicates, identical rerun 0 inserts.
- Docker smoke: blocked because `ducan` cannot access Docker socket and `docker compose` is unavailable.
- Deployment URL: not deployed.

## Next Step

Commit and push the verified Phase 1 ETL foundation, then continue with remote-only HF source metadata and smoke ingestion.
