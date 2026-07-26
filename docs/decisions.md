# Decisions

Last updated: 2026-07-26 15:05:30 Asia/Bangkok

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
- Rationale: both interval approaches hit the empirical coverage band, but median width remains above 80% of point estimate versus the <=50% target.
- Consequence: APIs and model cards may expose these as experimental evidence only; the next AVM uncertainty work should use quantile or conformalized quantile models before promotion.
