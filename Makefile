REMOTE_RUN := scripts/remote/run.sh

.PHONY: remote-doctor remote-bootstrap remote-sync remote-verify remote-etl-smoke remote-train-smoke remote-reproduce-smoke remote-coverage-smoke remote-vulnerability-smoke remote-type-smoke remote-terraform-validate remote-reproduce-full remote-up remote-cloud-smoke remote-fetch

remote-doctor:
	bash scripts/remote/doctor.sh

remote-bootstrap:
	bash scripts/remote/bootstrap.sh

remote-sync:
	bash scripts/remote/sync_to_vm.sh

remote-verify: remote-sync
	$(REMOTE_RUN) 'uv run pytest -q'

remote-etl-smoke: remote-sync
	$(REMOTE_RUN) 'uv run python src/data_prep.py'

remote-train-smoke: remote-sync
	$(REMOTE_RUN) 'uv run python src/pipeline.py --skip-data-prep --skip-feature-fit'

remote-reproduce-smoke:
	bash scripts/remote/reproduce_smoke.sh

remote-coverage-smoke:
	bash scripts/remote/coverage_smoke.sh

remote-vulnerability-smoke:
	bash scripts/remote/vulnerability_smoke.sh

remote-type-smoke:
	bash scripts/remote/type_smoke.sh

remote-terraform-validate:
	bash scripts/remote/terraform_validate.sh

remote-reproduce-full: remote-sync
	$(REMOTE_RUN) 'uv run pytest -q && docker compose build && docker compose up -d'

remote-up: remote-sync
	$(REMOTE_RUN) 'docker compose up -d --build'

remote-cloud-smoke:
	$(REMOTE_RUN) 'gcloud services list --project driven-reef-452414-b5 --limit=5 >/dev/null'

remote-fetch:
	bash scripts/remote/fetch_artifacts.sh
