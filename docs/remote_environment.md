# Remote Environment

Last updated: 2026-07-27 00:05:00 Asia/Bangkok

## SSH

- Host: `lfm`
- Required workspace: `/home/ducan/credit-mlops-codex`
- Preflight command: `ssh -o BatchMode=yes -o ConnectTimeout=10 lfm 'printf "SSH_OK\n"; whoami; hostname; pwd'`
- Result: `SSH_OK`, user `ducan`, hostname `lfm`, home `/home/ducan`
- Current status: SSH is working again; `make remote-coverage-smoke` and `make remote-vulnerability-smoke` both executed on `lfm` after the earlier transient auth issue.

## VM Resources

- OS: Ubuntu 24.04.4 LTS
- CPU: 4 vCPU, AMD EPYC 7B12, x86_64
- Memory: 15 GiB total, 14 GiB available during preflight
- Disk `/`: 145 GiB total, 80 GiB used, 66 GiB available
- GPU: not present (`nvidia-smi` not found)

## Tools

- `git`: `/usr/bin/git`
- `docker`: `/usr/bin/docker`
- `gcloud`: `/snap/bin/gcloud`
- `python3`: Python 3.12.3
- `terraform`: installed later as user-level Terraform 1.9.8 under `/home/ducan/.local/bin/terraform`
- `uv`: installed later at `/home/ducan/.local/bin/uv`
- Docker client: 29.1.3
- Docker server access: works for user `ducan` after group refresh
- Docker Compose: user-level plugin `v5.3.1` under `$HOME/.docker/cli-plugins`
- Latest measured Python suite: 139 tests passed in 15.91 seconds under `make remote-coverage-smoke`; latest warnings-enabled non-coverage suite was 139 passed in 11.20 seconds with Ruff passing and no TestClient warning summary.
- Latest remote smoke reproduction: `make remote-reproduce-smoke` completed in 5 seconds with Ruff passing and 61 focused tests passing in 3.24 seconds.
- Latest scoped coverage measurement: 81% total coverage for `api/*`, `src/*`, and `scripts/property_*.py`; wrapper runtime 19 seconds; evidence files `docs/evidence/phase7_coverage_report_20260726.txt`, `docs/evidence/phase7_coverage_stdout_20260726.txt`, and `reports/generated/phase7_coverage_20260726.json`.
- Latest vulnerability audit: `make remote-vulnerability-smoke` completed in 41 seconds with `pip_audit_exit=0` and 0 known vulnerabilities after dependency and TestClient warning remediation.
- Latest type-check smoke: `make remote-type-smoke` completed in 1 second with `mypy==1.18.2`; 19 source files checked, 0 issues.
- Latest Terraform validation: `make remote-terraform-validate` completed in 2 seconds with Terraform 1.9.8 and Google provider 6.50.0; backend disabled, `terraform_validate_exit=0`, no plan/apply.
- Latest Docker context guard: source check completed in 0 seconds and confirmed `.env` is not copied by Dockerfiles.
- Latest container dependency alignment: UI dependency import passed; main requirements audit exit 0; monitoring requirements audit exit 1 due transitive `lightgbm 4.5.0` vulnerability through NannyML.
- Latest Docker daemon recheck: `ducan` is in group `docker`; Docker client/server 29.1.3 respond.
- Latest Docker image builds: UI `94df2d30ecb0` 837MB in 55s, API `b4e4dcd3afd7` 3.01GB in 286s, monitor `ab3038d25eeb` 3.64GB in 298s.
- Latest plain container smokes: API `/health` returned `status=ok` with fallback local model and Docker health `healthy`; UI Streamlit health returned `ok` and Docker health `healthy`; monitoring image import check passed.
- Latest Compose smoke: `make remote-compose-smoke` completed in 74 seconds; Postgres, Redis, API, and UI reached Docker health `healthy`; API/UI HTTP health passed; isolated containers, network, and Postgres volume were removed.
- Latest Dockerized API load: `make remote-compose-load-smoke` completed in 78 seconds; 1,000 AVM and 1,000 lending requests at concurrency 10 returned status 200 with 0% errors; AVM p95 283.01 ms; lending p95 33.93 ms.
- Latest cloud smoke: `make remote-cloud-smoke` completed in 10 seconds with `gcp_readonly_smoke_exit=0`; deployer authentication, project describe, Artifact Registry, Cloud Run, and Scheduler read-only checks passed.
- Latest Terraform plan: remote `terraform init` and `terraform plan` passed in 3 seconds with Terraform 1.9.8 and Google provider 6.50.0; plan is 30 to add, 0 to change, 0 to destroy. No apply ran.
- Latest targeted cloud phase: `google_artifact_registry_repository.images` was applied alone with 1 added/0 changed/0 destroyed; both immutable images pushed; final Terraform plan is 29 to add/0 change/0 destroy with digest references.
- Latest measured local VM HTTP benchmark: AVM p95 140.84 ms and lending p95 24.21 ms with 0% errors at 1,000 requests/concurrency 10.
- Latest startup warm-up benchmark: property index startup 4.85 seconds, first comparable request after startup 10.99 ms.
- Latest AVM artifact evidence: 2.37 MB remote-only joblib, load 87.13 ms, single prediction 21.32 ms, same-seed MdAPE delta 0.0 percentage points.
- Latest artifact-backed local VM HTTP benchmark: AVM p95 136.63 ms and lending p95 15.53 ms with 0% errors at 1,000 requests/concurrency 10.

## Docker Access

- User/group: `uid=1002(ducan) gid=1003(ducan)`
- Groups: `ducan adm dialout cdrom floppy audio dip video plugdev lxd netdev ubuntu google-sudoers docker`
- Socket: `/var/run/docker.sock` is owned by `root:docker` with mode `srw-rw----`
- Result: Docker daemon and user-level Compose access work; individual image, plain-container, and core Compose stack evidence is captured.
- Remaining blocker: monitoring-profile Compose, Dockerized load tests, image push, and cloud deployment are not measured yet.

## GCP Access

- Active account: `credit-mlops-deployer@driven-reef-452414-b5.iam.gserviceaccount.com`
- Configured project: `driven-reef-452414-b5`
- Project describe: passes for project `driven-reef-452414-b5`
- Service Usage list: passes for required APIs
- Artifact Registry list: passes for `asia-southeast1`
- Cloud Run services list: passes
- Scheduler jobs list: passes

Remaining cloud blockers: push deployable images instead of Terraform's placeholder tags, confirm apply-time IAM and cost approval, populate the MLflow secret through an approved secret flow, then apply and smoke Cloud Run. No long-lived service account key should be downloaded as a workaround.
