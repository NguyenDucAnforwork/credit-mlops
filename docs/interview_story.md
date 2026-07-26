# Interview Story

Last updated: 2026-07-26 21:39:59 Asia/Bangkok

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
- Improved the AVM baseline with HGB on log(price/m2): December MdAPE 19.16% and RMSLE 0.3850, a 16.14% relative MdAPE gain over the strongest simple baseline.
- Calibrated 80% AVM intervals across residual, cohort residual, and direct quantile approaches; the best quantile run reached 78.67% coverage and 76.99% median width, so it was kept as evidence but rejected for production confidence because the width target is <=50%.
- Added a leakage-safe non-GIS comparable fallback and benchmarked 1,000 December queries on the VM: p95 14.88 ms, 0% valid-request errors, and 10 comparables per query, with distance explicitly marked unavailable.
- Added Phase 4 API scaffolding for AVM, comparables, and lending decisions; VM smoke returned 200 for all three endpoints and exact LTV boundary tests cover 0.75 and 0.85.
- Added an AVM promotion dry-run gate that raised the suite to 126 passing tests and correctly rejected the current candidate despite 16.14% MdAPE improvement because interval width and spatial/API evidence are not ready.
- Added deterministic property monitoring drift checks; synthetic drift shifted 5 inputs and triggered 4 alerts while raising the remote suite to 129 passing tests.
- Benchmarked warmed property APIs through uvicorn on the VM: 1,000 AVM HTTP requests at concurrency 10 reached p95 140.84 ms with 0% errors, and 1,000 lending HTTP requests reached p95 24.21 ms.
- Added delayed-label monitoring on 2,000 December listings: fallback comparable replay reached 16.73% MdAPE and found no district/property-type cohort above the +5 MdAPE point alert threshold.
- Moved property index construction into FastAPI startup, reducing the first comparable request after startup to 10.99 ms while making the 4.85-second startup cost explicit.
- Packaged the HGB quantile AVM as a VM-only 2.37 MB artifact, proved same-seed MdAPE delta 0.0 points, and measured artifact-backed uvicorn p95 at 136.63 ms for AVM requests.
- Added a Streamlit Property Intelligence workspace covering map reference input, AVM estimate/interval, comparables, factors, credit/LTV decisioning, disclaimers, and the three required demo scenarios.
- Added a 5-second remote reproduction smoke path that runs syntax checks, Ruff lint, and 61 focused tests on the VM after local secret/path scanning.
- Measured scoped API/source coverage on the VM after dependency and TestClient warning remediation: 139 tests passed in 15.91 seconds with 81% coverage across `api/*`, `src/*`, and property scripts.
- Added and remediated a remote vulnerability evidence target; initial `pip-audit` found 59 known vulnerabilities, and the post-upgrade audit found 0 while the warnings-enabled suite stayed clean.
- Added a scoped VM type-check smoke for the new property/API surface; after typing-only fixes, mypy found 0 issues in 19 source files with a 1-second wrapper runtime, and the full warnings-enabled suite passed 139 tests in 11.16 seconds.
- Added a GCP Terraform scaffold for required APIs, Artifact Registry, GCS, BigQuery, Secret Manager, Cloud Run service/job, Scheduler, IAM, and optional Cloud SQL/PostGIS; VM validation passed with Terraform 1.9.8 and Google provider 6.50.0 in 2 seconds without plan/apply.
- Reworked the repository README and reproduction report into an evidence-led portfolio entrypoint with remote-only reproduction commands and explicit blocker status.
- Not ready: GIS/spatial AVM metrics are not measured yet because coordinates are absent.
- Not ready: cloud deployment metrics are not measured yet.

## Tradeoffs

- Chose a VM executor first because it preserves local responsiveness and avoids accidental local dependency or data sprawl.
- Deferred cloud deployment because the VM currently lacks sufficient OAuth scopes for project and service inspection.
