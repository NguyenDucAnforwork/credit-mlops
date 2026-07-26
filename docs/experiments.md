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
