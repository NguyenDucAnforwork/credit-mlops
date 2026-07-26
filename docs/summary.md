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
- Current tests: 89 passed in 7.36 seconds on the VM after HF metadata source module.
- Baseline data split: version `cac9de3c`, 16,000 train rows, 4,000 test rows.
- ETL fixture: 1,000 inserts, 100 duplicates, identical rerun 0 inserts.
- HF dataset metadata: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`, 5 Parquet shards, last modified `2026-04-08T06:51:21.000Z`.
- Docker smoke: blocked because `ducan` cannot access Docker socket and `docker compose` is unavailable.
- Deployment URL: not deployed.

## Next Step

Commit and push the verified HF metadata milestone, then continue with remote-only shard checksum and row-count smoke ingestion.
