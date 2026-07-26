# AVM Model Card

Last updated: 2026-07-26 14:56:20 Asia/Bangkok

Status: non-GIS tabular baseline measured; production AVM not promoted.

## Intended Use

Estimate listing-based residential market value and price per square meter for lending demos. Outputs must include uncertainty, confidence, comparable support, and non-commercial data limitations.

## Current Metrics

- Temporal MdAPE: 19.16% for HGB log(price/m2) baseline on December 2025 test
- Temporal RMSLE: 0.3850 for HGB log(price/m2) baseline on December 2025 test
- Spatial MdAPE: not measured
- Spatial RMSLE: not measured
- 80% interval coverage: not measured
- Median interval-width ratio: not measured
- Artifact size: not measured
- Training runtime: 9 seconds for HGB baseline train/evaluation on VM
- Baseline runtime: 2 seconds on VM

## Known Limitations

- Full HF listing dataset has been ingested into a 638,123-row Hà Nội/Hồ Chí Minh gold cohort.
- Listing prices are asking prices, not verified transaction prices.
- Low-support and OOD behavior is not implemented yet.
- Source latitude/longitude columns are absent, so GIS features and spatial holdout are not implemented yet.
