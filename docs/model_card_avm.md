# AVM Model Card

Last updated: 2026-07-26 15:20:05 Asia/Bangkok

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
- Artifact size: not measured
- Training runtime: 9 seconds for HGB baseline train/evaluation on VM
- Baseline runtime: 2 seconds on VM

## Known Limitations

- Full HF listing dataset has been ingested into a 638,123-row Hà Nội/Hồ Chí Minh gold cohort.
- Listing prices are asking prices, not verified transaction prices.
- Low-support and OOD behavior is not implemented yet.
- Source latitude/longitude columns are absent, so GIS features and spatial holdout are not implemented yet.
- Current quantile intervals are calibrated but too wide. They improve median width versus global residual and cohort residual intervals, but still fail the production width target.
- Comparable fallback is administrative, not spatial; it must not be described as nearest-neighbor evidence.
