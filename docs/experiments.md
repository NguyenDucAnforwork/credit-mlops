# Experiments

## EXP-0001: Phase 0 Remote Preflight

- Timestamp in Asia/Bangkok: 2026-07-26 14:05:41
- Hypothesis: The local machine can orchestrate work while `lfm` performs runtime execution in `/home/ducan/credit-mlops-codex`.
- Local Git commit or working-tree identifier: `4ccd7e3` with uncommitted local documentation and orchestration changes.
- Dataset snapshot ID and checksums: not applicable; no dataset downloaded.
- Exact remote command: `ssh -o BatchMode=yes -o ConnectTimeout=10 lfm 'printf "SSH_OK\n"; whoami; hostname; pwd'` and VM inventory/GCP preflight commands from `CODEX_GOAL_LOCAL_TO_GCP_VM.md`.
- Configuration and seed: not applicable.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, 66 GiB free disk, no GPU.
- Runtime: SSH preflight completed successfully; inventory completed in under one minute.
- Peak RAM when available: not measured.
- Metrics: SSH OK; Docker present; Git present; gcloud present; `uv` missing; Terraform missing; GCP service access blocked by insufficient OAuth scopes.
- Baseline comparison: none.
- Interpretation: Remote non-cloud work can proceed after workspace bootstrap; cloud deployment cannot proceed until VM scopes/IAM are fixed.
- Decision: keep.
- Lesson learned: Cloud readiness needs an explicit VM-originating check before Terraform or `gcloud` work.
- Next experiment: run baseline tests and Docker smoke checks entirely on the VM.

## EXP-0002: Dedicated VM Workspace Bootstrap

- Timestamp in Asia/Bangkok: 2026-07-26 14:08:00
- Hypothesis: `/home/ducan/credit-mlops-codex` can be created safely as the only VM workspace for this project.
- Local Git commit or working-tree identifier: `4ccd7e3` with uncommitted local orchestration and docs.
- Dataset snapshot ID and checksums: not applicable; no dataset downloaded.
- Exact remote command: `scripts/remote/bootstrap.sh`
- Configuration and seed: `REMOTE_WORKSPACE=/home/ducan/credit-mlops-codex`, branch `feat/onemount-property-intelligence`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: under one minute before stopping.
- Peak RAM when available: not measured.
- Metrics: workspace and `.codex_remote_workspace` sentinel created; Git clone failed because VM could not resolve SSH host alias `github-nguyenducan`; `uv` missing.
- Retry metrics: user-level `uv` installation succeeded in `/home/ducan/.local/bin`; dependency sync was skipped until source sync because no `pyproject.toml` was present yet.
- Second retry metrics: after source sync, `uv sync --frozen --all-extras --dev` installed 168 packages into the VM `.venv`.
- Baseline comparison: none.
- Interpretation: safe workspace exists, but the VM must use rsync source sync until GitHub remote access is available from VM or the pushed branch can be fetched using a resolvable remote.
- Decision: retry with user-level `uv` installation and rsync-backed source sync.
- Lesson learned: local SSH aliases are not portable to VM Git operations.
- Next experiment: sync local source to the sentinel workspace and run baseline tests after dependency installation.

## EXP-0003: Original Test Baseline on VM

- Timestamp in Asia/Bangkok: 2026-07-26 14:09:52
- Hypothesis: The existing credit-scoring test suite passes when dependencies and baseline processed data are prepared on `lfm`.
- Local Git commit or working-tree identifier: `4ccd7e3` with uncommitted orchestration/docs.
- Dataset snapshot ID and checksums: credit baseline raw data version `cac9de3c`; full SHA256 not measured in this run.
- Exact remote command: `scripts/remote/run.sh 'uv run pytest -q'`
- Configuration and seed: baseline `src/data_prep.py` split with `random_state=42`; pytest default configuration.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: pytest reported 7.42 seconds; shell wrapper measured 9 seconds.
- Peak RAM when available: not measured.
- Metrics: 76 passed, 0 failed, 0 errors.
- Baseline comparison: prior README/results text claimed 62 or 76 tests depending section; measured current suite is 76 passing tests.
- Interpretation: original non-Docker baseline is reproducible on the VM after remote dependency sync and data prep.
- Decision: keep.
- Lesson learned: generated baseline splits should be rebuilt on the VM from ignored raw data instead of synced as source.
- Next experiment: Docker/API smoke after Docker socket and Compose access are available.

## EXP-0004: Docker Preflight on VM

- Timestamp in Asia/Bangkok: 2026-07-26 14:10:16
- Hypothesis: The `ducan` user can run Docker and Compose smoke checks on `lfm`.
- Local Git commit or working-tree identifier: `4ccd7e3` with uncommitted orchestration/docs.
- Dataset snapshot ID and checksums: not applicable.
- Exact remote command: `scripts/remote/run.sh 'docker ps; docker compose version; docker compose config --quiet'`
- Configuration and seed: not applicable.
- VM hardware/environment: Ubuntu 24.04.4 LTS, Docker client 29.1.3.
- Runtime: under one minute.
- Peak RAM when available: not measured.
- Metrics: Docker client available; Docker server access denied; socket owned by `root:docker`; user `ducan` is not in `docker`; `docker compose` command unavailable.
- Baseline comparison: none.
- Interpretation: Docker stack/API smoke cannot be run without an approved Docker permission and Compose fix.
- Decision: retry after user/admin updates VM Docker access; do not use sudo silently.
- Lesson learned: Docker client presence is insufficient evidence; check socket access and Compose separately.
- Next experiment: continue source-only/non-Docker implementation, or rerun Docker smoke after access is fixed.

## EXP-0005: Fixture-Backed ETL Foundation

- Timestamp in Asia/Bangkok: 2026-07-26 14:15:00
- Hypothesis: A deterministic local-source ETL module can validate bronze/silver/gold and incremental semantics on the VM without downloading the full real-estate dataset.
- Local Git commit or working-tree identifier: `cd27f63` plus uncommitted Phase 1 ETL source and tests.
- Dataset snapshot ID and checksums: fixture data generated in tests; no external dataset snapshot; no checksums.
- Exact remote command: `scripts/remote/run.sh 'uv run pytest tests/test_property_etl.py -q'` and `scripts/remote/run.sh 'uv run pytest -q'`.
- Configuration and seed: deterministic fixture records; no random seed used.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: focused ETL tests 0.27 seconds; final captured full suite 12.79 seconds with 15-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: 10 focused ETL tests passed; full suite 86 passed; incremental fixture first run inserted 1,000 and detected 100 duplicates; identical rerun inserted 0.
- Baseline comparison: previous pushed baseline had 76 tests passing; Phase 1 adds 10 passing tests.
- Interpretation: the ingestion foundation now covers adapter checkpointing, immutable bronze snapshots, silver normalization/quarantine/deduplication, gold derived features, and incremental duplicate behavior.
- Decision: keep.
- Lesson learned: new production packages should be added to `pyproject.toml` so standalone remote evidence scripts do not need `PYTHONPATH`.
- Next experiment: implement HF Parquet source metadata/checksum capture and small remote smoke ingestion without storing full data locally.

## EXP-0006: Hugging Face Dataset Metadata Capture

- Timestamp in Asia/Bangkok: 2026-07-26 14:21:46
- Hypothesis: The VM can capture reproducible Hugging Face dataset metadata without downloading the full Parquet shards.
- Local Git commit or working-tree identifier: `135b732` plus uncommitted HF metadata source module and docs.
- Dataset snapshot ID and checksums: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; shard checksums not measured yet.
- Exact remote command: `scripts/remote/run.sh 'curl -L --fail --silent --show-error https://huggingface.co/api/datasets/vduydong/vietnam-real-estates ...'`.
- Configuration and seed: Hugging Face API metadata only; no random seed.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: metadata capture and full suite completed in under one minute; pytest reported 7.36 seconds with 9-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: dataset ID `vduydong/vietnam-real-estates`; revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; last modified `2026-04-08T06:51:21.000Z`; 5 Parquet shards; full suite 89 passed.
- Baseline comparison: previous Phase 1 foundation had 86 passing tests; metadata source tests add 3 passing tests.
- Interpretation: source revision tracking is reproducible from the VM and does not require local data storage.
- Decision: keep.
- Lesson learned: capture dataset revision before shard download so later row counts and checksums have a stable source identity.
- Next experiment: remote shard checksum/row-count smoke and then full ingestion when disk/runtime constraints are confirmed.

## EXP-0007: HF Parquet Footer Manifest

