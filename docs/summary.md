# Summary

Last updated: 2026-07-26 23:16:14 Asia/Bangkok

Status: Phase 6/7 non-cloud portfolio evidence is mostly complete, with Terraform source validation, Docker image builds, plain-container smokes, core Docker Compose smoke, and Dockerized API load evidence added. Remaining blockers are coordinate-backed GIS/PostGIS, monitoring-profile evidence, and live GCP deployment.

The project is being converted from a credit scoring MLOps demo into a Property Intelligence & Lending MLOps Platform. The local repository remains the source of truth, and runtime work is executed on `lfm` in `/home/ducan/credit-mlops-codex`.

## Current Evidence

- SSH to `lfm`: working.
- Feature branch: `feat/onemount-property-intelligence`.
- VM resources: 4 vCPU, 15 GiB RAM, 66 GiB free disk, no GPU.
- GCP access: service listing works for `driven-reef-452414-b5`; project describe is blocked because Cloud Resource Manager API is disabled/permissioned for consumer project `582914829900`.
- Remote workspace: created as rsync-backed after VM Git clone failed on local SSH alias `github-nguyenducan`.
- Baseline tests: 76 passed in 7.42 seconds on the VM.
- Current tests: 139 passed in 15.91 seconds under `make remote-coverage-smoke`; latest warnings-enabled Ruff/full suite passed with 139 tests in 11.20 seconds and no TestClient warning summary.
- Baseline data split: version `cac9de3c`, 16,000 train rows, 4,000 test rows.
- ETL fixture: 1,000 inserts, 100 duplicates, identical rerun 0 inserts.
- HF dataset metadata: revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`, 5 Parquet shards, last modified `2026-04-08T06:51:21.000Z`.
- HF raw snapshot: downloaded on VM only, 1,000,000 total rows, 19 columns, 469,122,864 bytes, full SHA256 captured for 5 shards, 448M disk.
- HF ETL: 893,830 silver rows, 638,123 MVP gold rows, 106,170 quarantine rows, 8 duplicate rows.
- Coordinate blocker: actual source schema lacks `latitude` and `longitude`; no coordinates were fabricated.
- Data contract status: `pass_with_blockers`; core ETL checks pass and coordinate availability is the blocker.
- AVM baseline: district+property-type median price/m2 reached December test MdAPE 22.85% and RMSLE 0.4426 on 108,336 rows.
- Current best non-GIS AVM: HGB log(price/m2), December test MdAPE 19.16%, RMSLE 0.3850, 16.14% relative MdAPE improvement over strongest simple baseline.
- Uncertainty: direct quantile 80% interval coverage 78.67% passes and improves median width to 76.99% with 14.33% high-confidence share, but the <=50% width target still fails and p90 width is 134.16%.
- AVM artifact: HGB point + q10/q90 quantile artifact is packaged on the VM only at `artifacts/models/property_avm_hgb_quantile_20260726.joblib`; size 2.37 MB, load 87.13 ms, single prediction 21.32 ms, same-seed MdAPE delta 0.0 percentage points.
- Comparables: non-GIS fallback benchmark ran 1,000 December queries with p95 14.88 ms and 0% valid-request errors, but distance/radius/PostGIS criteria remain blocked by missing coordinates.
- APIs: `POST /v1/avm/predict`, `GET /v1/comparables`, and `POST /v1/lending/decision` are implemented and smoked with real VM gold data.
- AVM lifecycle: dry-run promotion gate rejects current candidate; temporal improvement and coverage pass, but interval width, spatial holdout, cohort regression, and warm API p95 evidence block promotion.
- Monitoring: synthetic property drift shifts at least three features and triggers 4 alerts across area, price/m2, interval width, and missingness.
- Delayed-label monitoring: 2,000 December labels show fallback comparable MdAPE 16.73%, within 20% 56.55%, 0 cohort alerts above +5 MdAPE points, and 0% distance availability because coordinates are absent.
- Warm uvicorn HTTP load: AVM p95 140.84 ms and lending p95 24.21 ms with 0% errors at 1,000 requests/concurrency 10; Docker and Cloud Run p95 remain unmeasured.
- API startup warm-up: first comparable request after startup is 10.99 ms after moving the 4.85s index load into lifespan startup.
- Artifact-backed API uvicorn load: AVM p95 136.63 ms and lending p95 15.53 ms with 0% valid-request errors at 1,000 requests/concurrency 10.
- Streamlit UI: property-lending workspace added with map reference input, property attributes, estimate/interval/comparables/factors, credit/LTV decision inputs, disclaimer, and three required scenarios.
- Remote smoke reproduction: `make remote-reproduce-smoke` performs local secret/path scan, syncs to VM, compiles key modules, runs Ruff with 0 errors, runs 61 focused tests, and completes in 5 seconds while explicitly skipping Docker/GCP blockers.
- Terraform validation: `make remote-terraform-validate` validates the GCP scaffold on the VM with Terraform 1.9.8 and Google provider 6.50.0; `terraform_validate_exit=0`, runtime 2 seconds, no plan/apply/deployment.
- Type check smoke: `make remote-type-smoke` runs pinned `mypy==1.18.2` on `src/property_intelligence`, `api`, and selected property scripts; it found 0 issues in 19 source files and completed in 1 second. Final source verification also passed Ruff and 139 warnings-enabled tests in 11.16 seconds.
- Coverage measurement after TestClient warning remediation: `make remote-coverage-smoke` passed 139 tests in 15.91 seconds on the VM; scoped coverage for `api/*`, `src/*`, and `scripts/property_*.py` is 81% total, with weakest measured modules `src/data_prep.py` 31%, `src/scorecard.py` 48%, and `api/model_loader.py` 49%.
- Vulnerability audit: initial `pip-audit` found 59 known vulnerabilities across 11 packages; after coordinated dependency remediation and the `httpx2` test-client fix, `make remote-vulnerability-smoke` completes in 41 seconds with `pip_audit_exit=0` and 0 known vulnerabilities.
- Container dependency alignment: UI Docker deps import with Streamlit 1.54.0 and requests 2.34.2; main `requirements.txt` audit exits 0; monitoring requirements audit exits 1 because NannyML resolves `lightgbm 4.5.0` with `PYSEC-2024-231`, while the fixed `lightgbm 4.6.0` conflicts with available NannyML 0.13.x releases.
- Dependency remediation: updated pins/lock for MLflow 3.14.0, FastAPI 0.140.0, Starlette 1.3.1, Streamlit 1.54.0, vulnerable transitives, and dev-only `httpx2==2.9.1`; VM `uv sync --frozen --all-extras --dev` passed, Ruff passed, warnings-enabled full tests passed, coverage passed, API smoke passed, and `pip-audit` passed.
- Portfolio documentation: README and `reports/reproduce.md` now present the remote-first Property Intelligence platform, measured evidence, and explicit blockers instead of the older local-first credit-scoring flow.
- Engineering test-count criterion: 139 passing tests meets the >=125 numeric floor.
- Docker context guard: `.dockerignore` excludes `.env`, raw/silver/gold/quarantine data, remote model directories, Terraform state, and generated evidence/report paths; API and monitoring Dockerfiles no longer copy `.env`.
- Docker build/runtime: daemon access now works for `ducan`; UI, API, and monitoring images built on the VM as `credit-mlops-*:codex-20260726`; API and UI health smokes passed with Docker health `healthy`; monitoring import smoke passed.
- Docker Compose: `make remote-compose-smoke` installed/reused Compose v5.3.1 under the VM user, created a VM-only no-secret `.env` default if missing, passed `docker compose config --quiet`, built API/UI, started isolated Postgres/Redis/API/UI services, reached Docker health `healthy` for all four, verified API/UI HTTP health, and tore down containers/network/volume in 74 seconds.
- Dockerized API load: `make remote-compose-load-smoke` passed after adding the API read-only property data mount; 1,000 AVM and 1,000 lending requests at concurrency 10 returned status 200 with 0% errors, AVM p95 283.01 ms, and lending p95 33.93 ms.
- Cloud smoke: `make remote-cloud-smoke` is now a reusable read-only diagnostic and currently fails as expected with `gcp_readonly_smoke_exit=1`; auth/project config pass, but Cloud Resource Manager, Artifact Registry, Cloud Run Admin, and Cloud Scheduler APIs are disabled or inaccessible.
- Terraform deploy: source validates, but live plan/apply is blocked by VM GCP Cloud Resource Manager/IAM/API access plus image registry push/deployment prerequisites.
- Monitoring container dependency audit: blocked by NannyML transitive LightGBM vulnerability until a compatible NannyML release or monitoring image redesign is available.
- Deployment URL: not deployed.

## Next Step

Continue only on unblocked work unless GCP Cloud Resource Manager/IAM/API access, cost-sensitive deploy approval, or legitimate coordinate enrichment becomes available.
