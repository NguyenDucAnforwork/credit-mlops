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
