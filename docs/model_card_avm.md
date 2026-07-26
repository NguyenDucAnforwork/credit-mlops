# AVM Model Card

Last updated: 2026-07-26 21:29:41 Asia/Bangkok

Status: non-GIS tabular baseline measured; production AVM not promoted.

## Intended Use

Estimate listing-based residential market value and price per square meter for lending demos. Outputs must include uncertainty, confidence, comparable support, and non-commercial data limitations.

## Current Metrics

- Temporal MdAPE: 19.16% for HGB log(price/m2) baseline on December 2025 test
- Temporal RMSLE: 0.3850 for HGB log(price/m2) baseline on December 2025 test
- Spatial MdAPE: not measured
- Spatial RMSLE: not measured
- 80% interval coverage: 78.67% for direct q10/q90 HGB quantile intervals on December 2025 test
- Median interval-width ratio: 76.99%, above the <=50% target
- p90 interval-width ratio: 134.16%
- High-confidence share: 14.33%; medium-confidence share: 39.30%; low-confidence share: 46.37%
- Comparable support: non-GIS fallback returns 10 leakage-safe comparables for each sampled December query with p95 14.88 ms; distance unavailable
- API scaffold smoke: `/v1/avm/predict` returned 200 with high confidence and 13.13 ms latency after comparable index build
- Promotion gate: dry-run decision `reject`; interval width, spatial holdout, major cohort regression, and warm API p95 evidence block promotion
- Monitoring: synthetic drift shifted at least three features and triggered 4 alerts
- Delayed-label monitoring: 2,000-label fallback replay MdAPE 16.73%, 0 cohort alerts above +5 points
- Warm API uvicorn HTTP load: AVM p95 140.84 ms with 0% errors at concurrency 10
- Startup warm-up: first comparable request after startup 10.99 ms after 4.85s index warm-up during lifespan
- Artifact package: 2.37 MB HGB point + q10/q90 quantile joblib, VM-only under `artifacts/models/`
- Artifact load/predict: load 87.13 ms, single prediction 21.32 ms
- Artifact-backed API: AVM p95 136.63 ms and lending p95 15.53 ms with 0% valid-request errors at concurrency 10
- Training runtime: 26.40 seconds for artifact train/evaluation on VM; same-seed MdAPE delta 0.0 percentage points
- Baseline runtime: 2 seconds on VM
- The 2026-07-26 `httpx2` TestClient remediation was dependency-only. It changed dev test compatibility, not AVM features, training data, model artifact bytes, promotion status, or measured AVM metrics.
- The 2026-07-26 type-check smoke phase changed annotations/guards and orchestration only. It did not retrain, repack, promote, or mutate the AVM artifact.

## Known Limitations

- Full HF listing dataset has been ingested into a 638,123-row Hà Nội/Hồ Chí Minh gold cohort.
- Listing prices are asking prices, not verified transaction prices.
- Low-support and OOD behavior is not implemented yet.
- Source latitude/longitude columns are absent, so GIS features and spatial holdout are not implemented yet.
- Current quantile intervals are calibrated but too wide. They improve median width versus global residual and cohort residual intervals, but still fail the production width target.
- Comparable fallback is administrative, not spatial; it must not be described as nearest-neighbor evidence.
- API can serve the experimental HGB quantile artifact when `AVM_ARTIFACT_PATH` is configured, and otherwise falls back to non-GIS comparables.
- No `property_avm@champion` alias is promoted yet.
- Monitoring currently covers synthetic drift and delayed-label replay; production delayed-label ingestion is not implemented yet.
- Warm local VM service p95 is measured with uvicorn; Docker and Cloud Run p95 are not measured.
