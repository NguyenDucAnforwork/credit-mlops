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
