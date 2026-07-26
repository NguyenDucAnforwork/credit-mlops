# Progress

Last updated: 2026-07-27 00:05:00 Asia/Bangkok

## Phase Checklist

- Phase 0 audit and remote baseline: partially complete; tests pass, Docker smoke blocked
- Phase 1 ETL: raw snapshot, silver/gold ETL, and data contracts complete with coordinate blocker documented
- Phase 2 PostGIS and GIS: PostGIS/GIS blocked by missing coordinates; non-GIS comparable fallback measured
- Phase 3 AVM: non-GIS median/tabular baselines, three interval calibrations, and remote-only HGB quantile artifact packaging measured
- Phase 4 APIs: scaffold endpoints implemented; local-on-VM uvicorn AVM/lending p95 criteria measured for fallback and artifact-backed service paths
- Phase 5 MLOps and monitoring: AVM promotion gate dry-run, synthetic drift, and delayed-label monitoring implemented
- Phase 6 Docker and GCP: Terraform source scaffold validates and plans on VM; Docker image builds, plain-container API/UI/monitor smokes, core Docker Compose API/UI/Postgres/Redis smoke, and Dockerized API load smoke pass on VM; reusable read-only GCP smoke passes, while live deployment remains intentionally unexecuted
- Phase 7 UI, CI, portfolio: Property Intelligence UI, non-Docker remote smoke reproduction, Ruff smoke, scoped coverage measurement, type-check smoke, vulnerability audit/remediation, TestClient warning remediation, and portfolio README/reproduction packaging implemented

## Evidence

