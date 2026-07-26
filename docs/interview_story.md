# Interview Story

Last updated: 2026-07-26 14:51:45 Asia/Bangkok

## Current 90-Second Story

I started with an existing credit scoring MLOps project and rebuilt its execution model so a weak local laptop only edits and commits code, while all runtime work happens on a dedicated GCP VM. The first phase added sentinel-guarded SSH/rsync orchestration, remote Make targets, and measured VM/GCP preflight evidence. That created the foundation for reproducible ETL, AVM training, geospatial features, API integration, and cloud deployment without contaminating the local repository with data, models, or secrets.

## Quantified CV Bullets

- Built a remote execution baseline where 76 original tests pass on the GCP VM in 7.42 seconds after VM-only dependency sync and data prep.
- Added a fixture-backed property ETL foundation that raised the VM-verified suite to 86 passing tests and proved 1,000-insert/100-duplicate incremental behavior.
- Captured reproducible Hugging Face source metadata from the VM: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38` across 5 Parquet shards.
- Verified the real-estate dataset scale without full local download by reading Parquet footers on the VM: 1,000,000 rows, 19 columns, 469,122,864 bytes.
- Downloaded and checksummed the full pinned real-estate snapshot on the VM in 74 seconds, with a 12-second verified rerun path and no raw data committed locally.
- Normalized 1,000,000 raw listings into 893,830 silver rows and 638,123 Hà Nội/Hồ Chí Minh gold rows in 48 seconds on the VM, while documenting missing coordinate columns as a real data limitation.
- Added data contracts with 102 VM-verified tests and a `pass_with_blockers` report: 9 core data checks pass, and coordinate availability is explicitly blocked.
- Established a non-GIS AVM baseline on 108,336 December listings: district+property-type median price/m2 achieved 22.85% MdAPE versus 47.97% for global median.
- Not ready: AVM metrics are not measured yet.
- Not ready: cloud deployment metrics are not measured yet.

## Tradeoffs

- Chose a VM executor first because it preserves local responsiveness and avoids accidental local dependency or data sprawl.
- Deferred cloud deployment because the VM currently lacks sufficient OAuth scopes for project and service inspection.
