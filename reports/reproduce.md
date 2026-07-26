# Remote Reproduction Report

Last updated: 2026-07-26 23:06:44 Asia/Bangkok

This project is reproduced from the local repository by executing runtime work on VM `lfm` in `/home/ducan/credit-mlops-codex`. Do not install dependencies, run tests, train models, build Docker images, run databases, execute Terraform, or deploy GCP resources locally.

## Current Remote Targets

| Target | Status | Evidence |
|--------|--------|----------|
| `make remote-reproduce-smoke` | pass; 61 focused tests in 3.24s, end-to-end 5s, Ruff 0 errors | `docs/evidence/remote_reproduce_smoke_20260726.txt` |
| `make remote-coverage-smoke` | pass; 139 tests in 15.91s, 81% scoped coverage, end-to-end 19s | `docs/evidence/phase7_coverage_report_20260726.txt` |
| `make remote-vulnerability-smoke` | pass; `pip-audit` found 0 known vulnerabilities after dependency and TestClient warning remediation | `docs/evidence/phase7_pip_audit_report_20260726.txt` |
| `make remote-type-smoke` | pass; mypy found 0 issues in 19 source files, end-to-end 1s | `docs/evidence/phase7_type_smoke_stdout_20260726.txt` |
| `make remote-terraform-validate` | pass; Terraform fmt/init/validate, end-to-end 2s, no plan/apply | `docs/evidence/phase6_terraform_validate_20260726.txt` |
| Docker context guard | pass; source excludes `.env`/generated artifacts | `docs/evidence/phase6_docker_context_guard_20260726.txt` |
| Docker image builds | pass; UI/API/monitor images built on VM | `docs/evidence/phase6_docker_images_20260726.txt` |
| Docker plain-container smokes | pass; API/UI health and monitor import checks passed | `docs/evidence/phase6_docker_api_smoke_20260726.txt` |
| `make remote-compose-smoke` | pass; isolated Postgres/Redis/API/UI healthy and HTTP smokes passed in 74s | `docs/evidence/phase6_compose_smoke_20260726.txt` |
| Container dependency alignment | partial; main requirements audit passes, monitoring requirements blocked by NannyML/LightGBM | `docs/evidence/phase6_container_dependency_alignment_20260726.txt` |
| `make remote-reproduce-full` | blocked | monitoring-profile/cloud prerequisites |
| `make remote-up` | partial | core Compose smoke passes; full long-running stack not left up |
| `make remote-cloud-smoke` | blocked; diagnostic exits 1 in 10s | `docs/evidence/phase6_gcp_readonly_smoke_20260726.txt` |

## Exact Commands

```bash
make remote-doctor
make remote-sync
make remote-reproduce-smoke
make remote-coverage-smoke
make remote-vulnerability-smoke
make remote-type-smoke
make remote-terraform-validate
```

The smoke and quality targets perform local changed-file path and secret-pattern scans, sync the source tree to the VM, run checks remotely, and fetch only small evidence artifacts back to `docs/evidence/` and `reports/generated/`.

## Full Evidence Trail

Use the canonical docs for current reproduction details:

- `docs/reproduce.md`
- `docs/progress.md`
- `docs/remote_environment.md`
- `docs/experiments.md`
- `reports/results.md`

The older local-first credit-scoring reproduction path is not the active contract for this branch.
