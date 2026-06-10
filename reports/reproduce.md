# Reproduction Guide

Complete step-by-step instructions to reproduce the credit scoring MLOps project from a clean environment.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12.x | 3.13 has no numpy 1.26.4 pip wheel |
| Docker + Docker Compose | 27.x / 2.x | Docker Desktop with WSL2 on Windows |
| Git | any | |
| DagsHub account | - | For MLflow remote tracking |

## 1. Clone and configure

```bash
git clone https://github.com/NguyenDucAnforwork/credit-mlops.git
cd credit-mlops
```

Create `.env` (never commit this file):

```env
MLFLOW_TRACKING_URI=https://dagshub.com/<your_user>/credit-mlops.mlflow
MLFLOW_TRACKING_USERNAME=<your_dagshub_username>
MLFLOW_TRACKING_PASSWORD=<your_dagshub_token>   # NOT DAGSHUB_TOKEN — MLflow reads this key

POSTGRES_USER=credituser
POSTGRES_PASSWORD=creditpass
POSTGRES_DB=creditdb
DATABASE_URL=postgresql://credituser:creditpass@postgres:5432/creditdb
REDIS_URL=redis://redis:6379/0
```

Place raw dataset at `data/raw/01_dataset.csv`.

## 2. Create Python environment

```bash
conda create -n credit python=3.12 -y
conda activate credit
pip install -r requirements.txt
```

## 3. Run the full training pipeline

```bash
# Full run (data prep + feature fit + train LR/XGBoost/Scorecard + register)
python src/pipeline.py

# Or with caching if data/features haven't changed:
python src/pipeline.py --skip-data-prep --skip-feature-fit
```

Pipeline steps:
1. **data_prep** — SHA256-hashes raw CSV → stratified 80/20 split → saves `data/processed/{train,test,reference}.csv`
2. **feature_fit** — KNNImputer(k=20) → Winsorizer(5-95%) → GroupPCA → RFE(22 features) → `artifacts/feature_pipeline.joblib`
3. **train** — 3 MLflow runs logged to DagsHub:
   - `logistic_regression_baseline` (SMOTE + StandardScaler)
   - `xgboost_challenger`
   - `scorecard_woe_lr` (WOE binning + GridSearchCV)
4. **register** — sets aliases: LR→challenger, XGBoost→champion, Scorecard→scorecard

## 4. Create fallback model artifact

The API uses this when MLflow is unreachable:

```bash
python -c "
import sys; sys.path.insert(0, 'src')
import pandas as pd, joblib
from xgboost import XGBClassifier
train_df = pd.read_csv('data/processed/train_data.csv')
X, y = train_df.drop(columns=['label']).values, train_df['label'].values
model = XGBClassifier(n_estimators=50, max_depth=4, scale_pos_weight=int((y==0).sum()/(y==1).sum()), random_state=42, verbosity=0)
model.fit(X, y)
joblib.dump(model, 'artifacts/fallback_model.joblib')
print('Saved fallback model')
"
```

## 5. Run tests

```bash
pytest tests/ -v
# Expected: 76 passed, 0 failed
# New: tests/test_deployment.py — 14 tests for champion/challenger deployment
```

## 6. Start the full stack with Docker Compose

```bash
docker compose up -d --build
```

Services started (8 always-on + nannyml_monitor profile = 9 total):
| Service | Port | Description |
|---------|------|-------------|
| api | 8000 | FastAPI inference service |
| streamlit | 8501 | Streamlit UI |
| postgres | 5432 | Audit log database |
| redis | 6379 | Rate limiting |
| prometheus | 9090 | Metrics scraping |
| alertmanager | 9093 | Alert routing |
| grafana | 3000 | Dashboards (admin/admin) |
| pushgateway | 9091 | Receives NannyML batch metrics (Pushgateway) |
| nannyml_monitor | — | NannyML drift/performance monitor (monitoring profile) |

## 7. Verify the stack

```bash
# Health check
curl http://localhost:8000/health

# Test prediction (use numeric features from processed data)
python -c "
import pandas as pd, json, math, requests
df = pd.read_csv('data/processed/test_data.csv')
row = df.drop(columns=['label']).iloc[0]
payload = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.to_dict().items()}
r = requests.post('http://localhost:8000/predict', json=payload)
print(r.json())
"

# Prometheus metrics
curl http://localhost:8000/metrics

# Grafana dashboard
open http://localhost:3000  # admin / admin
```

## 8. Champion/Challenger deployment workflow

### Promote a model version to an alias
```bash
# Promote version 8 to champion alias (e.g. after a successful challenger evaluation)
python scripts/promote_model.py --version 8 --alias champion --promoted-by alice

# Promote scorecard version 7 to the scorecard alias
python scripts/promote_model.py --version 7 --alias scorecard --promoted-by ci-bot
```
The script sets the MLflow registry alias and logs a `promote` event to the `model_deployment_events` Postgres table.

### Roll back to the previous version
```bash
# Roll back champion to whatever version it was before the last promotion
python scripts/rollback_model.py --alias champion --reason "P95 latency spike" --triggered-by oncall
```
Reads the last `promote` record from `model_deployment_events`, reverses the alias, logs a `rollback` event.

### Check deployment history
```bash
# View all promote/rollback events
psql postgresql://credituser:creditpass@localhost:5432/creditdb \
  -c "SELECT ts, event_type, alias, from_version, to_version, triggered_by, reason FROM model_deployment_events ORDER BY ts DESC LIMIT 10;"
```

