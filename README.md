# Credit Scoring MLOps

End-to-end credit default prediction system with MLflow experiment tracking, FastAPI inference service, champion/challenger deployment scripts, and a full observability stack including NannyML model monitoring.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Training Pipeline                               │
│   raw CSV → data_prep → feature_fit → train (LR/XGB/Scorecard)          │
│                            ↓ MLflow (DagsHub)                            │
│               champion / challenger / scorecard aliases                  │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │ model artifacts
┌──────────────────────────▼───────────────────────────────────────────────┐
│                      Inference Stack (Docker)                            │
│                                                                          │
│  ┌──────────┐   ┌──────────────────────────────┐   ┌─────────────────┐  │
│  │Streamlit │   │          FastAPI :8000        │   │    Postgres     │  │
│  │  UI:8501 │──▶│  /predict  /health  /metrics  │──▶│  predictions   │  │
│  └──────────┘   │  model_loader (bg thread)     │   │  deploy_events │  │
│                 └──────────────┬─────────────────┘   └─────────────────┘  │
│                                │ Prometheus metrics                       │
│  ┌─────────────────────────────▼──────────────────────────────────────┐  │
│  │                     Observability Layer                            │  │
│  │                                                                    │  │
│  │  Prometheus:9090 ──scrapes──▶ /metrics                            │  │
│  │  Pushgateway:9091 ◀── push ── NannyML monitor (batch, profile)    │  │
│  │  Alertmanager:9093 ◀─ rules ─ alert_rules.yml (5 rules)          │  │
│  │  Grafana:3000 ─────────────▶ 3-row dashboard                      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │               Champion/Challenger Deployment                     │    │
│  │   scripts/promote_model.py  ──▶  MLflow registry + audit log    │    │
│  │   scripts/rollback_model.py ──▶  MLflow registry + audit log    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

## Models

| Alias | Model | AUC | Gini | Notes |
|-------|-------|-----|------|-------|
| `champion` | XGBoost | 0.8223 | 0.6446 | Default serving model |
| `challenger` | LR + SMOTE | 0.8229 | 0.6459 | Baseline comparison |
| `scorecard` | WOE + LR | 0.8102 | 0.6205 | Full interpretability |

Switch serving model via env var — no code change needed:

```bash
MLFLOW_MODEL_ALIAS=scorecard docker compose up -d --build api
```

---

## Quick Start (Docker)

**Prerequisites:** Docker Desktop with WSL2 (Windows) or Docker Engine (Linux/Mac).

### 1. Clone and configure

```bash
git clone https://github.com/NguyenDucAnforwork/credit-mlops.git
cd credit-mlops
```

Create `.env` in the project root:

```env
MLFLOW_TRACKING_URI=https://dagshub.com/NguyenDucAnforwork/credit-mlops.mlflow
MLFLOW_TRACKING_USERNAME=NguyenDucAnforwork
MLFLOW_TRACKING_PASSWORD=<your_dagshub_token>

POSTGRES_USER=credituser
POSTGRES_PASSWORD=creditpass
POSTGRES_DB=creditdb
DATABASE_URL=postgresql://credituser:creditpass@postgres:5432/creditdb
REDIS_URL=redis://redis:6379/0
```

> **Note:** Use `MLFLOW_TRACKING_PASSWORD`, **not** `DAGSHUB_TOKEN` — MLflow reads this specific key for basic auth.

### 2. Start the stack

```bash
docker compose up -d --build
```

Wait ~30 seconds for the API to download the champion model from DagsHub.

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health
# → {"status":"ok","model_version":"credit_score_model@champion v3","uptime_s":...}

# Streamlit UI (non-technical user interface)
open http://localhost:8501

# Grafana dashboard
open http://localhost:3000   # admin / admin
```

The Streamlit UI now supports two scoring paths:
- `Mode A` — load a real row from `data/processed/test_data.csv` and send all non-null features for reproducible demo scenarios
- `Mode B` — manually enter the original 14 headline features for quick partial-input scoring

In Docker, `ui` reads Mode-A rows through the read-only `./data:/data:ro` mount and `TEST_DATA_PATH=/data/processed/test_data.csv`.

---

## Local Development Setup

### Requirements

- Python **3.12.x** (3.13 has no numpy 1.26.4 wheel)
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)

```bash
# Install uv (once)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv + install all deps from lockfile in seconds
uv sync