- Timestamp in Asia/Bangkok: 2026-07-26 14:27:24
- Hypothesis: The VM can measure Parquet shard row counts and object sizes using HTTP headers and footer range reads without downloading full shard bodies.
- Local Git commit or working-tree identifier: `e47f3eb` plus uncommitted shard manifest source/tests/docs.
- Dataset snapshot ID and checksums: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; HF ETags captured; full content SHA256 not measured.
- Exact remote command: `scripts/remote/run.sh 'uv run python ... build_hf_shard_manifest(metadata, measure_footers=True)'`.
- Configuration and seed: Hugging Face resolved URLs pinned to revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; no random seed.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: manifest generation completed in under one minute; final pytest reported 7.31 seconds with 9-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: 5 Parquet shards; each shard 200,000 rows; total rows 1,000,000; 19 columns; total remote object size 469,122,864 bytes; footer bytes per shard ranged from 10,514 to 11,517.
- Baseline comparison: previous metadata-only module had 89 passing tests; shard manifest adds 4 passing tests for 93 total.
- Interpretation: expected dataset scale is confirmed from Parquet footers without local data or full VM downloads.
- Decision: keep.
- Lesson learned: Parquet footers are enough to verify row counts and schema width cheaply, but they are not a substitute for full-content SHA256.
- Next experiment: full remote snapshot download with SHA256 and immutable bronze metadata, bounded by VM disk and runtime.

## EXP-0008: Full HF Raw Snapshot Download

- Timestamp in Asia/Bangkok: 2026-07-26 14:33:40
- Hypothesis: The VM can download the full pinned HF Parquet snapshot, compute full SHA256 checksums, and keep raw data out of the local repository.
- Local Git commit or working-tree identifier: `b2c41d0` plus uncommitted snapshot downloader source/tests/docs.
- Dataset snapshot ID and checksums: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; SHA256 checksums captured in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_snapshot.py'`.
- Configuration and seed: resolved HF URLs pinned to revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; no random seed.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: first download 74 seconds; rerun with local shard reuse 12 seconds; final pytest 7.35 seconds with 9-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: 5 shards; 469,122,864 bytes; 448M disk under `data/raw/vietnam-real-estates`; 1,000,000 rows from footers; 19 columns; 96 tests passed.
- Baseline comparison: previous shard manifest had 93 passing tests; snapshot downloader adds 3 passing tests for 96 total.
- Interpretation: raw source snapshot is now reproducible and verified on the VM, while local Git contains only small JSON manifests and evidence.
- Decision: keep.
- Lesson learned: shard-level reuse avoids repeat downloads, but still recomputes local SHA256 to prove the existing file content.
- Next experiment: convert raw snapshot into immutable bronze metadata and silver normalized/quarantine layers on the VM.

## EXP-0009: Full HF Silver/Gold ETL

- Timestamp in Asia/Bangkok: 2026-07-26 14:40:57
- Hypothesis: The full pinned HF raw snapshot can be normalized into silver, MVP Hà Nội/Hồ Chí Minh gold, and quarantine layers on the VM within the contract runtime/disk limits.
- Local Git commit or working-tree identifier: `e744235` plus uncommitted HF ETL source/tests/docs.
- Dataset snapshot ID and checksums: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw shard SHA256 checksums in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_etl.py'`.
- Configuration and seed: full raw snapshot under `data/raw/vietnam-real-estates/a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; no random seed.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: ETL 48 seconds; final pytest 7.38 seconds with 9-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: 1,000,000 raw rows; 893,830 silver rows; 638,123 gold MVP rows; 106,170 quarantine rows; 8 duplicate rows; 311,266 Hà Nội gold rows; 326,857 Hồ Chí Minh gold rows.
- Baseline comparison: previous snapshot downloader had 96 passing tests; HF ETL adds 3 passing tests for 99 total.
- Interpretation: full data volume is usable for MVP AVM row-count criteria, but source coordinates are absent, so PostGIS/H3 work needs an explicit enrichment source or geocoding strategy.
- Decision: keep ETL and document coordinate blocker honestly.
- Lesson learned: verify real schema before assuming coordinates from dataset descriptions.
- Next experiment: data contracts and coordinate enrichment decision; do not fabricate latitude/longitude.

## EXP-0010: HF Layer Data Contracts

- Timestamp in Asia/Bangkok: 2026-07-26 14:47:13
- Hypothesis: The full HF silver/gold/quarantine outputs satisfy core data contracts and expose coordinate availability as a measured blocker.
- Local Git commit or working-tree identifier: `71d2c7c` plus uncommitted data-contract source/tests/docs.
- Dataset snapshot ID and checksums: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_validate.py'`.
- Configuration and seed: validation threshold `min_gold_rows=500000`; no random seed.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: contract validation 16 seconds; final pytest 7.98 seconds with 10-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: status `pass_with_blockers`; 9 core checks passed; 1 blocker check failed for missing `latitude`/`longitude`; 638,123 gold MVP rows; 102 tests passed.
- Baseline comparison: previous HF ETL had 99 passing tests; contracts add 3 passing tests for 102 total.
- Interpretation: ETL output is model-usable for non-GIS tabular baselines and satisfies the >=500,000 MVP row criterion, but GIS/PostGIS/H3 requirements cannot be truthfully completed from this source alone.
- Decision: keep validation and treat coordinate enrichment as an explicit architecture decision.
- Lesson learned: a `pass_with_blockers` state is more honest than either failing all ETL or pretending GIS fields exist.
- Next experiment: document coordinate enrichment decision and start non-GIS AVM baselines.

## EXP-0011: Non-GIS AVM Median Baselines

- Timestamp in Asia/Bangkok: 2026-07-26 14:51:38
- Hypothesis: Simple listing price-per-m2 median baselines provide a defensible AVM floor before adding tabular ML or GIS features.
- Local Git commit or working-tree identifier: `84b1034` plus uncommitted AVM baseline source/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_avm_baseline.py'`.
- Configuration and seed: deterministic temporal split, June-October 2025 train, November 2025 validation, December 2025 test; no random seed.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: AVM baseline script 2 seconds; final pytest 7.57 seconds with 9-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: train 429,682 rows; validation 100,105 rows; test 108,336 rows. Best test model `district_property_type_median_price_per_m2`: MdAPE 22.85%, RMSLE 0.4426, MAE 18.52B VND, median absolute error 1.85B VND, R2 0.387, within 10% 23.42%, within 20% 44.42%.
- Baseline comparison: global median test MdAPE 47.97%; district median test MdAPE 31.43%; district+property-type median test MdAPE 22.85%.
- Interpretation: district+property-type stratification is a strong simple baseline and already meets the temporal MdAPE target, but RMSLE remains above target and GIS/spatial holdout requirements remain blocked by missing coordinates.
- Decision: keep as AVM Experiment 1 baseline.
- Lesson learned: property type materially improves listing-based value estimation, but the error distribution remains wide for high-value listings.
- Next experiment: train non-GIS tabular model and compare against this strongest simple baseline.

## EXP-0012: Non-GIS Tabular HGB AVM

- Timestamp in Asia/Bangkok: 2026-07-26 14:56:14
- Hypothesis: A non-GIS tabular gradient boosting model on log(price/m2) improves temporal MdAPE and RMSLE over the strongest simple median baseline without using fabricated coordinates.
- Local Git commit or working-tree identifier: `7ab6d5c` plus uncommitted tabular AVM source/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_avm_tabular.py'`.
- Configuration and seed: HistGradientBoostingRegressor, `random_state=42`, target `log(price_per_m2)`, deterministic temporal split June-October / November / December 2025.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: training/evaluation script 9 seconds; final pytest 7.69 seconds with 9-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: train 429,682 rows; validation 100,105 rows; test 108,336 rows. Test MdAPE 19.16%, RMSLE 0.3850, MAE 18.66B VND, median absolute error 1.58B VND, R2 0.313, within 10% 27.67%, within 20% 51.79%.
- Baseline comparison: strongest simple baseline test MdAPE 22.85% and RMSLE 0.4426; tabular HGB improves MdAPE by 16.14% relative and improves RMSLE by 13.02% relative, but MAE is slightly worse than 18.52B VND.
- Interpretation: non-GIS tabular modeling meets temporal MdAPE and RMSLE targets, but high-value outliers still hurt MAE and spatial/GIS criteria remain blocked by missing coordinates.
- Decision: keep as AVM Experiment 2 and current best temporal model.
- Lesson learned: optimizing log(price/m2) improves relative error and RMSLE, while absolute VND error still needs tail handling.
- Next experiment: calibrated uncertainty intervals and cohort metrics for the current best non-GIS model.

## EXP-0013: Validation Residual 80% Intervals

