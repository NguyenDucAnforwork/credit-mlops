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
# Expected: 54+ passed, 0 failed
```

## 6. Start the full stack with Docker Compose

```bash
docker compose up -d --build
```

Services started:
| Service | Port | Description |
|---------|------|-------------|
| api | 8000 | FastAPI inference service |
| postgres | 5432 | Audit log database |
| redis | 6379 | Rate limiting |
| prometheus | 9090 | Metrics scraping |
| alertmanager | 9093 | Alert routing |
| grafana | 3000 | Dashboards (admin/admin) |

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

## 8. Run drift detection

```bash
python monitoring/drift_report.py
# Outputs: monitoring/reports/drift_report.html + drift_summary.json
```

## 9. Switching the serving model

Set the `MLFLOW_MODEL_ALIAS` environment variable before starting the API:

```bash
# Serve scorecard model
MLFLOW_MODEL_ALIAS=scorecard docker compose up -d --build api

# Serve XGBoost champion (default)
MLFLOW_MODEL_ALIAS=champion docker compose up -d --build api

# Serve LR challenger
MLFLOW_MODEL_ALIAS=challenger docker compose up -d --build api
```

## Common issues

| Issue | Fix |
|-------|-----|
| `numpy` install fails | Use Python 3.12, not 3.13 |
| `__main__.FeaturePipeline` pickle error | Run `python src/save_pipeline.py` instead of `python src/features.py` directly |
| API health = `degraded` | Champion alias not set in registry, or `artifacts/fallback_model.joblib` missing |
| Docker build fails on `psycopg2` | Install `gcc libpq-dev` (already in Dockerfile) |
| MLflow auth fails | Use `MLFLOW_TRACKING_PASSWORD` (not `DAGSHUB_TOKEN`) |
