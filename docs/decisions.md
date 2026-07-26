# Decisions

Last updated: 2026-07-26 21:52:20 Asia/Bangkok

## ADR-0001: Local Source of Truth, VM Runtime Executor

- Decision: keep all source edits, docs, commits, and pushes local; run dependencies, tests, Docker, data, training, Terraform, and `gcloud` on `lfm`.
- Rationale: the local machine is constrained, while the VM has appropriate CPU, memory, disk, Docker, and cloud network context.
- Consequence: every verification command must be preceded by `scripts/remote/sync_to_vm.sh` or by resetting the VM clone to the pushed feature branch.

## ADR-0002: Sentinel-Guarded Remote Workspace

- Decision: use only `/home/ducan/credit-mlops-codex` with `.codex_remote_workspace`.
- Rationale: prevents accidental modification or deletion of unrelated VM projects.
- Consequence: sync/reset scripts refuse unsafe paths.

## ADR-0003: Do Not Fabricate Coordinates

- Decision: preserve `coordinate_status=missing_source_columns` for the HF dataset and block GIS/PostGIS/H3 work until a legitimate coordinate enrichment source is integrated.
- Rationale: the actual Parquet schema contains 19 columns and no `latitude`/`longitude`, contradicting the expected coordinate availability in the contract. Exact coordinates cannot be derived safely from listing text, district, street, or project names.
- Consequence: non-GIS tabular AVM baselines can proceed, but GIS features, PostGIS indexed comparable search, and H3 spatial holdout require a future enrichment step with measured provenance.

## ADR-0004: Do Not Promote Residual Interval Confidence Policy Yet

- Decision: keep global and province/property-type residual interval experiments as measured baselines, but do not treat the confidence policy as production-ready.
- Rationale: residual and direct quantile approaches hit the empirical coverage band, but the best median width measured so far is 76.99% of point estimate versus the <=50% target.
- Consequence: APIs and model cards may expose these as experimental evidence only; the next AVM uncertainty work needs richer support/comparable features, legitimate spatial enrichment, or stronger quantile diagnostics before promotion.

## ADR-0005: Use Non-GIS Comparables Only As Fallback

- Decision: implement district/property-type comparable fallback for support metadata and API scaffolding, with `distance_status=not_available_missing_coordinates`.
- Rationale: the real source schema lacks coordinates, so radius, distance, H3, and PostGIS evidence cannot be produced truthfully yet.
- Consequence: fallback p95 latency can be reported separately, but Phase 2 PostGIS comparable criteria remain incomplete until legitimate coordinates and PostGIS are available.

## ADR-0006: Property API Scaffold Uses Experimental Fallback

- Decision: expose `/v1/avm/predict`, `/v1/comparables`, and `/v1/lending/decision` using the non-GIS comparable fallback and explicit experimental warnings.
- Rationale: API consumers and tests need stable response contracts before Docker/GCP/service benchmarking is unblocked.
- Consequence: endpoint shape and lending policy boundaries are testable now, but API p95 done criteria require warm service load tests and a promoted AVM artifact later.

## ADR-0007: AVM Promotion Starts As Dry-Run Gate

- Decision: evaluate AVM promotion with an auditable dry-run gate and no MLflow alias mutation until all promotion evidence exists and passes.
- Rationale: the current candidate passes temporal improvement and coverage but fails interval width and lacks spatial/cohort/API load evidence.
- Consequence: model lifecycle work can progress with explicit rejection reasons while protecting any future `property_avm@champion` alias from premature promotion.

## ADR-0008: Start Monitoring With Deterministic Drift Checks

- Decision: implement deterministic property drift checks for area, price/m2, interval width, confidence mix, and missingness before wiring external monitoring services.
- Rationale: synthetic drift evidence must be reproducible and small enough to commit while Docker/monitoring services remain blocked.
- Consequence: alert logic is testable now; dashboards and production delayed-label pipelines remain future work.

## ADR-0009: Keep AVM Model Artifact Remote-Only

- Decision: package the HGB point + q10/q90 quantile AVM as a joblib artifact on the VM under `artifacts/models/`, expose it through `AVM_ARTIFACT_PATH`, and commit only JSON/stdout evidence.
- Rationale: the contract forbids committing model binaries locally, while artifact size/load/reproducibility evidence is required for the AVM done criteria.
- Consequence: local source remains lightweight; API can use the artifact when configured and otherwise degrades to the non-GIS comparable fallback. Promotion remains blocked by interval width, spatial holdout, and cloud/container evidence.

## ADR-0010: Treat Vulnerability Remediation as a Separate Compatibility Pass

- Decision: keep the `pip-audit` failure as evidence and do not blind-upgrade vulnerable dependencies in the audit commit.
- Rationale: the scan found 59 vulnerabilities across 11 packages, including transitive framework dependencies whose fixed versions may require coordinated FastAPI/Streamlit/MLflow compatibility checks.
- Consequence: this was resolved by a later compatibility-tested dependency remediation; keep the failed audit as historical evidence.

## ADR-0011: Do Not Apply Broad Dependency Upgrade From Resolver Probe Alone