- Timestamp in Asia/Bangkok: 2026-07-26 15:00:11
- Hypothesis: Central 80% intervals calibrated from November validation log residuals provide acceptable December empirical coverage for the current non-GIS HGB AVM.
- Local Git commit or working-tree identifier: `851ebf8` plus uncommitted interval calibration source/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_avm_intervals.py'`.
- Configuration and seed: HistGradientBoostingRegressor `random_state=42`; residual quantiles q10=-0.3807, q90=0.4196 from validation split.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: interval script 9 seconds; final pytest 7.73 seconds with 10-second wrapper runtime.
- Peak RAM when available: not measured.
- Metrics: test coverage 79.61%; median interval-width ratio 83.79%; p90 interval-width ratio 83.79%; low-confidence share 100%; point MdAPE 19.16%; RMSLE 0.3850.
- Baseline comparison: no prior interval baseline; coverage target 75%-85% passes, width target <=50% fails.
- Interpretation: validation residual intervals are calibrated but too wide for a usable confidence policy.
- Decision: retry/tune; keep as failed-width uncertainty experiment.
- Lesson learned: global residual intervals are blunt and produce uniformly low confidence; cohort- or quantile-model intervals are needed.
- Next experiment: reduce interval width through cohort calibration or quantile models while maintaining coverage.

## EXP-0014: Cohort-Calibrated 80% Intervals

- Timestamp in Asia/Bangkok: 2026-07-26 15:05:25
- Hypothesis: Province/property-type validation residual cohorts can reduce interval width while keeping December empirical coverage inside the 75%-85% target band.
- Local Git commit or working-tree identifier: `0e7ebd4` plus uncommitted cohort interval source/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_avm_cohort_intervals.py'`.
- Configuration and seed: HistGradientBoostingRegressor `random_state=42`; cohort columns `province, property_type`; minimum 500 validation rows per cohort; global q10/q90 residual fallback.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: cohort interval script 9 seconds; targeted AVM tests plus full suite passed before experiment, 7 AVM tests in 0.90 seconds and 109 total tests in 7.81 seconds.
- Peak RAM when available: not measured.
- Metrics: 6 qualified cohorts; 107,356 test rows used cohort residual bands; 980 test rows used global fallback; fallback share 0.90%; test coverage 79.29%; median interval-width ratio 82.32%; p90 interval-width ratio 107.48%; medium-confidence share 21.63%; low-confidence share 78.37%; point MdAPE 19.16%; RMSLE 0.3850.
- Baseline comparison: global residual interval coverage was 79.61% with 83.79% median width and 100% low-confidence share. Cohort calibration slightly reduced median width and created a medium-confidence segment, but p90 width worsened and the <=50% median width target still fails.
- Interpretation: coarse listing cohorts do not solve uncertainty usefulness without true spatial/location features or a more direct quantile objective.
- Decision: keep as failed-width uncertainty experiment; do not promote confidence policy.
- Lesson learned: segmenting residuals by province/property type can identify relatively tighter cohorts, but listing residual variance remains too large for narrow 80% bands.
- Next experiment: try quantile HGB or conformalized quantile regression, while continuing to treat GIS features as blocked until coordinates are legitimately enriched.

## EXP-0015: Direct Quantile HGB 80% Intervals

- Timestamp in Asia/Bangkok: 2026-07-26 15:12:35
- Hypothesis: Direct q10/q90 HGB models for log(price/m2) can reduce interval width versus residual calibration while preserving December empirical coverage.
- Local Git commit or working-tree identifier: `f97cc34` plus uncommitted quantile interval source/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_avm_quantile_intervals.py'`.
- Configuration and seed: three HistGradientBoostingRegressor pipelines with `random_state=42`: point squared-error model, q10 quantile model, q90 quantile model; target `log(price_per_m2)`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: quantile interval script 30 seconds; targeted AVM tests plus full suite passed before experiment, 8 AVM tests in 1.13 seconds and 110 total tests in 8.02 seconds.
- Peak RAM when available: not measured.
- Metrics: validation coverage 79.64%; validation median interval-width ratio 77.74%; test coverage 78.67%; test median interval-width ratio 76.99%; p90 interval-width ratio 134.16%; high-confidence share 14.33%; medium-confidence share 39.30%; low-confidence share 46.37%; point MdAPE 19.16%; RMSLE 0.3850.
- Baseline comparison: global residual median width 83.79%; cohort residual median width 82.32%; direct quantile median width 76.99%. Coverage remains in target, but p90 width is worse than residual baselines and median width still exceeds the <=50% target.
- Interpretation: direct quantile training materially improves confidence segmentation but does not satisfy production interval usability on this non-GIS listing feature set.
- Decision: keep as best current uncertainty experiment by median width and confidence segmentation, but do not promote.
- Lesson learned: direct quantile objectives are better than residual grouping for high/medium/low confidence separation, but missing location signal and listing noise still dominate interval width.
- Next experiment: add richer non-GIS support/comparable features or conformalized quantile diagnostics; GIS remains blocked until coordinates are legitimately enriched.

## EXP-0016: Non-GIS Comparable Fallback Benchmark

- Timestamp in Asia/Bangkok: 2026-07-26 15:19:58
- Hypothesis: A leakage-safe district/property-type comparable fallback can provide support metadata and fast local query behavior while PostGIS/H3 remains blocked.
- Local Git commit or working-tree identifier: `7f9c4a8` plus uncommitted comparable fallback source/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_comparables_benchmark.py'`.
- Configuration and seed: 1,000 December 2025 gold listings sampled with `random_state=42`; index built from all gold rows; candidates must be published before the subject listing time; area tolerance ±25%; max 10 results.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: benchmark script 13 seconds; focused comparable tests passed in 0.65 seconds; full suite passed with 112 tests in 8.13 seconds before the benchmark.
- Peak RAM when available: not measured.
- Metrics: 1,000 queries; 0 errors; valid-request error rate 0%; median latency 8.65 ms; p95 latency 14.88 ms; max latency 18.64 ms; comparable count median/mean/min/max all 10; support high 100%; distance status `not_available_missing_coordinates`.
- Baseline comparison: no prior comparable implementation; this is a fallback only and does not satisfy the PostGIS indexed query, distance, or radius fallback criteria.
- Interpretation: non-GIS comparable support is viable for API response scaffolding and model support metadata, but exact nearby comparable search remains blocked.
- Decision: keep fallback with explicit warnings; do not mark Phase 2 GIS/PostGIS comparable criteria complete.
- Lesson learned: district/property-type support can be fast and leakage-safe in memory, but benchmark labels must prevent it from being mistaken for spatial evidence.
- Next experiment: integrate fallback comparables into AVM/API response shape or continue API decision boundaries while PostGIS remains blocked.

## EXP-0017: Property API Scaffold Smoke

- Timestamp in Asia/Bangkok: 2026-07-26 15:27:02
- Hypothesis: The new Phase 4 API surface can return complete AVM, comparable, and lending decision response shapes on the VM using the non-GIS comparable fallback.
- Local Git commit or working-tree identifier: `d9371ed` plus uncommitted API schemas/endpoints/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_api_smoke.py'`.
- Configuration and seed: FastAPI `TestClient`; `PROPERTY_GOLD_PATH` set to VM gold parquet; smoke payload for Hà Nội/Cầu Giấy apartment at 55 m2; lending boundary payload with conservative LTV 0.75.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: smoke script 6 seconds; focused API tests passed in 1.98 seconds; full suite passed with 118 tests in 8.16 seconds before smoke.
- Peak RAM when available: not measured.
- Metrics: `/v1/comparables` status 200 with 10 comparables and cold index-build latency 2,624.48 ms; `/v1/avm/predict` status 200 with 4.95B VND estimate, 4.245B lower value, 5.02B upper value, 15.66% interval-width ratio, high confidence, and 13.13 ms latency after index build; `/v1/lending/decision` status 200 with conservative LTV 0.75 and decision `approve` in 2.63 ms.
- Baseline comparison: previous API surface only had `/health`, `/predict`, and `/metrics`; new endpoint tests increase the suite from 112 to 118 passing tests.
- Interpretation: response contracts and lending boundaries are in place, but this is not the final online performance benchmark because Docker/service runtime remains blocked and the AVM is an experimental comparable fallback.
- Decision: keep API scaffold; do not mark local-on-VM API p95 or lending API p95 criteria complete until warm service load tests run.
- Lesson learned: index construction must be warmed or moved to startup before load testing; cold comparable endpoint latency is dominated by parquet/index load.
- Next experiment: add warm API load benchmark once service execution path is available, or implement model/artifact loading for the promoted AVM path.

## EXP-0018: AVM Promotion Gate Dry-Run

