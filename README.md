# Credit Scoring MLOps

End-to-end credit default prediction system with MLflow experiment tracking, FastAPI inference service, and full observability stack.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Training Pipeline                            │
│  raw CSV → data_prep → feature_fit → train (LR/XGB/Scorecard)      │
│                          ↓ MLflow (DagsHub)                         │
│              champion / challenger / scorecard aliases              │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ model artifacts
┌─────────────────────────▼───────────────────────────────────────────┐
│                     Inference Stack (Docker)                        │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌────────────────┐    │
│  │  FastAPI  │  │ Postgres │  │   Redis   │  │   Prometheus   │    │
│  │  :8000   │→ │ audit log│  │rate limit │  │ + Alertmanager │    │
│  └──────────┘  └──────────┘  └───────────┘  └────────┬───────┘    │
│       ↑                                               ↓            │
│  POST /predict                                  ┌──────────┐       │
│  GET  /health                                   │  Grafana │       │
│  GET  /metrics                                  │  :3000   │       │
└─────────────────────────────────────────────────└──────────┘───────┘
```

## Models

| Alias | Model | AUC | Gini | Notes |
|-------|-------|-----|------|-------|
| `champion` | XGBoost | 0.8223 | 0.6446 | Default serving model |
| `challenger` | LR + SMOTE | 0.8229 | 0.6459 | Baseline comparison |
| `scorecard` | WOE + LR | ~0.81+ | ~0.63+ | Full interpretability |

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

# Grafana dashboard
open http://localhost:3000   # admin / admin
```

---

## Local Development Setup

### Requirements

- Python **3.12.x** (3.13 has no numpy 1.26.4 pip wheel)
- Conda or venv

```bash
conda create -n credit python=3.12 -y
conda activate credit
pip install -r requirements.txt
```

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
pytest tests/ -v
# 62 tests: unit, integration, chaos (fault injection)
```

### Run the API locally

```bash
# Start dependencies
docker compose up -d postgres redis

# Run API
cd api && uvicorn main:app --reload --port 8000
```

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
  "latency_ms": 38.1,
  "scorecard_score": 623.4,
  "scorecard_breakdown": [
    {"feature": "NUM_NEW_LOAN_TAKEN_PCA_1", "raw_value": -0.82, "bin": "(-inf, -0.5]", "woe": 0.71, "score_contribution": 52.3, "iv": 1.40},
    {"feature": "ENQUIRIES_PCA_1",          "raw_value":  0.31, "bin": "(0.1, 0.8]",   "woe": -0.24, "score_contribution": -18.1, "iv": 0.44},
    ...
  ]
}
```

### Decision thresholds

| default_probability | decision |
|---------------------|----------|
| < 0.45 | approve |
| 0.45 – 0.69 | manual_review |
| ≥ 0.70 | reject |

### `GET /metrics`

Prometheus metrics in text format. Scraped automatically by Prometheus at `:9090`.

---

## Monitoring

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Alertmanager | http://localhost:9093 | — |

Grafana dashboard includes: request rate, P95 latency, error rate, score distribution, decision breakdown.

Alert rules (in `monitoring/alert_rules.yml`):
- **HighErrorRate**: error rate > 1% for 5 min
- **HighLatencyP95**: P95 latency > 500ms for 5 min
- **APIDown**: API unreachable for 1 min

### Drift detection

```bash
python monitoring/drift_report.py
# → monitoring/reports/drift_report.html
```

---

## Model Switching

The serving model is controlled by `MLFLOW_MODEL_ALIAS` (default: `champion`).

```bash
# Switch to scorecard (interpretable)
echo "MLFLOW_MODEL_ALIAS=scorecard" >> .env
docker compose up -d --build api

# Or one-liner without modifying .env
MLFLOW_MODEL_ALIAS=scorecard docker compose up -d api
```

To promote a new model version to champion:

```bash
python -c "
from src.register import promote_to_champion
promote_to_champion('<version_number>')
"
# API reloads within 60s (RELOAD_INTERVAL_S)
```

---

## Project Structure

```
credit-mlops/
├── src/                    # Training pipeline
│   ├── data_prep.py        # Data loading, versioning, train/test split
│   ├── features.py         # sklearn Pipeline: KNN impute → Winsorize → GroupPCA → RFE
│   ├── scorecard.py        # WOE binning + LR scorecard + explain()
│   ├── train.py            # MLflow runs: LR, XGBoost, Scorecard
│   ├── register.py         # Model registry aliases
│   └── pipeline.py         # DAG orchestrator
├── api/                    # Inference service
│   ├── main.py             # FastAPI app + Prometheus metrics + audit log
│   ├── model_loader.py     # MLflow registry loader with fallback
│   ├── decision.py         # Threshold logic, score-to-band mapping
│   └── schemas.py          # Pydantic request/response models
├── monitoring/
│   ├── prometheus.yml       # Scrape config
│   ├── alert_rules.yml      # HighErrorRate, HighLatency, APIDown
│   ├── drift_report.py      # Evidently drift detection
│   └── grafana/            # Dashboard + datasource provisioning
├── tests/                  # 62 tests: unit, integration, chaos
├── reports/
│   ├── reproduce.md         # Step-by-step reproduction guide
│   ├── results.md           # Model comparison & metrics summary
│   ├── debug_workflows.md   # Environment & deployment bugs + fixes
│   └── lesson-learned.md    # Training/evaluation logic lessons
├── artifacts/
│   └── fallback_model.joblib  # Disaster recovery fallback
├── Dockerfile
└── docker-compose.yml      # 6 services: api, postgres, redis, prometheus, alertmanager, grafana
```