# Activate (optional — uv run works without it)
source .venv/bin/activate
```

> **Why uv?** Resolves 161 packages in 52 ms and installs them in ~1 s (vs pip's minutes). The `uv.lock` file pins every transitive dependency for bit-for-bit reproducibility. Docker uses the same lockfile via `uv sync --frozen`.

### Run the training pipeline

```bash
# Full run (first time): data prep + feature fit + train all 3 models + register
python src/pipeline.py

# Subsequent runs (data/features unchanged):
python src/pipeline.py --skip-data-prep --skip-feature-fit
```

Pipeline steps:
1. **data_prep** — SHA256-hashes raw CSV, stratified 80/20 split, saves `data/processed/`
2. **feature_fit** — KNNImputer(k=20) → Winsorizer(5-95%) → GroupPCA → RFE(22 features)
3. **train** — logs 3 MLflow runs to DagsHub (LR, XGBoost, Scorecard WOE-LR)
4. **register** — sets aliases: LR→challenger, XGB→champion, Scorecard→scorecard

### Run tests

```bash
uv run pytest tests/ -v
# 76 tests: unit, integration, chaos, deployment
```

### Run the API locally

```bash
# Start dependencies
docker compose up -d postgres redis

# Run API with auto-reload (code changes in api/ take effect immediately)
cd api && uv run uvicorn main:app --reload --port 8000
```

### Hot-reload in Docker (bind mounts)

The `docker-compose.yml` mounts `./api` and `./src` into the running container.
Edit any file in `api/` or `src/` locally and uvicorn's `--reload` picks it up — no
rebuild needed:

```bash
docker compose up -d  # start once
# ... edit api/main.py or src/scorecard.py ...
# changes are live within ~1 s, no docker compose build required
```

> `--reload` is enabled in the container CMD. To disable in production, remove it or
> override `CMD` in `docker-compose.yml`.

---

## API Reference

### `GET /health`

```json
{"status": "ok", "model_version": "credit_score_model@champion v3", "uptime_s": 120.5}
```

### `POST /predict`

Send raw credit bureau features (all optional, use `null` for missing):

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d @examples/sample_request.json
```

Response (XGBoost champion):
```json
{
  "default_probability": 0.23,
  "credit_score": 714,
  "risk_band": "Good",
  "decision": "approve",
  "model_version": "credit_score_model@champion v3",
  "model_alias": "champion",
  "trace_id": "a3f1c2d4-8b7e-4e2a-9f0d-1c2b3a4e5f60",
  "latency_ms": 45.2,
  "scorecard_score": null,
  "scorecard_breakdown": null
}
```

Response (scorecard model — includes interpretability):
```json
{
  "default_probability": 0.19,
  "credit_score": 726,
  "risk_band": "Good",
  "decision": "approve",
  "model_version": "credit_score_model@scorecard v5",
  "model_alias": "scorecard",
  "trace_id": "b7d2e1f3-9c8a-4f3b-a1e2-2d3c4b5a6e71",
  "latency_ms": 38.1,
  "scorecard_score": 623.4,
  "scorecard_breakdown": [
    {"feature": "NUM_NEW_LOAN_TAKEN_PCA_1", "raw_value": -0.82, "bin": "(-inf, -0.5]", "woe": 0.71, "score_contribution": 52.3, "iv": 1.40},
    {"feature": "ENQUIRIES_PCA_1",          "raw_value":  0.31, "bin": "(0.1, 0.8]",   "woe": -0.24, "score_contribution": -18.1, "iv": 0.44},
    ...
  ]
}
```

**New response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `model_alias` | `str` | The MLflow alias that served this request (e.g. `"champion"`) |
| `trace_id` | `str` | UUID4 per-request identifier for distributed tracing and log correlation |

### Decision thresholds

| default_probability | decision |
|---------------------|----------|
| < 0.45 | approve |
| 0.45 – 0.69 | manual_review |
| >= 0.70 | reject |