- Timestamp in Asia/Bangkok: 2026-07-26 15:33:51
- Hypothesis: An auditable AVM lifecycle gate can prevent promotion when measured evidence fails the contract even if temporal MdAPE improved.
- Local Git commit or working-tree identifier: `20bebb5` plus uncommitted lifecycle gate source/tests/docs.
- Dataset snapshot ID and checksums: gold layer from revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_avm_promotion_gate.py'`.
- Configuration and seed: dry-run gate using quantile AVM report as candidate, strongest simple median baseline report as baseline, no MLflow alias mutation.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: promotion gate script 1 second; focused lifecycle tests passed in 0.65 seconds; full suite passed with 126 tests in 8.20 seconds before gate.
- Peak RAM when available: not measured.
- Metrics: promotion decision `reject`; temporal MdAPE relative improvement 16.14% passed; 80% interval coverage 78.67% passed; median interval-width ratio 76.99% failed the <=50% threshold; spatial holdout evidence missing; major cohort regression evidence missing; warm API p95 load evidence missing; alias update plan `no_op`; rollback plan `no_op` because no promoted AVM alias history exists.
- Baseline comparison: previous lifecycle state had no AVM promotion gate and 118 passing tests; this adds dry-run gate logic and raises remote test count to 126, above the 125-test numeric floor.
- Interpretation: lifecycle scaffolding now blocks bad promotion explicitly rather than relying on narrative docs.
- Decision: keep dry-run gate; do not mutate MLflow aliases until all gate evidence exists and passes.
- Lesson learned: a model can satisfy temporal MdAPE and calibration coverage while still being unpromotable because uncertainty width and spatial/API evidence are not ready.
- Next experiment: add warm API load report or AVM registry artifact packaging when Docker/service execution is unblocked.

## EXP-0019: Synthetic Property Monitoring Drift

- Timestamp in Asia/Bangkok: 2026-07-26 15:39:32
- Hypothesis: Synthetic monitoring can shift at least three property/AVM features and trigger at least one alert with deterministic evidence.
- Local Git commit or working-tree identifier: `2b32ead` plus uncommitted monitoring source/tests/docs.
- Dataset snapshot ID and checksums: reference sample from gold revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_monitoring_drift.py'`.
- Configuration and seed: 5,000 pre-November gold rows sampled with `random_state=42`; synthetic shifts to area, price/m2, interval width, district missingness, and confidence.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: monitoring script 1 second; focused monitoring tests passed in 0.63 seconds; full suite passed with 129 tests in 8.26 seconds before drift run.
- Peak RAM when available: not measured.
- Metrics: status `alert`; alert count 4; shifted feature count 4; alerts fired for `area_m2`, `price_per_m2`, `interval_width_ratio`, and `missing_feature_share`; relative area mean shift 35%; relative price/m2 mean shift 35%; interval width mean shift 0.25; missing-feature share shift 0.0833.
- Baseline comparison: previous Phase 5 state had lifecycle gate only and 126 passing tests; monitoring adds deterministic drift checks and raises the remote suite to 129 passing tests.
- Interpretation: synthetic drift alerting now covers the contract requirement to shift at least three features and trigger an alert, but production monitoring dashboards/services remain unbuilt.
- Decision: keep deterministic monitoring module and script.
- Lesson learned: keep monitoring thresholds simple and auditable before connecting external monitoring services.
- Next experiment: add delayed-label AVM error/cohort monitoring or warm API load reports.

## EXP-0020: Warm Property API TestClient Load Benchmark

- Timestamp in Asia/Bangkok: 2026-07-26 15:44:25
- Hypothesis: The Phase 4 AVM and lending endpoints can satisfy local-on-VM p95 targets on a warmed FastAPI TestClient path while Docker service runtime remains blocked.
- Local Git commit or working-tree identifier: `53ec2bd` plus uncommitted load benchmark script/docs.
- Dataset snapshot ID and checksums: API reads gold revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_api_load_benchmark.py'`.
- Configuration and seed: FastAPI TestClient, index warmed by one comparable request, 1,000 AVM requests and 1,000 lending requests, concurrency 10.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: load script 23 seconds; final pytest after benchmark passed with 129 tests in 8.20 seconds.
- Peak RAM when available: not measured.
- Metrics: AVM endpoint status codes `[200]`, 0% valid-request error rate, p95 176.43 ms, p99 249.01 ms, max 302.14 ms, throughput 74.51 rps. Lending endpoint status codes `[200]`, 0% valid-request error rate, p95 64.71 ms, p99 94.07 ms, max 197.76 ms, throughput 220.49 rps.
- Baseline comparison: previous API smoke was single-request only and showed cold comparable index latency. This warmed benchmark demonstrates the endpoint logic can meet local p95 targets in-process, but not yet as Docker/uvicorn services.
- Interpretation: API p95 is promising after warm-up, but the contract's service benchmark remains incomplete until a real VM service can run.
- Decision: keep as scoped warm TestClient evidence; do not mark Docker/service or Cloud Run load criteria complete.
- Lesson learned: warm index reuse makes the fallback AVM endpoint fast enough in-process; service startup and Docker blockers still need separate evidence.
- Next experiment: run uvicorn/HTTP load benchmark on the VM if allowed without Docker, or continue delayed-label monitoring.

## EXP-0021: Warm Property API Uvicorn HTTP Benchmark

- Timestamp in Asia/Bangkok: 2026-07-26 15:49:26
- Hypothesis: The Phase 4 property endpoints can satisfy local-on-VM warm HTTP p95 targets through an actual `uvicorn` service without requiring Docker.
- Local Git commit or working-tree identifier: `d902c15` plus uncommitted HTTP benchmark script/docs.
- Dataset snapshot ID and checksums: API reads gold revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_api_http_benchmark.py'`.
- Configuration and seed: `uvicorn main:app` bound to a random localhost port on the VM; `PROPERTY_GOLD_PATH` set to VM gold parquet; one warm comparable request; 1,000 AVM HTTP requests and 1,000 lending HTTP requests; concurrency 10 via `httpx.AsyncClient`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: HTTP benchmark script 19 seconds; final pytest after benchmark passed with 129 tests in 8.24 seconds.
- Peak RAM when available: not measured.
- Metrics: AVM endpoint status codes `[200]`, 0% valid-request error rate, p95 140.84 ms, p99 173.39 ms, max 242.26 ms, throughput 98.38 rps. Lending endpoint status codes `[200]`, 0% valid-request error rate, p95 24.21 ms, p99 224.35 ms, max 354.39 ms, throughput 649.09 rps. Comparable warmup status 200 and latency 2,640.39 ms.
- Baseline comparison: TestClient benchmark had AVM p95 176.43 ms and lending p95 64.71 ms. Uvicorn HTTP benchmark improves both p95s and provides service-level VM evidence outside Docker.
- Interpretation: local-on-VM warm AVM and lending API p95/error targets pass for the experimental fallback service. Docker and Cloud Run performance remain unmeasured.
- Decision: keep as local-on-VM HTTP service evidence; do not mark Docker build, Compose, or Cloud Run criteria complete.
- Lesson learned: service-level HTTP overhead is acceptable after warm-up; first comparable request is still dominated by index load and should be warmed at startup before demos.
- Next experiment: warm index at API startup or continue delayed-label/cohort monitoring.

## EXP-0022: Delayed-Label AVM Monitoring

- Timestamp in Asia/Bangkok: 2026-07-26 15:55:24
- Hypothesis: The non-GIS comparable fallback can produce delayed-label MAE/MdAPE and district/property-type cohort bias monitoring evidence on a December label sample.
- Local Git commit or working-tree identifier: `131a0c5` plus uncommitted delayed-label monitoring source/tests/docs.
- Dataset snapshot ID and checksums: 2,000-label sample from gold revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_delayed_label_monitoring.py'`.
- Configuration and seed: December 2025 gold listings sampled with `random_state=42`; predictions from non-GIS comparable fallback; cohort groups `district, property_type`; minimum 50 rows; alert threshold >5 MdAPE points above overall.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: monitoring script 22 seconds; focused monitoring tests passed in 0.65 seconds; final full suite passed with 130 tests in 8.20 seconds.
- Peak RAM when available: not measured.
- Metrics: 2,000 delayed labels; status `ok`; MAE 5.30B VND; median absolute error 1.4225B VND; MdAPE 16.73%; within 10% 36.10%; within 20% 56.55%; median comparable count 10; distance availability 0%; 10 monitored cohorts; 0 cohort alerts. Worst monitored cohort: Bình Thạnh house, 85 rows, MdAPE 20.56%, +3.83 MdAPE points vs overall.
- Baseline comparison: previous monitoring covered synthetic feature drift only; this adds delayed-label error and district/property-type bias evidence and raises the remote suite to 130 passing tests.
- Interpretation: fallback comparable predictions are reasonable on the sampled delayed-label cohort, but distance monitoring remains unavailable because source coordinates are absent.
- Decision: keep delayed-label monitoring; do not treat it as the final AVM promotion cohort-regression report because the promoted model is still absent.
- Lesson learned: delayed-label monitoring can be useful before production labels exist by replaying held-out listing labels, but it must identify the prediction source and sample scope.
- Next experiment: add API startup warm-up or artifact packaging for the HGB/quantile model.

