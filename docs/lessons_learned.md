# Lessons Learned

Last updated: 2026-07-26 14:05:41 Asia/Bangkok

- Verify GCP from the VM before planning Terraform or Cloud Run work. The current VM account is present, but OAuth scopes are insufficient for Cloud Resource Manager and Service Usage.
- Keep remote orchestration scripts allowlisted and sentinel-guarded so source synchronization cannot delete unrelated VM data.
- Do not assume a local Git remote alias works on the VM. The VM could not resolve `github-nguyenducan`, so bootstrap must support an rsync-backed workspace.
- Preserve remote-only safety sentinels during `rsync --delete`; `.codex_remote_workspace` must be excluded and re-touched after sync.
- Docker readiness requires both socket access and Compose availability. The VM has Docker client 29.1.3, but `ducan` cannot access `/var/run/docker.sock` and `docker compose` is unavailable.
- Keep fixture ETL evidence separate from full dataset claims. The current Phase 1 evidence proves incremental semantics, not full Hugging Face row counts or runtime.
- Add new production packages to `pyproject.toml`; after adding `src/property_intelligence`, standalone VM imports work without `PYTHONPATH`.
- Capture Hugging Face dataset revision metadata before downloading shards; row counts and checksums should always point back to a stable revision.
