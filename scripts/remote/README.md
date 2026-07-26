# Remote Execution Helpers

These scripts keep the local repository as the source of truth while running heavy work on the GCP VM workspace `/home/ducan/credit-mlops-codex`.

```bash
scripts/remote/doctor.sh
scripts/remote/bootstrap.sh
scripts/remote/sync_to_vm.sh
scripts/remote/run.sh 'uv run pytest -q'
scripts/remote/fetch_artifacts.sh
scripts/remote/reset_to_pushed_branch.sh
```

Runtime data, model artifacts, databases, Terraform state, credentials, and caches stay on the VM. Only small redacted evidence under `reports/generated/`, `reports/figures/`, and `docs/evidence/` is copied back.
