# Summary

Last updated: 2026-07-26 15:33:55 Asia/Bangkok

Status: Phase 1 data contracts complete with blockers for GIS/GCP/Docker.

The project is being converted from a credit scoring MLOps demo into a Property Intelligence & Lending MLOps Platform. The local repository remains the source of truth, and runtime work is executed on `lfm` in `/home/ducan/credit-mlops-codex`.

## Current Evidence

- SSH to `lfm`: working.
- Feature branch: `feat/onemount-property-intelligence`.
- VM resources: 4 vCPU, 15 GiB RAM, 66 GiB free disk, no GPU.
- GCP access: blocked by `ACCESS_TOKEN_SCOPE_INSUFFICIENT`.
- Remote workspace: created as rsync-backed after VM Git clone failed on local SSH alias `github-nguyenducan`.
- Baseline tests: 76 passed in 7.42 seconds on the VM.
- Current tests: 126 passed in 8.27 seconds on the VM after AVM lifecycle gate implementation and docs/evidence updates.
- Baseline data split: version `cac9de3c`, 16,000 train rows, 4,000 test rows.
- ETL fixture: 1,000 inserts, 100 duplicates, identical rerun 0 inserts.
- HF dataset metadata: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`, 5 Parquet shards, last modified `2026-04-08T06:51:21.000Z`.
- HF raw snapshot: downloaded on VM only, 1,000,000 total rows, 19 columns, 469,122,864 bytes, full SHA256 captured for 5 shards, 448M disk.
- HF ETL: 893,830 silver rows, 638,123 MVP gold rows, 106,170 quarantine rows, 8 duplicate rows.
- Coordinate blocker: actual source schema lacks `latitude` and `longitude`; no coordinates were fabricated.
- Data contract status: `pass_with_blockers`; core ETL checks pass and coordinate availability is the blocker.
- AVM baseline: district+property-type median price/m2 reached December test MdAPE 22.85% and RMSLE 0.4426 on 108,336 rows.
- Current best non-GIS AVM: HGB log(price/m2), December test MdAPE 19.16%, RMSLE 0.3850, 16.14% relative MdAPE improvement over strongest simple baseline.
- Uncertainty: direct quantile 80% interval coverage 78.67% passes and improves median width to 76.99% with 14.33% high-confidence share, but the <=50% width target still fails and p90 width is 134.16%.
- Comparables: non-GIS fallback benchmark ran 1,000 December queries with p95 14.88 ms and 0% valid-request errors, but distance/radius/PostGIS criteria remain blocked by missing coordinates.
- APIs: `POST /v1/avm/predict`, `GET /v1/comparables`, and `POST /v1/lending/decision` are implemented and smoked with real VM gold data through TestClient; full warm service p95 criteria are not measured.
- AVM lifecycle: dry-run promotion gate rejects current candidate; temporal improvement and coverage pass, but interval width, spatial holdout, cohort regression, and warm API p95 evidence block promotion.
- Engineering test-count criterion: 126 passing tests meets the >=125 numeric floor.
- Docker smoke: blocked because `ducan` cannot access Docker socket and `docker compose` is unavailable.
- Deployment URL: not deployed.

## Next Step

Run final AVM lifecycle verification, commit and push it, then continue with monitoring or warm API load reporting.
