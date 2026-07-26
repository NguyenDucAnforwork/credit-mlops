# Property Intelligence & Lending MLOps

Portfolio MLOps project that extends an existing credit-scoring system into a Vietnam residential property intelligence platform. The repository covers remote execution orchestration, Hugging Face real-estate ETL, AVM experiments with uncertainty, comparable support, credit + LTV decision APIs, monitoring, Streamlit demo workflows, and reproducibility evidence.

Local source is the source of truth. Heavy/runtime work runs on the VM `lfm` in `/home/ducan/credit-mlops-codex`; raw data, generated datasets, model binaries, caches, databases, and cloud state stay off the local repository.

## Current Status

Measured on 2026-07-26 from branch `feat/onemount-property-intelligence`.

| Area | Current measured evidence |
|------|---------------------------|
| Remote baseline | SSH to `lfm` works; VM has 4 vCPU, 15 GiB RAM, 66 GiB free disk, no GPU |
| Source dataset | HF `vduydong/vietnam-real-estates`, revision `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38`, 5 Parquet shards, 1,000,000 rows |
| ETL | 893,830 silver rows; 638,123 Hà Nội/Hồ Chí Minh gold rows; 106,170 quarantine rows; 8 duplicate rows |
| Coordinate status | Source schema lacks `latitude`/`longitude`; GIS/PostGIS/H3 criteria are blocked rather than fabricated |
| AVM | HGB log(price/m2), December 2025 MdAPE 19.16%, RMSLE 0.3850, 16.14% relative MdAPE improvement over strongest simple baseline |
| Uncertainty | Direct q10/q90 intervals: 78.67% empirical coverage, 76.99% median width ratio; coverage passes, width target fails |
| Comparables | Non-GIS fallback p95 14.88 ms for 1,000 December queries, 0% valid-request errors |
| APIs | `/v1/avm/predict`, `/v1/comparables`, `/v1/lending/decision` implemented and smoked on VM data |
| API load | Artifact-backed uvicorn AVM p95 136.63 ms and lending p95 15.53 ms at 1,000 requests/concurrency 10 |
| Model artifact | VM-only HGB quantile joblib, 2.37 MB, load 87.13 ms, single prediction 21.32 ms |
| Monitoring | Synthetic drift triggers 4 alerts; delayed-label fallback replay MdAPE 16.73% on 2,000 labels |
| UI | Streamlit Property Intelligence workspace with three required demo scenarios and LTV decision flow |
| Terraform | VM `terraform init` and `terraform plan` pass with Terraform 1.9.8/provider 6.50.0; plan is 30 add, 0 change, 0 destroy; no apply |
| Docker packaging | `.dockerignore` excludes secrets/raw data/model directories; Dockerfiles no longer copy `.env`; Docker build still blocked |
| Tests/quality | 139 tests pass under coverage in 15.91 seconds; scoped coverage 81%; Ruff, warnings-enabled full suite, and mypy type smoke pass |
| Security audit | Project lock/main requirements audit clean; monitoring container requirements still blocked by NannyML `lightgbm` 4.5.0 vulnerability |

## Known Blockers

| Blocker | Current evidence |
|---------|------------------|
| GIS/PostGIS/H3 | Primary source has no coordinate columns, so spatial holdout, distance, radius, and H3 criteria are not claimed |
| Docker/Compose on VM | Docker daemon, image builds, plain smokes, core Compose stack, and Dockerized API load pass; monitoring profile not measured |
| GCP deployment | deployer account and read-only API/resource smoke pass; image push, apply-time IAM, cost approval, and Cloud Run verification remain |
| AVM promotion | Dry-run gate rejects candidate because interval width, spatial holdout, cohort regression, and production service evidence are incomplete |
| Dependency security | Latest audit is clean; FastAPI/Starlette TestClient warning resolved by adding `httpx2==2.9.1` to dev dependencies |
| Monitoring container audit | `requirements-monitor.txt` resolves vulnerable `lightgbm 4.5.0`; fixed `lightgbm 4.6.0` conflicts with available NannyML releases |

## Architecture

```text
Local repo
  |
  |  git edits, docs, commits, pushes
  |  bash scripts/remote/*.sh
  v
VM lfm:/home/ducan/credit-mlops-codex
  |
  |-- HF metadata/snapshot/ETL -> VM-only raw/silver/gold data
  |-- AVM experiments -> metrics/evidence, remote-only model artifacts
  |-- FastAPI service -> credit scoring + property AVM + comparables + LTV decision
  |-- Streamlit UI -> property-lending demo scenarios
  |-- Monitoring -> synthetic drift and delayed-label replay evidence
  |-- Quality -> Ruff, pytest, coverage, pip-audit
```

## Remote Reproduction

Do not install project dependencies, run tests, train models, build Docker, run Terraform, or call `gcloud` locally. Use the remote Make targets:

```bash
make remote-doctor
make remote-sync
make remote-reproduce-smoke
make remote-coverage-smoke
make remote-vulnerability-smoke
make remote-type-smoke
make remote-terraform-validate
```

Current measured targets:

