# Decisions

Last updated: 2026-07-26 15:33:55 Asia/Bangkok

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