- Decision: keep the successful broad dependency resolver dry-run as planning evidence only.
- Rationale: the narrow fix is blocked by MLflow's `cryptography<47` constraint, and the resolver-level solution upgrades MLflow, FastAPI, Starlette, Streamlit, Pillow, NLTK, and many transitives.
- Consequence: the later compatibility run updated pins and lockfile in source, then verified sync, Ruff, full tests, coverage, API smoke, and audit on the VM before commit.

## ADR-0012: Apply Coordinated Dependency Remediation After VM Compatibility Checks

- Decision: update dependency pins and `uv.lock` for the broad resolver-compatible remediation set.
- Rationale: VM verification passed `uv sync --frozen --all-extras --dev`, Ruff, full pytest, coverage, property API smoke, and `pip-audit`.
- Consequence: vulnerability gate now passes with 0 known vulnerabilities; the FastAPI/Starlette TestClient deprecation warning was resolved in ADR-0013.

## ADR-0013: Add httpx2 For Starlette TestClient Compatibility

- Decision: add `httpx2==2.9.1` to dev dependencies and lock the transitive `httpcore2` and `truststore` packages.
- Rationale: Starlette 1.3.1 resolves its TestClient compatibility path through `httpx2`; adding it removes the deprecation warning without changing runtime API dependencies.
- Consequence: Ruff and the warnings-enabled full suite pass on the VM with 139 tests in 11.20 seconds, coverage remains 81%, and `pip-audit` still reports 0 known vulnerabilities.

## ADR-0014: Scope Type Checking To New Property/API Surface First

- Decision: add `make remote-type-smoke` with pinned `mypy==1.18.2` for `src/property_intelligence`, `api`, and selected property scripts.
- Rationale: the contract requires type-check evidence for new production modules, while the legacy project has no existing full-repository type-check configuration.
- Consequence: the scoped VM type smoke passes with 0 issues in 19 source files and can be broadened later without blocking the current non-Docker/non-cloud evidence path.

## ADR-0015: Validate Terraform Source Without Cloud Mutation

- Decision: add `infra/terraform` and `make remote-terraform-validate`, using backend-disabled init and validation only.
- Rationale: GCP IAM/OAuth and Docker image prerequisites are blocked, but source architecture can still be checked safely without creating or changing resources.
- Consequence: Terraform source now validates on the VM; deployment remains blocked until project scopes/IAM, Docker build/push, and cost-sensitive apply approval are available.

## ADR-0016: Keep Secrets Out Of Docker Images

- Decision: add `.dockerignore` and remove `COPY .env` from Dockerfiles.
- Rationale: environment files and generated data/model artifacts must not be baked into images by default; runtime configuration should come from Compose env files, Cloud Run environment, or Secret Manager.
- Consequence: Docker source guard passes; later daemon access allowed image builds and plain-container smokes, but Compose service-stack validation remains blocked.

## ADR-0017: Do Not Force Incompatible NannyML LightGBM Fix

- Decision: align main/UI/container pins where compatible, but do not add `lightgbm==4.6.0` to `requirements-monitor.txt`.
- Rationale: `pip-audit` reports `PYSEC-2024-231` for transitive `lightgbm 4.5.0`, but pinning the fixed version conflicts with available NannyML 0.13.x releases.
- Consequence: main requirements audit is clean; monitoring requirements audit remains a documented blocker until NannyML offers a compatible dependency path or the monitor image is redesigned.

## ADR-0018: Use Plain Docker Smokes Until Compose Is Available

- Decision: build UI/API/monitor images and smoke them with plain `docker run` on the VM, but keep `remote-up` and service-stack claims blocked until Docker Compose exists.
- Rationale: Docker daemon access was restored and individual image validation was valuable while Compose was not yet available.
- Consequence: superseded by ADR-0019 for core Compose smoke; image push, monitoring-profile service integration, Dockerized load tests, and Cloud Run deployment remain incomplete.

## ADR-0019: Run Compose Smoke In An Isolated VM Project

- Decision: add `make remote-compose-smoke` with a user-level Compose plugin, VM-only `.env` default, isolated project name, core Postgres/Redis/API/UI health checks, and teardown.
- Rationale: Compose can now be verified without sudo, without syncing local secrets, and without leaving persistent database volumes from a smoke run.
- Consequence: core Compose service wiring is measured; monitoring-profile jobs, Dockerized load tests, registry push, and Cloud Run deployment remain separate evidence requirements.

## ADR-0020: Make Cloud Smoke Read-Only And Failure-Sensitive

- Decision: replace the one-line `remote-cloud-smoke` target with `scripts/remote/cloud_smoke.sh`, a read-only prerequisite diagnostic that records command-level exit codes and returns nonzero while deployment APIs/IAM are blocked.
- Rationale: `gcloud services list` can succeed even when Cloud Resource Manager, Artifact Registry, Cloud Run, and Scheduler are not usable.
- Consequence: cloud readiness is no longer overstated; Terraform plan/apply, image push, API enablement, and deployment stay blocked until the diagnostic passes and cost-sensitive actions are approved.
