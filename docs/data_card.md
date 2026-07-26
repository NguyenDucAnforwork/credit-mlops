# Data Card

Last updated: 2026-07-26 14:05:41 Asia/Bangkok

## Primary Dataset

- Source: Hugging Face dataset `vduydong/vietnam-real-estates`
- Expected scale: approximately 1,000,000 listings
- Format: Parquet
- Coordinates: WGS84
- License: CC BY-NC 4.0
- Current local status: not downloaded
- Current VM status: not downloaded in this phase
- Source revision: `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`
- Last modified: `2026-04-08T06:51:21.000Z`
- Parquet shards: 5 (`shard_0000.parquet` through `shard_0004.parquet`)
- Checksums: not measured
- Row counts: not measured

## Fixture Data

- Purpose: ETL contract tests and smoke evidence only.
- Location: generated in tests and `/tmp` on the VM; not committed as a dataset.
- Measured incremental behavior: 1,000 inserts and 100 duplicates on first run; 0 inserts on identical rerun.
- Limitation: fixture data does not represent real market distribution and must not be used for AVM metrics.

## Usage Limits

The dataset is non-commercial. Listing prices are not verified transaction prices, and AVM outputs must be described as listing-based market-value estimates.

## MVP Geography

The MVP focuses on Hà Nội and Hồ Chí Minh City, with configuration intended to extend to additional provinces.
