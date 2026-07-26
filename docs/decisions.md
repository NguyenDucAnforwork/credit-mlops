# Decisions

Last updated: 2026-07-26 20:51:13 Asia/Bangkok

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
- Consequence: the next remediation attempt must update pins and lockfile in source, then verify compatibility on the VM before commit.

## ADR-0012: Apply Coordinated Dependency Remediation After VM Compatibility Checks

- Decision: update dependency pins and `uv.lock` for the broad resolver-compatible remediation set.
- Rationale: VM verification passed `uv sync --frozen --all-extras --dev`, Ruff, full pytest, coverage, property API smoke, and `pip-audit`.
- Consequence: vulnerability gate now passes with 0 known vulnerabilities; the FastAPI/Starlette TestClient deprecation warning remains a follow-up.