## EXP-0023: Property API Startup Warm-Up

- Timestamp in Asia/Bangkok: 2026-07-26 16:00:33
- Hypothesis: Warming the property comparable index during FastAPI startup moves the cold parquet/index load out of the first user request while preserving VM uvicorn p95 targets.
- Local Git commit or working-tree identifier: `a653899` plus uncommitted startup warm-up source/tests/docs.
- Dataset snapshot ID and checksums: API reads gold revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote command: `scripts/remote/run.sh 'uv run python scripts/property_api_http_benchmark.py'`.
- Configuration and seed: `uvicorn main:app` on a random VM localhost port; `PROPERTY_GOLD_PATH` set to VM gold parquet; startup calls `warm_property_index`; one post-startup comparable warm request; 1,000 AVM HTTP requests and 1,000 lending HTTP requests at concurrency 10.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: HTTP benchmark script 18 seconds; focused API tests passed in 1.98 seconds; final full suite passed with 132 tests in 10.73 seconds.
- Peak RAM when available: not measured.
- Metrics: startup latency 4,849.08 ms; first comparable request after startup 10.99 ms with status 200; AVM p95 137.81 ms with 0% errors; lending p95 13.56 ms with 0% errors; no lingering uvicorn process after benchmark.
- Baseline comparison: prior uvicorn benchmark had first comparable request 2,640.39 ms because index build happened on the request path. Startup warm-up reduced post-startup comparable latency by 99.58% while keeping AVM p95 essentially unchanged.
- Interpretation: local VM service should be warmed before demos/load tests; the startup cost is explicit and measurable.
- Decision: keep startup warm-up as non-fatal; missing property data degrades property endpoints but does not break `/health`.
- Lesson learned: startup warm-up is a better place for predictable parquet/index initialization than the first customer request.
- Next experiment: package/load the trained HGB/quantile AVM artifact or continue UI/portfolio work while Docker and GCP remain blocked.

## EXP-0024: HGB Quantile AVM Artifact Packaging

- Timestamp in Asia/Bangkok: 2026-07-26 16:16:20
- Hypothesis: The measured HGB point + q10/q90 quantile model can be packaged as a small VM-only artifact, loaded by the API through `AVM_ARTIFACT_PATH`, and still satisfy local-on-VM HTTP p95 targets.
- Local Git commit or working-tree identifier: `e8c2962` plus uncommitted artifact source/tests/docs.
- Dataset snapshot ID and checksums: artifact trains on gold revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; raw SHA256 manifest in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json`.
- Exact remote commands: `scripts/remote/run.sh 'uv run python scripts/property_avm_artifact.py'` and `scripts/remote/run.sh 'AVM_ARTIFACT_PATH=artifacts/models/property_avm_hgb_quantile_20260726.joblib uv run python scripts/property_api_http_benchmark.py'`.
- Configuration and seed: HGB point model plus HGB q10/q90 quantile models for `log(price_per_m2)`, `random_state=42`, June-October train, November validation, December test.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: artifact train/evaluation 26.40 seconds; artifact script runtime with same-seed rerun 55 seconds; artifact-backed HTTP benchmark 18 seconds; final full suite 135 tests in 11.15 seconds.
- Peak RAM when available: not measured.
- Metrics: artifact size 2,480,557 bytes / 2.37 MB; load latency 87.13 ms; single prediction latency 21.32 ms; same-seed MdAPE difference 0.0 percentage points; December test MdAPE 19.16%, RMSLE 0.3850; interval coverage 78.67%, median width 76.99%.
- API metrics with artifact: AVM p95 136.63 ms and 0% valid-request errors; lending p95 15.53 ms and 0% valid-request errors; 1,000 requests per endpoint, concurrency 10.
- Baseline comparison: artifact-backed AVM p95 is similar to the warmed fallback path and remains under the 300 ms local VM target; artifact size is far below the 150 MB limit.
- Interpretation: artifact packaging, loading, size, same-seed reproducibility, and local-on-VM API p95 criteria are measured. Promotion remains blocked by interval width, spatial holdout, cohort regression, Docker, and Cloud Run evidence.
- Decision: keep the artifact as experimental and remote-only; do not mutate an MLflow alias or commit the binary.
- Lesson learned: the artifact boundary should be evidence-driven and lightweight; model binaries stay on the VM while JSON reports carry the auditable metrics.
- Next experiment: build the UI/portfolio surface or CI smoke path while Docker/GCP and coordinate-backed GIS remain blocked.

## EXP-0025: Property Intelligence Streamlit Workspace

- Timestamp in Asia/Bangkok: 2026-07-26 16:26:10
- Hypothesis: The existing Streamlit UI can add the required property-lending demo workflow without changing API contracts or requiring Docker/GCP runtime.
- Local Git commit or working-tree identifier: `e79a0f4` plus uncommitted UI source/tests/docs.
- Dataset snapshot ID and checksums: UI calls the API; no dataset is read by the UI path. Property API evidence still references gold revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`.
- Exact remote command: `scripts/remote/run.sh 'uv run pytest tests/test_ui_property_workflow.py -q && uv run python -m py_compile ui/streamlit_app.py ui/property_workflow.py'`.
- Configuration and seed: three deterministic UI scenarios for Hà Nội apartment, Hồ Chí Minh City house, and low-support manual review; LTV payload uses AVM lower interval value.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: UI helper tests 0.04 seconds; final full suite 139 tests in 11.06 seconds.
- Peak RAM when available: not measured.
- Metrics: 4 UI helper tests passed; Streamlit app and helper module compiled successfully; full suite increased from 135 to 139 tests.
- Baseline comparison: prior UI was credit-only. The new workspace covers map reference input, property attributes, estimate and interval, comparables, factors, credit inputs, LTV decision, disclaimer, and all three required demo scenarios.
- Interpretation: Phase 7 UI requirement is partially met at source/test level. A live Streamlit smoke remains tied to Docker/service runtime and is not claimed.
- Decision: keep UI helpers separate from Streamlit runtime code for testability; Dockerfile now copies both UI modules.
- Lesson learned: UI contract checks can be covered with pure helpers while VM Docker remains blocked.
- Next experiment: implement CI/reproduction smoke commands or portfolio documentation while Docker/GCP and coordinate-backed GIS remain blocked.

## EXP-0026: Remote Reproduction Smoke Target

- Timestamp in Asia/Bangkok: 2026-07-26 20:09:20
- Hypothesis: A reusable non-Docker smoke path can verify source syntax and focused product contracts on the VM in under 15 minutes without requiring live cloud credentials.
- Local Git commit or working-tree identifier: `09c2d16` plus uncommitted smoke target source/docs.
- Dataset snapshot ID and checksums: focused tests use fixtures and existing VM gold artifacts as needed; no new dataset download.
- Exact remote command: `make remote-reproduce-smoke`.
- Configuration and seed: local secret/path scan, `scripts/remote/sync_to_vm.sh`, VM `py_compile` for key API/script/UI modules, focused pytest set for ETL/HF/contracts/comparables/AVM/lifecycle/monitoring/API/UI.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: end-to-end smoke 5 seconds; focused pytest 61 tests in 3.24 seconds; final full suite 139 tests in 11.11 seconds.
- Peak RAM when available: not measured.
- Metrics: smoke exit 0; Ruff lint 0 errors; Docker explicitly skipped because VM Docker socket/Compose access remains blocked; GCP explicitly skipped because VM access token scope remains insufficient.
- Baseline comparison: prior `remote-reproduce-smoke` was an alias for full pytest only and did not record evidence or blocker status. The new target is a measured CI-style smoke path.
- Interpretation: smoke CI path duration criterion passes for the non-Docker/non-cloud scope. Docker build, Terraform validation, vulnerability scan, coverage, and Cloud Run smoke remain incomplete.
- Decision: keep this as the PR/portfolio smoke path until Docker/GCP permissions are fixed.
- Lesson learned: reproduction targets should be explicit about what they prove and what they skip.
- Next experiment: add coverage/type/lint/vulnerability checks if dependencies are available or document precise tooling blockers without installing locally.