- Local SSH preflight passed for host `lfm`.
- Local GitHub dry-run push returned `Everything up-to-date` before feature branch creation.
- Feature branch created locally: `feat/onemount-property-intelligence`.
- VM inventory captured in `docs/remote_environment.md`.
- GCP access is now verified with the deployer account: project describe, Artifact Registry, Cloud Run, and Scheduler read-only checks pass for `driven-reef-452414-b5`.
- Initial remote bootstrap created the dedicated workspace/sentinel but could not clone with local SSH alias `github-nguyenducan`; the workspace is treated as rsync-backed until the feature branch is pushed.
- Initial remote bootstrap stopped because `uv` was not installed; bootstrap now attempts a user-level `uv` install without sudo.
- `uv sync --frozen --all-extras --dev` completed on the VM and installed 168 packages.
- Baseline data prep on the VM produced data version `cac9de3c`, 16,000 train rows, and 4,000 test rows.
- Original tests passed on the VM: 76 passed in 7.42 seconds; wrapper runtime 9 seconds.
- Initial Docker smoke was blocked because `ducan` was not in the `docker` group and `docker compose` was unavailable; after the 2026-07-26 SSH/group refresh and user-level Compose install, Docker daemon access and core Compose smoke work.
- Phase 1 ETL foundation tests passed on the VM: 10 passed in 0.27 seconds.
- Full suite after Phase 1 foundation passed on the VM: 86 passed in 12.79 seconds; wrapper runtime 15 seconds.
- Incremental fixture evidence: first run inserted exactly 1,000 rows and found exactly 100 duplicates; identical rerun inserted 0 rows.
- Hugging Face metadata captured on the VM for `vduydong/vietnam-real-estates`: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`, 5 Parquet shards, last modified `2026-04-08T06:51:21.000Z`.
- Full suite after HF metadata source module passed on the VM: 89 passed in 7.36 seconds; wrapper runtime 9 seconds.
- HF shard footer manifest measured on the VM without full downloads: 5 shards, 1,000,000 total rows, 19 columns, 469,122,864 total bytes, ETags captured.
- Full suite after shard manifest module passed on the VM: 93 passed in 7.31 seconds; wrapper runtime 9 seconds.
- Full HF snapshot downloaded on the VM only: 5 Parquet shards, 469,122,864 bytes, 1,000,000 rows from footers, full SHA256 for every shard.
- Snapshot download runtime: 74 seconds; rerun/reuse runtime: 12 seconds; disk usage: 448M under `data/raw/vietnam-real-estates`.
- Full suite after snapshot downloader passed on the VM: 96 passed in 7.35 seconds; wrapper runtime 9 seconds.
- Full HF ETL on VM: 1,000,000 raw rows, 893,830 silver rows, 638,123 Hà Nội/Hồ Chí Minh gold rows, 106,170 quarantine rows, 8 duplicate rows.
- ETL runtime: 48 seconds; disk: 407M silver, 287M gold, 52M quarantine.
- Coordinate source columns `latitude` and `longitude` are absent from the actual dataset schema; records are marked `coordinate_status=missing_source_columns`.
- Full suite after HF ETL passed on the VM: 99 passed in 7.38 seconds; wrapper runtime 9 seconds.
- Data contract validation status: `pass_with_blockers`; 9 core checks passed; coordinate-source check failed as blocker.
- Full suite after data contracts passed on the VM: 102 passed in 7.98 seconds; wrapper runtime 10 seconds.
- AVM baseline split: train June-October 2025 = 429,682 rows, validation November 2025 = 100,105 rows, test December 2025 = 108,336 rows.
- Best non-GIS simple baseline: district + property-type median price/m2; December test MdAPE 22.85%, RMSLE 0.4426, MAE 18.52B VND, R2 0.387, within 20% = 44.42%.
- Full suite after AVM baseline passed on the VM: 105 passed in 7.57 seconds; wrapper runtime 9 seconds.
- Non-GIS tabular HGB baseline: December test MdAPE 19.16%, RMSLE 0.3850, MAE 18.66B VND, R2 0.313, within 20% = 51.79%.
- Relative MdAPE improvement over strongest simple baseline: 16.14%.
- Full suite after tabular AVM passed on the VM: 107 passed in 7.69 seconds; wrapper runtime 9 seconds.
- First interval calibration: empirical 80% interval coverage 79.61%, median interval width ratio 83.79%, p90 width ratio 83.79%; coverage passes but width fails the <=50% target.
- Full suite after interval calibration passed on the VM: 108 passed in 7.73 seconds; wrapper runtime 10 seconds.
- Cohort interval calibration using province/property-type residual bands: empirical 80% interval coverage 79.29%, median interval width ratio 82.32%, p90 width ratio 107.48%; 6 qualified cohorts; 0.90% global fallback; medium-confidence share 21.63%; width still fails the <=50% target.
- Targeted AVM tests plus full suite before cohort experiment passed on the VM: 7 AVM tests in 0.90 seconds and 109 total tests in 7.81 seconds.
- Final full suite after cohort docs/evidence passed on the VM: 109 passed in 9.44 seconds; wrapper runtime 12 seconds.
- Direct quantile HGB intervals: empirical 80% interval coverage 78.67%, median interval width ratio 76.99%, p90 width ratio 134.16%; high-confidence share 14.33%, medium-confidence share 39.30%, low-confidence share 46.37%; width still fails the <=50% target.
- Targeted AVM tests plus full suite before quantile experiment passed on the VM: 8 AVM tests in 1.13 seconds and 110 total tests in 8.02 seconds.
- Final full suite after quantile docs/evidence passed on the VM: 110 passed in 7.98 seconds; wrapper runtime 10 seconds.
- Non-GIS comparable fallback benchmark: 1,000 December queries; median latency 8.65 ms; p95 14.88 ms; max 18.64 ms; 0% valid-request errors; 10 comparables for every sampled query; distance status `not_available_missing_coordinates`.
- Focused comparable tests plus full suite before benchmark passed on the VM: 2 comparable tests in 0.65 seconds and 112 total tests in 8.13 seconds.
- Final full suite after comparable docs/evidence passed on the VM: 112 passed in 8.12 seconds; wrapper runtime 10 seconds.
- API scaffold: added `POST /v1/avm/predict`, `GET /v1/comparables`, and `POST /v1/lending/decision` while preserving `/health`, `/predict`, and `/metrics`.
- API tests: 14 focused API tests passed in 1.98 seconds; full suite passed with 118 tests in 8.16 seconds before smoke.
- Real-data API smoke via FastAPI TestClient on the VM: `/v1/comparables` 200 with 10 comparables and 2,624.48 ms cold index latency; `/v1/avm/predict` 200 with 4.95B VND estimate and 13.13 ms latency after index build; `/v1/lending/decision` 200 with conservative LTV 0.75 approved in 2.63 ms.
- Final full suite after API docs/evidence passed on the VM: 118 passed in 8.16 seconds; wrapper runtime 10 seconds.
- AVM promotion gate dry-run: decision `reject`; temporal MdAPE relative improvement 16.14% and interval coverage 78.67% passed, but median interval-width ratio 76.99%, missing spatial holdout, missing major cohort regression report, and missing warm API p95 report block promotion.
- Lifecycle tests plus full suite before gate passed on the VM: 8 lifecycle tests in 0.65 seconds and 126 total tests in 8.20 seconds.
- Final full suite after lifecycle docs/evidence passed on the VM: 126 passed in 8.27 seconds; wrapper runtime 10 seconds.
- Test-count numeric floor status: 126 total passing tests meets the >=125 criterion.
- Synthetic property drift monitoring: shifted area, price/m2, interval width, district missingness, and confidence; status `alert`; 4 alerting checks for `area_m2`, `price_per_m2`, `interval_width_ratio`, and `missing_feature_share`.
- Monitoring tests plus full suite before drift run passed on the VM: 3 monitoring tests in 0.63 seconds and 129 total tests in 8.26 seconds.
- Final full suite after monitoring docs/evidence passed on the VM: 129 passed in 8.15 seconds; wrapper runtime 10 seconds.
- Warm API TestClient load benchmark: 1,000 AVM requests and 1,000 lending requests at concurrency 10; AVM p95 176.43 ms with 0% errors; lending p95 64.71 ms with 0% errors; scope is in-process VM TestClient, not Docker/uvicorn service.
- Full suite after API load benchmark passed on the VM: 129 passed in 8.20 seconds; wrapper runtime 10 seconds.
- Warm uvicorn HTTP API benchmark: 1,000 AVM requests and 1,000 lending requests at concurrency 10; AVM p95 140.84 ms with 0% errors; lending p95 24.21 ms with 0% errors; scope is VM uvicorn service, not Docker or Cloud Run.
- No lingering uvicorn process remained after the benchmark; final full suite passed on the VM: 129 passed in 8.24 seconds; wrapper runtime 10 seconds.
- Delayed-label AVM monitoring: 2,000 December labels; fallback comparable MdAPE 16.73%, MAE 5.30B VND, within 20% 56.55%, median comparable count 10, distance availability 0%.
- District/property-type bias monitoring: 10 cohorts with >=50 rows; 0 alerts above +5 MdAPE points; worst cohort Bình Thạnh house MdAPE 20.56%, +3.83 points vs overall.
- Final full suite after delayed-label monitoring passed on the VM: 130 passed in 8.20 seconds; wrapper runtime 10 seconds.
- API startup warm-up: property comparable index now warms during FastAPI lifespan; startup latency 4,849.08 ms; first comparable request after startup 10.99 ms versus prior 2,640.39 ms cold request.
- Warm uvicorn HTTP benchmark after startup warm-up: AVM p95 137.81 ms with 0% errors; lending p95 13.56 ms with 0% errors; no lingering uvicorn process remained.
- Final full suite after startup warm-up passed on the VM: 132 passed in 10.73 seconds; wrapper runtime 13 seconds.
- HGB quantile AVM artifact packaged on the VM only: `artifacts/models/property_avm_hgb_quantile_20260726.joblib`, 2,480,557 bytes / 2.37 MB, load latency 87.13 ms, single prediction latency 21.32 ms.
- Artifact training/evaluation runtime: 26.40 seconds; script runtime including same-seed reproducibility rerun: 55 seconds; same-seed MdAPE delta 0.0 percentage points.
- Artifact-backed uvicorn HTTP benchmark: AVM p95 136.63 ms with 0% errors; lending p95 15.53 ms with 0% errors; startup latency 4,855.76 ms; first comparable request after startup 11.07 ms.
- Focused artifact/API tests passed on the VM: 27 passed in 3.06 seconds; final full suite passed with 135 tests in 11.15 seconds; wrapper runtime 13 seconds.
- Streamlit Property Intelligence workspace added: map reference input, property attributes, estimate/interval/comparables/factors display, credit decision + requested-loan input, LTV policy decision, disclaimer, and scenarios for Hà Nội apartment, Hồ Chí Minh City house, and low-support manual review.
- UI helper tests passed on the VM: 4 passed in 0.04 seconds; `ui/streamlit_app.py` and `ui/property_workflow.py` compiled successfully.
- Final full suite after UI work passed on the VM: 139 passed in 11.06 seconds; wrapper runtime 13 seconds.
- `make remote-reproduce-smoke` added as a reusable non-Docker smoke path. It ran local secret/path scans, synced to the VM, compiled key API/script/UI modules, ran Ruff with 0 errors, ran 61 focused tests in 3.24 seconds, and completed in 5 seconds.
- The older remote reproduction smoke reported Docker/GCP skipped before Compose and GCP status were rechecked; later evidence adds core Compose success, while GCP project describe remains blocked.
- Final full suite after remote smoke/Ruff work passed on the VM: 139 passed in 11.11 seconds; wrapper runtime 13 seconds.
- `make remote-coverage-smoke` added as a reusable VM coverage path. It ran the full test suite under coverage, passed 139 tests in 16.29 seconds, completed in 19 seconds, and measured 81% total coverage for `api/*`, `src/*`, and `scripts/property_*.py`.
- Weakest measured coverage areas: `src/data_prep.py` 31%, `src/scorecard.py` 48%, and `api/model_loader.py` 49%; this is evidence, not a threshold gate yet.
- `make remote-vulnerability-smoke` added as a reusable VM dependency audit path. It exported resolved dependencies on the VM, ran `pip-audit`, completed in 33 seconds, and wrote JSON/text evidence.
- Initial vulnerability audit result: `pip_audit_exit=1`; 59 known vulnerabilities in 11 packages (`aiohttp`, `cryptography`, `gitpython`, `python-dotenv`, `starlette`, `nltk`, `pillow`, `pyasn1`, `streamlit`, `tornado`, `ujson`). Post-remediation audit result: `pip_audit_exit=0`, 0 known vulnerabilities; local package `credit-mlops` remains skipped because it is not on PyPI.
- README rewritten as the current Property Intelligence & Lending MLOps portfolio entrypoint with measured evidence, remote reproduction commands, API surface, documentation map, and blocker table.
- `reports/reproduce.md` replaced with a remote-first reproduction report pointing to the verified smoke, coverage, and vulnerability targets.
- Dependency remediation probe 1 failed: pinning `cryptography==48.0.1` is unsatisfiable while `mlflow==3.12.0` requires `cryptography<47`.
- Dependency remediation probe 2 succeeded as a dry-run only after allowing a broad upgrade set including `mlflow 3.14.0`, `fastapi 0.140.0`, `starlette 1.3.1`, `streamlit 1.54.0`, `pillow 12.3.0`, `nltk 3.10.0`, and related transitives.
- Dependency remediation applied: `uv lock --upgrade` succeeded in 1 second and `uv sync --frozen --all-extras --dev` succeeded in 6 seconds on the VM.
- Post-remediation compatibility: Ruff passed; full suite passed with 139 tests in 22.96 seconds and 1 FastAPI/Starlette TestClient deprecation warning.
- TestClient warning remediation: adding dev-only `httpx2==2.9.1` locked `httpcore2` and `truststore`; `uv lock` and `uv sync --frozen --all-extras --dev` both completed in 0 seconds on the VM.
- Warnings-enabled compatibility after `httpx2`: Ruff passed and `uv run pytest -q -W default` passed 139 tests in 11.20 seconds with no warning summary; wrapper runtime 14 seconds.
- Post-TestClient-remediation coverage: `make remote-coverage-smoke` passed 139 tests in 15.91 seconds; scoped coverage remained 81%; wrapper runtime 19 seconds.
- Post-remediation property API smoke: comparables, AVM, and lending endpoints returned 200; wrapper runtime 5 seconds.
- Post-TestClient-remediation vulnerability audit: `make remote-vulnerability-smoke` passed with `pip_audit_exit=0`, 0 known vulnerabilities, and 41-second runtime.
- Type-check smoke added: `make remote-type-smoke` runs pinned `mypy==1.18.2` on `src/property_intelligence`, `api`, and selected property scripts; after typing-only fixes, it passed with 0 issues across 19 source files and 1-second wrapper runtime. Final source verification also passed Ruff and 139 warnings-enabled tests in 11.16 seconds; wrapper runtime 13 seconds.
- GCP Terraform scaffold added under `infra/terraform`: required APIs, Artifact Registry, GCS, BigQuery, Secret Manager placeholder, Cloud Run service, Cloud Run ETL job, Scheduler, IAM service accounts, and optional disabled-by-default Cloud SQL/PostGIS scaffold.
- `make remote-terraform-validate` installed/reused user-level Terraform 1.9.8 on the VM, initialized Google provider 6.50.0 with backend disabled, passed `terraform fmt -check -recursive`, passed `terraform validate`, and completed in 2 seconds. No `terraform plan`, `terraform apply`, `gcloud`, Docker build, image push, or cloud deployment was run.
- Docker context guard added: `.dockerignore` excludes `.env`, generated data layers, remote model directories, Terraform state/plans, and generated evidence/report paths; API and monitoring Dockerfiles no longer copy `.env`. Remote guard check passed in 0 seconds before daemon access was refreshed.
- Container dependency alignment: `requirements.txt` updated to match the remediated main dependency set, `requirements-monitor.txt` updated for `python-dotenv==1.2.2`, and `ui/Dockerfile` updated to Streamlit 1.54.0. VM evidence: UI dependency import passed; main requirements audit exit 0; monitoring requirements audit exit 1 due `PYSEC-2024-231` in transitive `lightgbm 4.5.0`.
- Docker/GCP recheck after SSH agent refresh: Docker daemon access works for `ducan` in group `docker`; Docker client/server 29.1.3 respond; GCP active account is `582914829900-compute@developer.gserviceaccount.com` with project `driven-reef-452414-b5`.
- GCP service listing now succeeds for project `driven-reef-452414-b5`, but `gcloud projects describe driven-reef-452414-b5` exits 1 because Cloud Resource Manager API is disabled/permissioned for consumer project `582914829900`; no Terraform plan/apply or deployment was run.
- Docker build-check probe failed as a documented approach: `docker build --check` is unsupported by the VM legacy builder and exited 125 for API/UI/monitoring checks.
- Individual Docker image builds passed on VM: UI `credit-mlops-ui:codex-20260726` ID `94df2d30ecb0`, 837MB, 55 seconds; API `credit-mlops-api:codex-20260726` ID `b4e4dcd3afd7`, 3.01GB, 286 seconds; monitor `credit-mlops-monitor:codex-20260726` ID `ab3038d25eeb`, 3.64GB, 298 seconds.
- Plain Docker container smokes passed without Compose: API `/health` returned `status=ok` and `model_version=fallback_local` with Docker health `healthy`; UI Streamlit `/_stcore/health` returned `ok` with Docker health `healthy`; monitoring image imported NannyML 0.13.1, Pandas 2.2.3, and LightGBM 4.5.0.
- `make remote-compose-smoke` added and verified: user-level Docker Compose v5.3.1 installed/reused on VM, VM-only `.env` default created if missing, `docker compose config --quiet` passed, API/UI Compose builds passed, and isolated `postgres`, `redis`, `api`, and `ui` services all reached Docker health `healthy`.
- Compose core stack HTTP smoke passed: API `/health` returned `status=ok` and `model_version=fallback_local`; UI health returned `ok`; isolated containers, network, and Postgres volume were removed by `docker compose down -v --remove-orphans`.
- `make remote-cloud-smoke` now runs a reusable read-only GCP diagnostic and exits nonzero when prerequisites are blocked. Latest evidence: active account and project config pass; filtered Service Usage list passes; project describe, Artifact Registry, Cloud Run, and Scheduler checks fail because required APIs are disabled or inaccessible.
- Dockerized Compose API load: the first attempt returned AVM 503 because the API container did not have an explicit mounted property gold path. Compose now mounts `./data:/app/data:ro` for API and sets `PROPERTY_GOLD_PATH` to the VM gold parquet.
- Dockerized Compose API load after the fix passed: 1,000 AVM requests and 1,000 lending requests at concurrency 10 against the Dockerized API; AVM p95 283.01 ms and lending p95 33.93 ms with 0% valid-request errors; wrapper runtime 78 seconds.

## 2026-07-27 GCP Plan Update

- Deployer service account/API bootstrap passed on `lfm`: project describe, Artifact Registry, Cloud Run, and Scheduler read-only checks pass.
- Terraform init and plan passed remotely with Terraform 1.9.8/provider 6.50.0 in 3 seconds.
- Measured plan: 30 resources to add, 0 to change, 0 to destroy; Cloud SQL disabled.
- No GCP resources, image push, secret population, apply, Cloud Run smoke, scheduler execution, or rollback test ran.
- Numeric monthly cost is not available from Terraform plan; approved usage assumptions are required.

## Next

Continue Docker/GCP work only on unblocked steps: monitoring-profile Compose can proceed on the VM. Cloud image push, Terraform apply, and live deployment still require immutable image tags, approved secret population, apply-time IAM, cost approval, and post-deploy verification. Legitimate coordinate enrichment is still required for GIS/PostGIS/H3 criteria.
