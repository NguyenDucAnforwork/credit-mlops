# Progress

Last updated: 2026-07-26 14:27:30 Asia/Bangkok

## Phase Checklist

- Phase 0 audit and remote baseline: partially complete; tests pass, Docker smoke blocked
- Phase 1 ETL: fixture-backed foundation and HF footer manifest complete; full content download/ETL not started
- Phase 2 PostGIS and GIS: not started
- Phase 3 AVM: not started
- Phase 4 APIs: not started
- Phase 5 MLOps and monitoring: not started
- Phase 6 Docker and GCP: cloud access blocked by VM OAuth scopes; local Docker baseline pending
- Phase 7 UI, CI, portfolio: not started

## Evidence

- Local SSH preflight passed for host `lfm`.
- Local GitHub dry-run push returned `Everything up-to-date` before feature branch creation.
- Feature branch created locally: `feat/onemount-property-intelligence`.
- VM inventory captured in `docs/remote_environment.md`.
- GCP project access from VM is blocked by `ACCESS_TOKEN_SCOPE_INSUFFICIENT`.
- Initial remote bootstrap created the dedicated workspace/sentinel but could not clone with local SSH alias `github-nguyenducan`; the workspace is treated as rsync-backed until the feature branch is pushed.
- Initial remote bootstrap stopped because `uv` was not installed; bootstrap now attempts a user-level `uv` install without sudo.
- `uv sync --frozen --all-extras --dev` completed on the VM and installed 168 packages.
- Baseline data prep on the VM produced data version `cac9de3c`, 16,000 train rows, and 4,000 test rows.
- Original tests passed on the VM: 76 passed in 7.42 seconds; wrapper runtime 9 seconds.
- Docker smoke is blocked: `ducan` is not in the `docker` group and `docker compose` is unavailable.
- Phase 1 ETL foundation tests passed on the VM: 10 passed in 0.27 seconds.
- Full suite after Phase 1 foundation passed on the VM: 86 passed in 12.79 seconds; wrapper runtime 15 seconds.
- Incremental fixture evidence: first run inserted exactly 1,000 rows and found exactly 100 duplicates; identical rerun inserted 0 rows.
- Hugging Face metadata captured on the VM for `vduydong/vietnam-real-estates`: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`, 5 Parquet shards, last modified `2026-04-08T06:51:21.000Z`.
- Full suite after HF metadata source module passed on the VM: 89 passed in 7.36 seconds; wrapper runtime 9 seconds.
- HF shard footer manifest measured on the VM without full downloads: 5 shards, 1,000,000 total rows, 19 columns, 469,122,864 total bytes, ETags captured.
- Full suite after shard manifest module passed on the VM: 93 passed in 7.31 seconds; wrapper runtime 9 seconds.

## Next

Commit and push the verified shard manifest milestone, then continue toward full remote snapshot download, SHA256 checksums, schema normalization, and data contracts.