## EXP-0027: Scoped Remote Coverage Measurement

- Timestamp in Asia/Bangkok: 2026-07-26 20:21:39
- Hypothesis: The current VM-verified test suite can produce a reproducible coverage signal without installing dependencies or running tests locally.
- Local Git commit or working-tree identifier: `1cc380d` plus uncommitted reusable coverage target.
- Dataset snapshot ID and checksums: coverage run uses the existing VM workspace and fixtures/artifacts; no new dataset download.
- Exact remote command: `make remote-coverage-smoke`.
- Configuration and seed: normal pytest configuration; coverage report scoped to `api/*`, `src/*`, and `scripts/property_*.py`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: pytest under coverage 16.29 seconds; wrapper runtime 19 seconds.
- Peak RAM when available: not measured.
- Metrics: coverage exit 0; 139 tests passed; total scoped coverage 81%; weakest measured modules were `src/data_prep.py` 31%, `src/scorecard.py` 48%, and `api/model_loader.py` 49%.
- Baseline comparison: prior smoke had Ruff and focused pytest evidence but no coverage measurement.
- Interpretation: coverage is now measured and portfolio-ready, but not yet enforced as a CI gate; legacy paths need targeted tests or explicit exclusion before setting a hard threshold.
- Decision: keep `make remote-coverage-smoke` as a reusable coverage evidence path, not as a pass/fail quality gate.
- Lesson learned: source coverage can look healthy overall while important older modules remain under-tested.
- Next experiment: add type or vulnerability evidence if available on the VM, or document precise blockers without installing tooling locally.

## EXP-0028: Remote Dependency Vulnerability Audit

- Timestamp in Asia/Bangkok: 2026-07-26 20:33:58
- Hypothesis: The resolved dependency set can be audited on the VM and produce small, commit-safe evidence without installing tooling locally.
- Local Git commit or working-tree identifier: `334be2f` plus uncommitted vulnerability target/evidence/docs.
- Dataset snapshot ID and checksums: no dataset used.
- Exact remote command: `make remote-vulnerability-smoke`.
- Configuration and seed: VM `uv export --all-extras --dev --format requirements-txt --no-hashes`; `uvx pip-audit` JSON and text reports.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: 33 seconds.
- Peak RAM when available: not measured.
- Metrics: `pip_audit_exit=1`; 59 known vulnerabilities across 11 packages; affected packages are `aiohttp`, `cryptography`, `gitpython`, `python-dotenv`, `starlette`, `nltk`, `pillow`, `pyasn1`, `streamlit`, `tornado`, and `ujson`; local `credit-mlops` package skipped because it is not on PyPI.
- Baseline comparison: no prior dependency vulnerability evidence existed.
- Interpretation: vulnerability audit execution is reproducible, but the security gate fails.
- Decision: do not blind-upgrade dependencies inside this evidence commit; remediation requires a separate VM compatibility run because several affected packages are transitive and framework-constrained.
- Lesson learned: security scans should be reported as first-class evidence even when they fail.
- Next experiment: plan and test dependency upgrades on the VM, then rerun Ruff, coverage, full tests, API smoke, and vulnerability audit.

## EXP-0029: Portfolio README and Reproduction Packaging

- Timestamp in Asia/Bangkok: 2026-07-26 20:42:23
- Hypothesis: The repository entrypoint can accurately present the Property Intelligence platform without claiming unmeasured Docker, GIS, or GCP outcomes.
- Local Git commit or working-tree identifier: `e08e630` plus uncommitted README/report docs.
- Dataset snapshot ID and checksums: documentation references existing evidence only; no data used.
- Exact remote command: not applicable; documentation packaging follows already verified remote smoke, coverage, and vulnerability evidence.
- Configuration and seed: README and `reports/reproduce.md` updated against current measured docs.
- VM hardware/environment: no new VM runtime.
- Runtime: not applicable.
- Peak RAM when available: not measured.
- Metrics: README now lists measured ETL, AVM, API, monitoring, UI, quality, and security evidence; `reports/reproduce.md` now lists three verified remote targets and three blocked targets.
- Baseline comparison: prior README and report reproduction guide were local/Docker-first credit-scoring docs and contradicted the remote-first contract for this branch.
- Interpretation: portfolio packaging is now aligned with measured evidence and blockers.
- Decision: keep current README concise and evidence-led, with detailed evidence delegated to `docs/` and `reports/results.md`.
- Lesson learned: portfolio docs must be rewritten when the project shape changes; stale quick-start instructions can become safety violations.
- Next experiment: dependency remediation planning and compatibility-tested upgrades on the VM.

## EXP-0030: Dependency Remediation Resolver Probe

- Timestamp in Asia/Bangkok: 2026-07-26 20:45:07
- Hypothesis: The failing vulnerability audit can be remediated by raising vulnerable package pins without destabilizing the dependency graph.
- Local Git commit or working-tree identifier: `4def17c` plus uncommitted resolver probe evidence/docs.
- Dataset snapshot ID and checksums: no dataset used.
- Exact remote command: VM `/tmp` resolver sandbox with copied `pyproject.toml` and `uv.lock`; `uv lock --dry-run --upgrade` after proposed pin edits.
- Configuration and seed: probe 1 pinned vulnerable direct/transitive fixes while keeping `mlflow==3.12.0`; probe 2 allowed `mlflow>=3.12.0`, `fastapi>=0.136.3`, `streamlit==1.54.0`, `starlette==1.3.1`, and fixed vulnerable transitives.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: resolver probe 1 and probe 2 each completed in under 2 seconds.
- Peak RAM when available: not measured.
- Metrics: probe 1 failed because `mlflow==3.12.0` requires `cryptography>=43.0.0,<47` and the audit fix requires `cryptography==48.0.1`; probe 2 resolved 172 packages and would update MLflow to 3.14.0, FastAPI to 0.140.0, Starlette to 1.3.1, Streamlit to 1.54.0, and many transitives.
- Baseline comparison: vulnerability audit found 59 known vulnerabilities across 11 packages.
- Interpretation: vulnerability remediation is possible at resolver level but broad enough to require a full compatibility test cycle before changing committed pins and lockfile.
- Decision: do not apply the broad dependency update in this probe commit.
- Lesson learned: security remediation can be constrained by model lifecycle frameworks; resolver success is not enough evidence for production readiness.
- Next experiment: apply the broad update in a controlled VM-backed source change, run `uv lock`, `uv sync --frozen --all-extras --dev`, Ruff, full tests, coverage, API smoke, and `pip-audit`.

## EXP-0031: Dependency Remediation Compatibility Run

- Timestamp in Asia/Bangkok: 2026-07-26 20:51:13
- Hypothesis: The broad resolver-compatible dependency update clears `pip-audit` findings while preserving non-Docker API/test behavior on the VM.
- Local Git commit or working-tree identifier: `9ad8a38` plus uncommitted dependency pins, lockfile, evidence, and docs.
- Dataset snapshot ID and checksums: property API smoke uses existing VM gold snapshot revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; no new dataset download.
- Exact remote commands: `uv lock --upgrade`; `uv sync --frozen --all-extras --dev`; `uvx ruff check . --output-format=concise && uv run pytest -q`; `make remote-coverage-smoke`; `uv run python scripts/property_api_smoke.py`; `make remote-vulnerability-smoke`.
- Configuration and seed: direct pins updated for MLflow 3.14.0, FastAPI 0.140.0, python-dotenv 1.2.2, Streamlit 1.54.0, and security constraints for `aiohttp`, `cryptography`, `gitpython`, `nltk`, `pillow`, `pyasn1`, `starlette`, `tornado`, and `ujson`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: lock 1 second; sync 6 seconds; Ruff + full pytest wrapper 27 seconds; coverage wrapper 23 seconds; API smoke wrapper 5 seconds; vulnerability audit wrapper 33 seconds.
- Peak RAM when available: not measured.
- Metrics: Ruff 0 errors; 139 tests passed in 22.96 seconds with 1 FastAPI/Starlette TestClient deprecation warning; coverage 81% with 139 tests in 18.58 seconds; property API smoke returned 200 for comparables, AVM, and lending; `pip_audit_exit=0`, 0 known vulnerabilities.
- Baseline comparison: previous `pip-audit` found 59 known vulnerabilities across 11 packages.
- Interpretation: dependency security gate now passes for the non-Docker VM scope. The deprecation warning is not a functional failure but should be tracked.
- Decision: keep the dependency pin and lockfile update.
- Lesson learned: broad security upgrades need both resolver evidence and product smoke evidence; the successful audit alone would not have been enough.
- Next experiment: handle the FastAPI/Starlette `httpx`/`httpx2` TestClient deprecation warning or continue with remaining Docker/GCP/GIS blockers.

