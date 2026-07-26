# Progress

Last updated: 2026-07-26 15:00:15 Asia/Bangkok

## Phase Checklist

- Phase 0 audit and remote baseline: partially complete; tests pass, Docker smoke blocked
- Phase 1 ETL: raw snapshot, silver/gold ETL, and data contracts complete with coordinate blocker documented
- Phase 2 PostGIS and GIS: not started
- Phase 3 AVM: non-GIS median/tabular baselines and first interval calibration measured
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
- Full HF snapshot downloaded on the VM only: 5 Parquet shards, 469,122,864 bytes, 1,000,000 rows from footers, full SHA256 for every shard.
- Snapshot download runtime: 74 seconds; rerun/reuse runtime: 12 seconds; disk usage: 448M under `data/raw/vietnam-real-estates`.
- Full suite after snapshot downloader passed on the VM: 96 passed in 7.35 seconds; wrapper runtime 9 seconds.
- Full HF ETL on VM: 1,000,000 raw rows, 893,830 silver rows, 638,123 Hà Nội/Hồ Chí Minh gold rows, 106,170 quarantine rows, 8 duplicate rows.
- ETL runtime: 48 seconds; disk: 407M silver, 287M gold, 52M quarantine.
- Coordinate source columns `latitude` and `longitude` are absent from the actual dataset schema; records are marked `coordinate_status=missing_source_columns`.
- Full suite after HF ETL passed on the VM: 99 passed in 7.38 seconds; wrapper runtime 9 seconds.
- Data contract validation status: `pass_with_blockers`; 9 core checks passed; coordinate-source check failed as blocker.
- Full suite after data contracts passed on the VM: 102 passed in 7.98 seconds; wrapper runtime 10 seconds.
- AVM baseline split: train June-October 2025 = 429,682 rows, validation November 2025 = 100,105 rows, test December 2025 = 108,336 rows.
- Best non-GIS simple baseline: district + property-type median price/m2; December test MdAPE 22.85%, RMSLE 0.4426, MAE 18.52B VND, R2 0.387, within 20% = 44.42%.
- Full suite after AVM baseline passed on the VM: 105 passed in 7.57 seconds; wrapper runtime 9 seconds.
- Non-GIS tabular HGB baseline: December test MdAPE 19.16%, RMSLE 0.3850, MAE 18.66B VND, R2 0.313, within 20% = 51.79%.
- Relative MdAPE improvement over strongest simple baseline: 16.14%.
- Full suite after tabular AVM passed on the VM: 107 passed in 7.69 seconds; wrapper runtime 9 seconds.
- First interval calibration: empirical 80% interval coverage 79.61%, median interval width ratio 83.79%, p90 width ratio 83.79%; coverage passes but width fails the <=50% target.
- Full suite after interval calibration passed on the VM: 108 passed in 7.73 seconds; wrapper runtime 10 seconds.

## Next

Commit and push the verified interval calibration experiment, then retry uncertainty width reduction and add cohort metrics while coordinate enrichment remains unresolved.
