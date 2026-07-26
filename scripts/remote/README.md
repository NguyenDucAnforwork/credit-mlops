# Remote Execution Helpers

These scripts keep the local repository as the source of truth while running heavy work on the GCP VM workspace `/home/ducan/credit-mlops-codex`.

```bash
scripts/remote/doctor.sh
scripts/remote/bootstrap.sh
scripts/remote/sync_to_vm.sh
scripts/remote/run.sh 'uv run pytest -q'
scripts/remote/reproduce_smoke.sh
scripts/remote/type_smoke.sh
scripts/remote/fetch_artifacts.sh
scripts/remote/reset_to_pushed_branch.sh
```

Runtime data, model artifacts, databases, Terraform state, credentials, and caches stay on the VM. Only small redacted evidence under `reports/generated/`, `reports/figures/`, and `docs/evidence/` is copied back.

`reproduce_smoke.sh` is the non-Docker PR/portfolio smoke path. It performs a local secret/path scan, syncs source, runs syntax checks, Ruff lint, and focused contract tests on the VM, records runtime evidence, and explicitly marks Docker/GCP checks skipped when those external blockers remain.

`coverage_smoke.sh` runs the full Python suite under coverage on the VM, writes text and JSON coverage evidence, and fetches only the small report artifacts back to the local repository.

`vulnerability_smoke.sh` exports the resolved dependency set on the VM, runs `pip-audit`, records the audit exit status and reports, and fetches only the small audit evidence back locally.

`type_smoke.sh` runs pinned `mypy` on the new property intelligence modules, API code, and selected property scripts on the VM, records stdout/runtime evidence, and fetches only the small evidence files back locally.