## EXP-0032: FastAPI/Starlette TestClient Warning Remediation

- Timestamp in Asia/Bangkok: 2026-07-26 21:18:02
- Hypothesis: Adding Starlette's supported `httpx2` TestClient dependency removes the post-upgrade deprecation warning without breaking the API test suite, coverage, or vulnerability gate.
- Local Git commit or working-tree identifier: `45cbb6a` plus uncommitted `httpx2` dependency, lockfile, evidence, and docs.
- Dataset snapshot ID and checksums: existing VM gold snapshot revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`; no new dataset download.
- Exact remote commands: `uv run --with httpx2 pytest -q tests/test_api.py tests/test_deployment.py tests/test_chaos.py -W default`; `uv lock`; `uv sync --frozen --all-extras --dev`; `uvx ruff check . --output-format=concise && uv run pytest -q -W default`; `make remote-coverage-smoke`; `make remote-vulnerability-smoke`.
- Configuration and seed: dev dependencies add `httpx2==2.9.1`; lockfile adds `httpcore2==2.9.1` and `truststore==0.10.4`; no model or random-seed changes.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: focused `httpx2` probe 4.89 seconds for 39 tests; lock 0 seconds; sync 0 seconds; Ruff + full pytest wrapper 14 seconds; coverage wrapper 19 seconds; vulnerability audit wrapper 41 seconds.
- Peak RAM when available: not measured.
- Metrics: focused probe passed 39 tests with no warning summary; Ruff 0 errors; warnings-enabled full suite passed 139 tests in 11.20 seconds with no warning summary; coverage 81% with 139 tests in 15.91 seconds; `pip_audit_exit=0`, 0 known vulnerabilities.
- Baseline comparison: EXP-0031 passed 139 tests in 22.96 seconds but emitted 1 FastAPI/Starlette TestClient deprecation warning.
- Interpretation: `httpx2` is a dev-only compatibility dependency that removes noisy TestClient warnings while preserving the remediated dependency security posture.
- Decision: keep `httpx2==2.9.1` in dev dependency groups.
- Lesson learned: framework deprecation warnings should be closed through the documented compatibility package when possible, then verified with warnings enabled rather than suppressed.
- Next experiment: remaining blocked done criteria require Docker socket/Compose access, GCP OAuth/IAM fixes, or legitimate coordinate enrichment.

## EXP-0033: Remote Type-Check Smoke

- Timestamp in Asia/Bangkok: 2026-07-26 21:29:41
- Hypothesis: The new property intelligence modules, API code, and selected property scripts can pass a reproducible VM-only type-check smoke after narrow typing fixes.
- Local Git commit or working-tree identifier: `a1d4e02` plus uncommitted type-smoke target, typing fixes, evidence, and docs.
- Dataset snapshot ID and checksums: not applicable; type checking does not read datasets.
- Exact remote command: `make remote-type-smoke`.
- Configuration and seed: pinned `mypy==1.18.2`; options `--ignore-missing-imports --follow-imports=silent`; checked `src/property_intelligence`, `api`, `scripts/property_api_smoke.py`, `scripts/property_monitoring_drift.py`, and `scripts/property_avm_promotion_gate.py`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: type-smoke wrapper runtime 1 second; final Ruff + warnings-enabled full-suite wrapper runtime 13 seconds.
- Peak RAM when available: not measured.
- Metrics: `type_smoke_exit=0`; mypy found 0 issues in 19 source files; Ruff 0 errors; final warnings-enabled suite passed 139 tests in 11.16 seconds.
- Baseline comparison: initial direct mypy probe failed with 14 errors across 4 files before type-only fixes.
- Interpretation: type-check smoke now covers the new production API/property surface, but it is intentionally scoped and does not claim full-repository strict typing.
- Decision: keep `make remote-type-smoke` as a reusable VM evidence path.
- Lesson learned: scoped type checks can expose real optional-state and scalar-conversion bugs without requiring a disruptive full-repo typing migration.
- Next experiment: remaining blocked done criteria require Docker socket/Compose access, GCP OAuth/IAM fixes, or legitimate coordinate enrichment.

## EXP-0034: GCP Terraform Source Validation

- Timestamp in Asia/Bangkok: 2026-07-26 21:39:59
- Hypothesis: A conservative GCP Terraform scaffold can cover the required managed-resource shape and validate on the VM without cloud mutation while IAM/OAuth and Docker image prerequisites remain blocked.
- Local Git commit or working-tree identifier: `b3273ad` plus uncommitted Terraform scaffold, validation script, evidence, and docs.
- Dataset snapshot ID and checksums: not applicable; Terraform validation does not read datasets.
- Exact remote command: `make remote-terraform-validate`.
- Configuration and seed: Terraform 1.9.8 installed/reused under the VM user path; Google provider 6.50.0; backend disabled; Cloud SQL/PostGIS scaffold present but `enable_cloud_sql=false` by default.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: 2 seconds.
- Peak RAM when available: not measured.
- Metrics: `terraform_validate_exit=0`; `terraform fmt -check -recursive` passed; `terraform init -backend=false` passed; `terraform validate` passed.
- Baseline comparison: no prior `infra/terraform` source or Terraform validation evidence existed.
- Interpretation: GCP source scaffolding is now reproducible and syntactically valid, but it is not deployment evidence because no plan/apply, Docker image build/push, or live cloud smoke ran.
- Decision: keep the Terraform scaffold and validation target; do not run plan/apply until VM GCP OAuth/IAM and Docker image prerequisites are fixed.
- Lesson learned: Terraform validation can advance cloud architecture evidence without mutating cloud state, but it must be labeled separately from deployment.
- Next experiment: Docker build/push and live GCP plan/apply remain blocked by VM Docker socket/Compose access and GCP OAuth/IAM.

## EXP-0035: Docker Context Secret/Data Guard

- Timestamp in Asia/Bangkok: 2026-07-26 21:46:09
- Hypothesis: Docker packaging can be hardened at source level by excluding secrets/generated artifacts and removing baked `.env` copies, even while Docker build/runtime remains blocked.
- Local Git commit or working-tree identifier: `75379fa` plus uncommitted `.dockerignore`, Dockerfile hardening, evidence, and docs.
- Dataset snapshot ID and checksums: not applicable; Docker context guard does not read datasets.
- Exact remote command: source guard command captured in `docs/evidence/phase6_docker_context_guard_20260726.txt`.
- Configuration and seed: `.dockerignore` excludes `.env`, generated data layers, remote model directories, Terraform state/plans, generated evidence/report paths, and secrets; API and monitoring Dockerfiles no longer copy `.env`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: 0 seconds.
- Peak RAM when available: not measured.
- Metrics: `docker_context_guard_exit=0`; `.env`, `data/raw`, and `artifacts/models` exclusions verified; recursive Dockerfile check found no `COPY .env`; Docker client 29.1.3 still fails daemon access with permission denied.
- Baseline comparison: prior Dockerfile source copied `.env`, and no `.dockerignore` existed.
- Interpretation: Docker source safety is improved, but this is not Docker build evidence because daemon access remains blocked.
- Decision: keep the Docker context guard and do not run Docker build/up until VM socket/Compose access is fixed.
- Lesson learned: remove secret-copy hazards before container runtime is available; source hardening and build evidence are separate milestones.
- Next experiment: superseded by EXP-0037 for Docker socket/build evidence; Compose smoke still requires a Compose command on the VM.

## EXP-0036: Container Dependency Alignment And Monitoring Audit Blocker

- Timestamp in Asia/Bangkok: 2026-07-26 21:52:20
- Hypothesis: Legacy container dependency pins can be aligned with the remediated project dependency set and audited without building Docker images.
- Local Git commit or working-tree identifier: `6a1f0cf` plus uncommitted requirements/UI Dockerfile changes, evidence, and docs.
- Dataset snapshot ID and checksums: not applicable; dependency audit does not read datasets.
- Exact remote command: UI dependency import plus `uvx pip-audit -r requirements.txt` and `uvx pip-audit -r requirements-monitor.txt`, captured in `docs/evidence/phase6_container_dependency_alignment_20260726.txt`.
- Configuration and seed: `requirements.txt` aligned to remediated MLflow/FastAPI/python-dotenv/security pins; `requirements-monitor.txt` aligns `python-dotenv==1.2.2`; `ui/Dockerfile` uses `streamlit==1.54.0`.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: 28 seconds.
- Peak RAM when available: not measured.
- Metrics: UI dependency import passed with Streamlit 1.54.0 and requests 2.34.2; main requirements audit exit 0; monitoring requirements audit exit 1 with `PYSEC-2024-231` in transitive `lightgbm 4.5.0`.
- Baseline comparison: `requirements.txt`, `requirements-monitor.txt`, and `ui/Dockerfile` previously carried stale pre-remediation pins.
- Interpretation: main/API/UI container dependency source is better aligned, but monitoring image audit remains blocked by NannyML resolving a vulnerable LightGBM version.
- Decision: keep safe alignment changes; do not pin incompatible `lightgbm==4.6.0` because it conflicts with available NannyML 0.13.x releases.
- Lesson learned: transitive security fixes can be constrained by monitoring frameworks; record the failed compatible-fix attempt instead of making requirements unsatisfiable.
- Next experiment: revisit monitoring image dependencies when NannyML releases a compatible LightGBM fix, or redesign the monitor image to avoid the vulnerable path.

## EXP-0037: Remote Docker Build And Plain-Container Smoke

- Timestamp in Asia/Bangkok: 2026-07-26 22:51:40
- Hypothesis: After SSH agent restoration and Docker group refresh, plain Docker builds and container health checks can run on the VM even though the Docker Compose plugin is still unavailable.
- Local Git commit or working-tree identifier: `0fd6708` plus uncommitted Docker/GCP evidence and documentation.
- Dataset snapshot ID and checksums: no new data was generated; Docker build context uses committed source plus existing small fallback artifacts already present in the repository, while generated HF datasets and remote model directories remain ignored.
- Exact remote commands: Docker daemon/GCP recheck; `docker build --check` probe; `docker build -f ui/Dockerfile -t credit-mlops-ui:codex-20260726 .`; `docker build -f Dockerfile -t credit-mlops-api:codex-20260726 .`; `docker build -f monitoring/Dockerfile.monitor -t credit-mlops-monitor:codex-20260726 .`; plain `docker run` smoke checks for API, UI, and monitoring imports.
- Configuration and seed: image tag suffix `codex-20260726`; API smoke used fallback local model artifacts and no registry secret; UI smoke used `API_URL=http://127.0.0.1:18000`; monitoring smoke imported NannyML/Pandas/LightGBM only and did not run the batch monitor.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: daemon/GCP recheck 1/9 seconds; build-check probe 0 seconds; UI build 55 seconds; API build 286 seconds; monitor build 298 seconds; API smoke 21 seconds; UI smoke 19 seconds; monitor import smoke 3 seconds.
- Peak RAM when available: not measured.
- Metrics: Docker daemon access now works for `ducan` in group `docker`; Docker server/client 29.1.3; `docker compose` remains unavailable; `docker build --check` is unsupported by the legacy builder and exits 125; UI image `94df2d30ecb0` size 837MB; API image `b4e4dcd3afd7` size 3.01GB; monitor image `ab3038d25eeb` size 3.64GB; API `/health` returned `{"status":"ok","model_version":"fallback_local","uptime_s":9.1}` and Docker health `healthy`; UI `/_stcore/health` returned `ok` and Docker health `healthy`; monitoring image imports passed with NannyML 0.13.1, Pandas 2.2.3, and LightGBM 4.5.0.
- Baseline comparison: EXP-0035 could only verify Docker context safety because daemon access failed with permission denied.
- Interpretation: remote Docker build/runtime evidence is now available for individual images, but Compose orchestration, Postgres/Redis/MLflow service integration, image push, and Cloud Run deployment are still not measured.
- Decision: keep the image build and plain-container smoke evidence; do not claim `remote-up`, Compose, or cloud deployment completion until Compose and GCP blockers are cleared.
- Lesson learned: Docker readiness is layered. Group membership fixed daemon access, but Compose availability and vulnerable monitoring transitive dependencies remain separate blockers.
- Next experiment: install or enable a Compose-compatible command on the VM if approved/available, then run `remote-up`/Compose smoke; otherwise continue GCP read-only/IAM diagnosis and source-only cloud hardening.

