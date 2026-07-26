# Data Card

Last updated: 2026-07-26 16:16:20 Asia/Bangkok

## Primary Dataset

- Source: Hugging Face dataset `vduydong/vietnam-real-estates`
- Expected scale: approximately 1,000,000 listings
- Format: Parquet
- Coordinates: expected WGS84 from contract, but actual Parquet schema has no latitude/longitude columns
- License: CC BY-NC 4.0
- Current local status: not downloaded
- Current VM status: downloaded under ignored path `data/raw/vietnam-real-estates/a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`
- Source revision: `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`
- Last modified: `2026-04-08T06:51:21.000Z`
- Parquet shards: 5 (`shard_0000.parquet` through `shard_0004.parquet`)
- HF ETags: measured for all 5 shards in `reports/generated/hf_vietnam_real_estates_shard_manifest_20260726.json`
- Full SHA256 checksums: measured for all 5 shards in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`
- Row counts: 1,000,000 total rows from Parquet footers, 200,000 per shard
- Schema width: 19 columns from Parquet footers
- Total shard size: 469,122,864 bytes from HTTP headers
- VM raw snapshot disk use: 448M
- Silver rows: 893,830
- Gold MVP rows: 638,123 for Hà Nội and Hồ Chí Minh City
- Quarantine rows: 106,170
- Duplicate rows: 8
- Coordinate status: `missing_source_columns`
- Data contract status: `pass_with_blockers`
- Core contract checks: required columns, unique listing IDs, MVP city filter, >=500,000 gold rows, positive price/area/price_per_m2, quarantine reasons all pass
- Blocker contract check: coordinate source columns present fails because the actual source schema lacks `latitude` and `longitude`
- Current AVM uncertainty evidence uses only non-GIS listing attributes; direct quantile intervals remain too wide for a promoted confidence policy.
- Current AVM artifact evidence uses the same VM gold cohort and non-GIS features; no model binary or generated dataset is stored locally.
- Comparable fallback evidence uses administrative fields and listing age only; it cannot provide distance, radius, H3, or nearest-neighbor spatial support until coordinates are enriched.
- Property API smoke reads the VM gold parquet through `PROPERTY_GOLD_PATH`; the full dataset remains VM-only.

## Fixture Data

- Purpose: ETL contract tests and smoke evidence only.
- Location: generated in tests and `/tmp` on the VM; not committed as a dataset.
- Measured incremental behavior: 1,000 inserts and 100 duplicates on first run; 0 inserts on identical rerun.
- Limitation: fixture data does not represent real market distribution and must not be used for AVM metrics.

## Usage Limits

The dataset is non-commercial. Listing prices are not verified transaction prices, and AVM outputs must be described as listing-based market-value estimates.

## MVP Geography

The MVP gold cohort has 311,266 Hà Nội rows and 326,857 Hồ Chí Minh City rows. Configuration remains extensible to additional provinces.
