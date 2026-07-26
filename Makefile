REMOTE_RUN := scripts/remote/run.sh

.PHONY: remote-doctor remote-bootstrap remote-sync remote-verify remote-etl-smoke remote-train-smoke remote-reproduce-smoke remote-coverage-smoke remote-reproduce-full remote-up remote-cloud-smoke remote-fetch

remote-doctor:
	scripts/remote/doctor.sh

remote-bootstrap:
	scripts/remote/bootstrap.sh

remote-sync:
	scripts/remote/sync_to_vm.sh

remote-verify: remote-sync
	$(REMOTE_RUN) 'uv run pytest -q'

remote-etl-smoke: remote-sync
	$(REMOTE_RUN) 'uv run python src/data_prep.py'

remote-train-smoke: remote-sync
	$(REMOTE_RUN) 'uv run python src/pipeline.py --skip-data-prep --skip-feature-fit'

remote-reproduce-smoke:
	scripts/remote/reproduce_smoke.sh

remote-coverage-smoke:
	scripts/remote/coverage_smoke.sh

remote-reproduce-full: remote-sync
	$(REMOTE_RUN) 'uv run pytest -q && docker compose build && docker compose up -d'

remote-up: remote-sync
	$(REMOTE_RUN) 'docker compose up -d --build'

remote-cloud-smoke:
	$(REMOTE_RUN) 'gcloud services list --project driven-reef-452414-b5 --limit=5 >/dev/null'

remote-fetch:
	scripts/remote/fetch_artifacts.sh
