# Remote Execution Helpers

These scripts keep the local repository as the source of truth while running heavy work on the GCP VM workspace `/home/ducan/credit-mlops-codex`.

```bash
scripts/remote/doctor.sh
scripts/remote/bootstrap.sh
scripts/remote/sync_to_vm.sh
scripts/remote/run.sh 'uv run pytest -q'
scripts/remote/reproduce_smoke.sh
scripts/remote/type_smoke.sh
scripts/remote/terraform_validate.sh
scripts/remote/compose_smoke.sh
scripts/remote/compose_load_smoke.sh
scripts/remote/cloud_smoke.sh
scripts/remote/fetch_artifacts.sh
scripts/remote/reset_to_pushed_branch.sh
```

Runtime data, model artifacts, databases, Terraform state, credentials, and caches stay on the VM. Only small redacted evidence under `reports/generated/`, `reports/figures/`, and `docs/evidence/` is copied back.

`reproduce_smoke.sh` is the non-Docker PR/portfolio smoke path. It performs a local secret/path scan, syncs source, runs syntax checks, Ruff lint, and focused contract tests on the VM, records runtime evidence, and explicitly marks Docker/GCP checks skipped when those external blockers remain.

`coverage_smoke.sh` runs the full Python suite under coverage on the VM, writes text and JSON coverage evidence, and fetches only the small report artifacts back to the local repository.

`vulnerability_smoke.sh` exports the resolved dependency set on the VM, runs `pip-audit`, records the audit exit status and reports, and fetches only the small audit evidence back locally.

`type_smoke.sh` runs pinned `mypy` on the new property intelligence modules, API code, and selected property scripts on the VM, records stdout/runtime evidence, and fetches only the small evidence files back locally.

`terraform_validate.sh` ensures a user-level Terraform binary exists on the VM, syncs source, runs `terraform fmt -check`, `init -backend=false`, and `validate`, then fetches only the provider lock and small validation evidence. It never runs `plan` or `apply`.

`compose_smoke.sh` ensures a user-level Docker Compose plugin exists on the VM, creates a VM-only empty/default `.env` if needed, uses an isolated Compose project name, builds and starts the core Postgres/Redis/API/UI services, checks HTTP health, records evidence, and tears down its own containers and volumes.

`compose_load_smoke.sh` uses the same isolated Compose pattern, then runs the async external HTTP benchmark against the Dockerized API service. It records endpoint latency/error evidence under `reports/generated/` and `docs/evidence/`, then tears down containers and volumes.

`cloud_smoke.sh` runs read-only `gcloud` checks from the VM for authentication, configured project, required API visibility, Artifact Registry, Cloud Run, and Scheduler. It records failure evidence and exits nonzero when cloud prerequisites are still blocked. It never enables APIs, creates resources, pushes images, or runs Terraform.
