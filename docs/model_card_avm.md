# AVM Model Card

Last updated: 2026-07-26 14:51:45 Asia/Bangkok

Status: simple non-GIS baseline measured; production AVM not trained.

## Intended Use

Estimate listing-based residential market value and price per square meter for lending demos. Outputs must include uncertainty, confidence, comparable support, and non-commercial data limitations.

## Current Metrics

- Temporal MdAPE: 22.85% for district+property-type median price/m2 baseline on December 2025 test
- Temporal RMSLE: 0.4426 for district+property-type median price/m2 baseline on December 2025 test
- Spatial MdAPE: not measured
- Spatial RMSLE: not measured
- 80% interval coverage: not measured
- Median interval-width ratio: not measured
- Artifact size: not measured
- Training runtime: not measured
- Baseline runtime: 2 seconds on VM

## Known Limitations

- Full HF listing dataset has been ingested into a 638,123-row Hà Nội/Hồ Chí Minh gold cohort.
- Listing prices are asking prices, not verified transaction prices.
- Low-support and OOD behavior is not implemented yet.
- Source latitude/longitude columns are absent, so GIS features and spatial holdout are not implemented yet.
