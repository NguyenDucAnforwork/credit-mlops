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
| Terraform | GCP source scaffold validates on VM with Terraform 1.9.8 and Google provider 6.50.0; no plan/apply run |
| Docker packaging | `.dockerignore` excludes secrets/raw data/model directories; Dockerfiles no longer copy `.env`; Docker build still blocked |
| Tests/quality | 139 tests pass under coverage in 15.91 seconds; scoped coverage 81%; Ruff, warnings-enabled full suite, and mypy type smoke pass |
| Security audit | Project lock/main requirements audit clean; monitoring container requirements still blocked by NannyML `lightgbm` 4.5.0 vulnerability |

## Known Blockers

| Blocker | Current evidence |
|---------|------------------|
| GIS/PostGIS/H3 | Primary source has no coordinate columns, so spatial holdout, distance, radius, and H3 criteria are not claimed |
| Docker/Compose on VM | Docker daemon access works and image smokes pass; `docker compose` is unavailable |
| GCP deployment | VM account exists and Service Usage list works; Cloud Resource Manager project describe remains blocked |
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
- Docker image builds: UI/API/monitor images build on the VM and pass plain-container smokes; Docker Compose remains unavailable.
- Container dependency alignment: UI deps import and main `requirements.txt` audit passes; monitoring requirements audit remains blocked by `PYSEC-2024-231` in transitive `lightgbm 4.5.0`.

Compose and cloud targets are intentionally blocked until VM Docker Compose availability and GCP Cloud Resource Manager/IAM/API access are fixed:

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
