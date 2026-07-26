# AGENTS.md

This repository is operated with the local machine as the control plane and source of truth. Heavy/runtime work must execute on SSH host `lfm` in `/home/ducan/credit-mlops-codex`.

- Use branch `feat/onemount-property-intelligence`.
- Do not run dependency installs, tests, training, Docker, databases, Terraform, or `gcloud` locally.
- Use `scripts/remote/sync_to_vm.sh` before remote verification.
- Use `scripts/remote/run.sh '<command>'` for VM commands.
- Keep raw data, generated datasets, model binaries, Docker volumes, Terraform state, and secrets out of Git.
- Update the required `docs/*.md` and `reports/results.md` after each measured phase, experiment, deployment attempt, or blocker.