### `GET /metrics`

Prometheus metrics in text format. Scraped automatically by Prometheus at `:9090`.

**Model reload metrics** (emitted by `model_loader.py`):

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `model_reload_success_total` | counter | `alias`, `source` | Successful background reloads |
| `model_reload_failure_total` | counter | `alias`, `error_type` | Failed background reloads |
| `model_version_info` | gauge | `alias`, `version`, `source` | Set to 1 for the currently active version |
| `feature_missing_rate` | histogram | — | Fraction of null features per request (0–1) |

---

## Services Overview

| Service | Port | Purpose |
|---------|------|---------|
| `api` | 8000 | FastAPI inference |
| `ui` | 8501 | Streamlit UI |
| `postgres` | 5432 | `predictions` table + `model_deployment_events` audit log |
| `redis` | 6379 | Rate limiting |
| `prometheus` | 9090 | Metrics scraping (API + Pushgateway) |
| `pushgateway` | 9091 | Receives NannyML batch metrics |
| `alertmanager` | 9093 | Alert routing |
| `grafana` | 3000 | Dashboards |
| `nannyml_monitor` | — | Profile: `monitoring`; one-shot CBPE + drift batch job |

---

## Champion/Challenger Deployment

Alias promotion and rollback are managed by two scripts in `scripts/`. Every operation is recorded in the `model_deployment_events` Postgres table (columns: `event_type`, `model_name`, `alias`, `from_version`, `to_version`, `triggered_by`, `reason`, `ts`).

### Promote a model version

Promotes a registered model version to the given alias and logs a `promote` event:

```bash
python scripts/promote_model.py --version 8 --alias champion --promoted-by alice
```

The API's background reload thread picks up the new version within `RELOAD_INTERVAL_S` seconds (default: 60) without blocking in-flight requests.

### Roll back to the previous version

Reads the last `promote` event from `model_deployment_events`, reverses the alias to the previous version, and logs a `rollback` event:

```bash
python scripts/rollback_model.py --alias champion --reason "P95 latency spike" --triggered-by oncall
```

### Model switching via environment variable

For switching between the three registered aliases without a registry promotion:

```bash
# Switch to the scorecard (interpretable) model
echo "MLFLOW_MODEL_ALIAS=scorecard" >> .env
docker compose up -d --build api

# One-liner without modifying .env
MLFLOW_MODEL_ALIAS=scorecard docker compose up -d api
```

### Non-blocking background reload

`ModelLoader.maybe_reload()` spawns a daemon thread so reloads never block in-flight requests. Health checks return `200` throughout a reload, even if the reload fails. The active alias and version are always reflected in the `model_version_info` gauge.

---

## Monitoring

### Observability services

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Pushgateway | http://localhost:9091 | — |
| Alertmanager | http://localhost:9093 | — |

### Grafana dashboard (3 rows)

**Row 1 — System Observability**
Request Rate, Latency p50/p95, Error Rate, Model Reload Events

**Row 2 — Model Observability**
Probability Heatmap, Decision Distribution, Feature Missing Rate, Reload Success/Failure, Active Model Version

**Row 3 — NannyML: Estimated Performance and Drift**
Estimated AUC (CBPE), Estimated F1, Drifted Features count, Last NannyML Run timestamp

### Alert rules

Five rules defined in `monitoring/alert_rules.yml`:

| Rule | Condition |
|------|-----------|
| `HighErrorRate` | Error rate > 1% for 5 min |
| `HighLatencyP95` | P95 latency > 500 ms for 5 min |
| `APIDown` | API unreachable for 1 min |
| `ModelReloadFailing` | `model_reload_failure_total` increases in any 15 min window |
| `HighFeatureMissingRate` | p90 missing-feature fraction > 70% for 5 min |

### NannyML monitoring (CBPE + drift)

`monitoring/nannyml_monitor.py` is a batch job that estimates model performance without ground-truth labels and detects feature drift.