## EXP-0038: Isolated Docker Compose Core Stack Smoke

- Timestamp in Asia/Bangkok: 2026-07-26 23:00:30
- Hypothesis: A user-level Docker Compose plugin plus VM-only default `.env` can validate the core Postgres/Redis/API/UI stack without committing secrets or leaving runtime state behind.
- Local Git commit or working-tree identifier: `1b2ff7b` plus uncommitted `remote-compose-smoke` orchestration, evidence, and documentation.
- Dataset snapshot ID and checksums: no new dataset or model artifact generated. Compose used the VM workspace and Docker volumes under isolated project `credit_mlops_codex_smoke`, then removed its own containers/volume.
- Exact remote command: `bash scripts/remote/compose_smoke.sh`.
- Configuration and seed: Docker Compose plugin `v5.3.1` installed under `$HOME/.docker/cli-plugins`; `COMPOSE_PROJECT_NAME=credit_mlops_codex_smoke`; core services `postgres`, `redis`, `api`, and `ui`; `.env` created on the VM only with a no-secret comment if missing.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: 74 seconds.
- Peak RAM when available: not measured.
- Metrics: `compose_smoke_exit=0`; `docker compose config --quiet` passed; API/UI Compose builds passed using cached layers; Postgres, Redis, API, and UI reached Docker health `healthy`; API `/health` returned `{"status":"ok","model_version":"fallback_local","uptime_s":11.2}`; UI health returned `ok`; `docker compose down -v --remove-orphans` removed the isolated containers, network, and Postgres volume.
- Baseline comparison: EXP-0037 could only run individual `docker run` smokes because `docker compose` was unavailable.
- Interpretation: core Docker Compose service wiring is now verified for API/UI with Postgres and Redis. Monitoring-profile batch job, Prometheus/Grafana stack, Dockerized load tests, image push, and Cloud Run deployment are still not measured.
- Decision: keep `make remote-compose-smoke` as the reusable VM Compose evidence path and keep `remote-up`/deployment claims separate.
- Lesson learned: create VM-only runtime defaults instead of syncing local `.env`; isolated Compose project names make teardown safe and auditable.
- Next experiment: extend Compose evidence to monitoring profile and/or Dockerized load tests, then proceed to Artifact Registry/Cloud Run only after GCP Cloud Resource Manager/IAM/API access is fixed.

## EXP-0039: Read-Only GCP Deployment Prerequisite Smoke

- Timestamp in Asia/Bangkok: 2026-07-26 23:06:44
- Hypothesis: A reusable read-only cloud smoke can distinguish working VM authentication from missing project APIs/IAM before any Terraform plan/apply, image push, or deployment attempt.
- Local Git commit or working-tree identifier: `85257f7` plus uncommitted `remote-cloud-smoke` script, GCP evidence, and documentation.
- Dataset snapshot ID and checksums: not applicable; no data or model artifact was read, written, or moved.
- Exact remote command: `bash scripts/remote/cloud_smoke.sh`.
- Configuration and seed: project `driven-reef-452414-b5`, region `asia-southeast1`, VM active account `582914829900-compute@developer.gserviceaccount.com`; read-only `gcloud` list/describe commands only.
- VM hardware/environment: Ubuntu 24.04.4 LTS, 4 vCPU AMD EPYC 7B12, 15 GiB RAM, no GPU.
- Runtime: 10 seconds.
- Peak RAM when available: not measured.
- Metrics: `gcp_readonly_smoke_exit=1`; `auth_exit=0`; `project_config_exit=0`; filtered Service Usage list returned only `serviceusage.googleapis.com` enabled; `project_describe_exit=1` because Cloud Resource Manager API is disabled/permissioned for consumer project `582914829900`; `artifact_repos_exit=1` because Artifact Registry API is disabled for `driven-reef-452414-b5`; `cloud_run_services_exit=1` because Cloud Run Admin API is disabled for `driven-reef-452414-b5`; `scheduler_jobs_exit=1` because Cloud Scheduler API is disabled for `driven-reef-452414-b5`.
- Baseline comparison: the previous `remote-cloud-smoke` only checked `gcloud services list` and could pass while deployment prerequisites were still blocked.
- Interpretation: VM auth is present, but live deployment cannot proceed truthfully until required GCP APIs are enabled and IAM is granted.
- Decision: make `make remote-cloud-smoke` call the reusable diagnostic script and exit nonzero when cloud prerequisites are blocked.
- Lesson learned: a cloud smoke should check every deployment prerequisite explicitly; a single successful Service Usage list is not deployment readiness.
- Next experiment: after APIs/IAM are fixed, rerun `make remote-cloud-smoke`, then run Terraform plan and image push/deploy only with cost-sensitive deployment approval.
