# Lessons Learned

Last updated: 2026-07-26 15:33:55 Asia/Bangkok

- Verify GCP from the VM before planning Terraform or Cloud Run work. The current VM account is present, but OAuth scopes are insufficient for Cloud Resource Manager and Service Usage.
- Keep remote orchestration scripts allowlisted and sentinel-guarded so source synchronization cannot delete unrelated VM data.
- Do not assume a local Git remote alias works on the VM. The VM could not resolve `github-nguyenducan`, so bootstrap must support an rsync-backed workspace.
- Preserve remote-only safety sentinels during `rsync --delete`; `.codex_remote_workspace` must be excluded and re-touched after sync.
- Docker readiness requires both socket access and Compose availability. The VM has Docker client 29.1.3, but `ducan` cannot access `/var/run/docker.sock` and `docker compose` is unavailable.
- Keep fixture ETL evidence separate from full dataset claims. The current Phase 1 evidence proves incremental semantics, not full Hugging Face row counts or runtime.
- Add new production packages to `pyproject.toml`; after adding `src/property_intelligence`, standalone VM imports work without `PYTHONPATH`.
- Capture Hugging Face dataset revision metadata before downloading shards; row counts and checksums should always point back to a stable revision.
- Use Parquet footer range reads to verify row counts cheaply. Keep the evidence label precise: footer-derived row counts and HF ETags are not full-content SHA256 checksums.
- For raw snapshot reruns, reuse existing remote files only after recomputing local SHA256 and size. This keeps reruns cheap without trusting stale manifests blindly.
- The real HF schema has no latitude/longitude columns. GIS features must come from a legitimate enrichment source; do not infer exact coordinates from text fields.
- Data validation can pass core ETL gates while still surfacing a blocker. `pass_with_blockers` is useful when non-GIS work can continue but GIS work cannot.
- District and property-type medians are a strong listing AVM baseline: December test MdAPE improved from 47.97% global median to 22.85% with district+property type.
- HGB on log(price/m2) improved relative error and RMSLE but not MAE. Future AVM work should include tail/outlier handling and interval calibration, not just average relative error.
- Global validation-residual intervals can hit coverage but be too wide. The first 80% interval had 79.61% coverage but 83.79% median width ratio, so interval usefulness needs cohort or quantile modeling.
- Province/property-type residual cohorts are not enough by themselves. They improved median interval width only to 82.32% and increased p90 width to 107.48%, so the next uncertainty attempt should optimize quantiles directly rather than only regrouping residuals.
- Direct q10/q90 HGB quantiles improved median interval width to 76.99% and created a 14.33% high-confidence segment, but still failed the <=50% width target. Quantile objectives help, but the listing feature set still lacks enough signal for narrow 80% AVM intervals.
- Non-GIS comparables can be fast and leakage-safe for support metadata, but the evidence must remain separate from PostGIS criteria. The 1,000-query fallback p95 was 14.88 ms, but distance and radius are still unavailable.
- API smoke must distinguish cold initialization from warm request latency. The first comparable request spent 2.62 seconds building the index, while the following AVM request was 13.13 ms after reuse.
- Promotion gates should reject on missing evidence, not only bad metrics. The current AVM improves temporal MdAPE but must not become champion without spatial holdout, cohort regression, width, and warm API evidence.