**What it does:**
1. Builds reference predictions from `data/processed/test_data.csv` (4000 rows), cached as `monitoring/nannyml_reference.csv`
2. Pulls live predictions from the Postgres `predictions` table
3. Runs **CBPE** (Confidence-Based Performance Estimation) to estimate AUC and F1 without ground truth
4. Runs univariate drift (Jensen-Shannon divergence) and multivariate drift (PCA reconstruction error)
5. Pushes 5 metrics to Prometheus Pushgateway
6. Saves HTML reports and `reports/nannyml/latest_summary.json`

**Pushgateway metrics:**

| Metric | Description |
|--------|-------------|
| `nannyml_estimated_auc` | CBPE-estimated AUC for the current window |
| `nannyml_estimated_f1` | CBPE-estimated F1 for the current window |
| `nannyml_drifted_features_count` | Number of features flagged as drifted |
| `nannyml_production_rows` | Number of production rows analysed |
| `nannyml_last_run_timestamp_seconds` | Unix timestamp of the last completed run |

**Run the monitor:**

```bash
docker compose --profile monitoring run --rm nannyml_monitor
```

The `nannyml_monitor` service uses a separate `requirements-monitor.txt` (nannyml, lightgbm, etc.) so the main API image stays lean (2.96 GB unchanged).

### Evidently drift reports

```bash
python monitoring/drift_report.py
# → monitoring/reports/drift_report.html
```

---

## Project Structure

```
credit-mlops/
├── src/
│   ├── data_prep.py          # Data loading, versioning, train/test split
│   ├── features.py           # sklearn Pipeline: KNN impute → Winsorize → GroupPCA → RFE
│   ├── scorecard.py          # WOE binning + LR scorecard + explain()
│   ├── train.py              # MLflow runs: LR, XGBoost, Scorecard
│   ├── evaluate.py           # Evaluation utilities
│   ├── register.py           # Model registry aliases
│   └── pipeline.py           # DAG orchestrator
├── api/
│   ├── main.py               # FastAPI app + FEATURE_MISSING_RATE + deployment_events + trace_id + model_alias
│   ├── model_loader.py       # MLflow registry loader, background reload thread, MODEL_RELOAD metrics, MODEL_INFO gauge
│   ├── decision.py           # Threshold logic, score-to-band mapping
│   └── schemas.py            # Pydantic models; PredictResponse includes model_alias + trace_id
├── scripts/
│   ├── promote_model.py      # Promote a version to an alias; logs promote event to Postgres
│   └── rollback_model.py     # Reverse last promotion; logs rollback event to Postgres
├── monitoring/
│   ├── prometheus.yml        # Scrapes API + Pushgateway (honor_labels=true)
│   ├── alert_rules.yml       # 5 alert rules
│   ├── drift_report.py       # Evidently HTML drift reports
│   ├── nannyml_monitor.py    # CBPE + univariate/multivariate drift → Pushgateway
│   ├── Dockerfile.monitor    # Separate image using requirements-monitor.txt
│   └── grafana/
│       ├── dashboard.json    # 3-row dashboard (System / Model / NannyML)
│       ├── datasource.yml
│       └── dashboards.yml
├── tests/
│   ├── test_api.py
│   ├── test_chaos.py
│   ├── test_contract.py
│   ├── test_decision.py
│   ├── test_deployment.py    # 14 tests: non-blocking reload, trace_id, model_alias, metrics, promote/rollback
│   ├── test_evaluate.py
│   ├── test_features.py
│   └── test_scorecard.py
├── reports/
│   ├── nannyml/              # latest_summary.json + HTML report per run
│   ├── reproduce.md
│   ├── results.md
│   ├── debug_workflows.md
│   └── lesson-learned.md
├── ui/
│   ├── streamlit_app.py      # Model alias + source dropdowns in sidebar
│   └── Dockerfile
├── artifacts/
│   ├── fallback_model.joblib
│   ├── scorecard_model.joblib
│   └── feature_pipeline.joblib
├── Dockerfile
├── docker-compose.yml        # 9 services + nannyml_monitor profile
├── requirements.txt
├── requirements-monitor.txt  # nannyml, lightgbm etc. — monitor image only
├── pyproject.toml
└── uv.lock
```