- `make remote-reproduce-smoke`: local secret/path scan, VM sync, syntax checks, Ruff, 61 focused tests; completed in 5 seconds.
- `make remote-coverage-smoke`: full pytest under coverage on VM; 139 passed in 15.91 seconds, 81% scoped coverage, 19-second wrapper runtime.
- `make remote-vulnerability-smoke`: dependency audit on VM; evidence capture completed in 41 seconds and found 0 known vulnerabilities after remediation.
- `make remote-type-smoke`: pinned mypy on new property intelligence modules, API code, and selected property scripts; 19 source files checked with 0 issues in a 1-second wrapper runtime.
- `make remote-terraform-validate`: GCP Terraform scaffold fmt/init/validate on VM; completed in 2 seconds with `terraform_validate_exit=0`.
- `scripts/remote/run.sh 'terraform -chdir=infra/terraform init -no-color && terraform -chdir=infra/terraform plan -no-color'`: remote init/plan passed; evidence is in `docs/evidence/phase6_terraform_init_plan_20260727.txt`.
- `make remote-compose-smoke`: installs/reuses user-level Compose on the VM, starts isolated Postgres/Redis/API/UI, reaches healthy status for all four, verifies API/UI HTTP health, and tears down in 74 seconds.
- `make remote-compose-load-smoke`: Dockerized API load test; 1,000 AVM and 1,000 lending requests at concurrency 10 pass with 0% errors, AVM p95 283.01 ms, and lending p95 33.93 ms.
- `make remote-cloud-smoke`: read-only GCP prerequisite diagnostic; latest run exits 0 in 10 seconds with the deployer account and required resource checks passing.
- Docker image builds: UI/API/monitor images build on the VM and pass plain-container smokes.
- Container dependency alignment: UI deps import and main `requirements.txt` audit passes; monitoring requirements audit remains blocked by `PYSEC-2024-231` in transitive `lightgbm 4.5.0`.

Full-stack and cloud targets are intentionally blocked until monitoring-profile/Dockerized load evidence and GCP Cloud Resource Manager/IAM/API access are fixed:

```bash
make remote-reproduce-full
make remote-up
make remote-cloud-smoke
```

## API Surface

Credit scoring endpoints from the original project remain available:

- `GET /health`
- `POST /predict`
- `GET /metrics`

Property lending endpoints added for this branch:

- `POST /v1/avm/predict`: listing-based value estimate, interval, confidence, factors, comparable support metadata
- `GET /v1/comparables`: non-GIS comparable fallback with explicit missing-distance status
- `POST /v1/lending/decision`: combines credit decision, requested loan amount, and AVM lower-bound value into LTV policy output

## Documentation Map

- [docs/summary.md](docs/summary.md): current evidence and blockers
- [docs/progress.md](docs/progress.md): phase-by-phase progress log
- [docs/reproduce.md](docs/reproduce.md): remote-only reproduction commands
- [docs/experiments.md](docs/experiments.md): every measured experiment and failed approach
- [reports/results.md](reports/results.md): benchmark and evaluation tables
- [docs/data_card.md](docs/data_card.md): dataset provenance, row counts, schema limitations, usage limits
- [docs/model_card_avm.md](docs/model_card_avm.md): AVM intended use, metrics, limitations, promotion status
- [docs/gcp_deployment.md](docs/gcp_deployment.md): deployment status and cloud blockers
- [docs/remote_environment.md](docs/remote_environment.md): VM resources, tools, Docker/GCP access status
- [docs/interview_story.md](docs/interview_story.md): concise portfolio narrative and quantified CV bullets

## Repository Layout

```text
api/                         FastAPI credit + property endpoints
src/                         Credit scoring pipeline and property intelligence modules
scripts/                     Model lifecycle, property experiments, benchmarks
scripts/remote/              Sentinel-guarded local-to-VM orchestration
ui/                          Streamlit credit/property demo workspace
monitoring/                  NannyML, Prometheus, Grafana, alerting assets
docs/                        Evidence-led project documentation
reports/                     Results, summaries, generated small artifacts
tests/                       VM-verified unit/integration/contract tests
```

## Safety Rules

- Never commit secrets, `.env`, raw data, generated datasets, databases, model binaries, Docker layers, or Terraform state.
- Do not report deployment URLs, costs, row counts, metrics, or test results unless they are measured and linked to evidence.
- Treat non-GIS comparables as administrative fallback only; do not describe them as spatial nearest neighbors.
- Treat current AVM and UI outputs as experimental portfolio evidence, not production lending advice.

## Deployed architecture

The demo uses Cloud Run for the authenticated API and ETL job, Cloud Scheduler for the daily `03:00 Asia/Bangkok` trigger, versioned Cloud Storage parquet snapshots, BigQuery property tables, immutable Artifact Registry images, and Secret Manager-backed MLflow configuration. Cloud SQL remains disabled.

## Live deployment

- API: `https://credit-mlops-demo-api-ocj3bsu27q-as.a.run.app`
- Services: `credit-mlops-demo-api`, `credit-mlops-demo-etl`, `credit-mlops-demo-etl-daily`
- Full redacted evidence: [`deployment_report.md`](deployment_report.md)

## Validation commands

Use `scripts/remote/run.sh` for Terraform, Cloud Run, Scheduler, and focused pytest validation. The exact measured commands are listed in `deployment_report.md`.

## Redeployment workflow

Build and push immutable API/job images on `lfm`, update Terraform digest variables, run a reviewed plan, apply only the affected Cloud Run resource, then repeat the API, ETL, and scheduler checks.

## Known limitations

The source dataset lacks coordinates, so GIS/radius comparables are unavailable. The deployed AVM is an experimental listing-based fallback and reports low confidence when comparable support is absent.