### API model/source override (per-request, no restart needed)
```bash
# Use scorecard model, force DagsHub source
curl -X POST "http://localhost:8000/predict?model=scorecard&source=dagshub" \
  -H "Content-Type: application/json" \
  -d '{"NUMBER_OF_LOANS": 3.0}'

# Use local fallback model
curl -X POST "http://localhost:8000/predict?model=champion&source=local" \
  -H "Content-Type: application/json" \
  -d '{"NUMBER_OF_LOANS": 3.0}'
```

## 9. Run NannyML performance estimation and drift detection

NannyML estimates model AUC **without ground truth labels** using CBPE (Confidence-Based Performance Estimation). Useful because credit default labels arrive 3–12 months after the loan decision.

### Seed production data (first run only)
The monitor requires ≥50 predictions in the `predictions` table:
```bash
python -c "
import requests, random
for _ in range(60):
    r = requests.post('http://localhost:8000/predict', json={
        'NUMBER_OF_LOANS': random.uniform(1, 10),
        'ENQUIRIES_3M': random.uniform(0, 8),
        'NUMBER_OF_CREDIT_CARDS': random.uniform(0, 5),
    })
    assert r.status_code == 200
print('Seeded 60 predictions')
"
```

### Run the monitor
```bash
docker compose --profile monitoring run --rm nannyml_monitor
```

Expected output:
```
[nannyml] building reference predictions (runs once, then cached)…
[nannyml] reference saved: monitoring/nannyml_reference.csv  (4000 rows, base_rate=0.182)
[nannyml] production: 60 rows  2026-06-06 → 2026-06-06
[nannyml] chunk_size=50  (1 chunks)
[nannyml] CBPE → AUC≈0.7968  F1≈0.6687  alerts=0
[nannyml] drift → 12 features drifted: [...]
[nannyml] metrics pushed to http://pushgateway:9091
[nannyml] done  estimated_auc=0.7968  drifted=12
```

### Outputs
- `reports/nannyml/latest_summary.json` — machine-readable summary
- `reports/nannyml/cbpe_YYYY-MM-DD.html` — CBPE performance chart
- `reports/nannyml/drift_YYYY-MM-DD.html` — univariate drift chart
- Prometheus Pushgateway metrics at `http://localhost:9091` — visible in Grafana NannyML row

### Force reference rebuild (after model version change)
```bash
rm monitoring/nannyml_reference.csv
docker compose --profile monitoring run --rm nannyml_monitor
```

## 10. Run drift detection (legacy)

```bash
python monitoring/drift_report.py
# Outputs: monitoring/reports/drift_report.html + drift_summary.json
```

## 11. Switching the serving model

### Option A: Environment variable (persistent, requires restart)
```bash
# Serve scorecard model
echo "MLFLOW_MODEL_ALIAS=scorecard" >> .env
docker compose up -d api   # no rebuild needed — bind-mounted code

# Serve XGBoost champion (default)
echo "MLFLOW_MODEL_ALIAS=champion" >> .env
docker compose up -d api
```

### Option B: Per-request query parameter (instant, no restart)
```bash
# Use challenger model for this request only
curl -X POST "http://localhost:8000/predict?model=challenger&source=auto" \
  -H "Content-Type: application/json" -d '{"NUMBER_OF_LOANS": 3.0}'
```
The Streamlit UI exposes the same `model` and `source` dropdowns in the sidebar.

### Option C: Promote/rollback scripts (registry-level, persists across restarts)
```bash
python scripts/promote_model.py --version 8 --alias champion --promoted-by alice
# API picks up the new version within RELOAD_INTERVAL_S (3600s) via background thread
# Or restart api to reload immediately: docker compose restart api
```

## Common issues

| Issue | Fix |
|-------|-----|
| `numpy` install fails | Use Python 3.12, not 3.13 |
| `__main__.FeaturePipeline` pickle error | Run `python src/save_pipeline.py` instead of `python src/features.py` directly |
| API health = `degraded` | Champion alias not set in registry, or `artifacts/fallback_model.joblib` missing |
| Docker build fails on `psycopg2` | Install `gcc libpq-dev` (already in Dockerfile) |
| MLflow auth fails | Use `MLFLOW_TRACKING_PASSWORD` (not `DAGSHUB_TOKEN`) |
| `nannyml_monitor` exits with "insufficient production data" | Need ≥50 rows in `predictions` table — seed with the snippet in Step 9 |
| NannyML CBPE estimated AUC is None | NannyML `to_df()` uses MultiIndex `('roc_auc', 'value')` — sub-column is `'value'` not `'estimated'` |
| Pushgateway metrics missing in Grafana | Check `honor_labels: true` in `monitoring/prometheus.yml`; verify Prometheus scraping pushgateway:9091 |
| NannyML Grafana row shows "No data" after a reboot | Pushgateway lost in-memory metrics on restart. Persistence is now enabled (`--persistence.file` + `pushgateway_data` volume + `user: root`); if metrics are still gone, just re-run the monitor (Step 9). Verify it survives: `docker compose restart pushgateway && curl -s localhost:9091/metrics \| grep nannyml` |
| Pushgateway store file not written (`permission denied` in logs) | Image runs as `nobody` (UID 65534) but the named volume is root-owned. `user: root` on the pushgateway service (already in compose) fixes it |
| `nannyml_reference.csv` shows stale model metrics | Delete the file and re-run the monitor to regenerate with the current model version |
| Docker disk full during nannyml build | Run `docker builder prune -f` — freed 14.6 GB of build cache in our case |
