# Debug Workflows

Environment, deployment, and MLOps-specific issues encountered during this project and how they were resolved.

---

## 1. Python 3.13 — no numpy wheel

**Symptom:** `pip install numpy==1.26.4` fails on Python 3.13 with "no matching distribution found".

**Root cause:** numpy 1.26.4 pre-dates Python 3.13; PyPI has no pre-built wheel for that combination.

**Fix:** Use Python 3.12 in Docker and locally.

```dockerfile
# Wrong
FROM python:3.13-slim

# Correct
FROM python:3.12-slim
```

**Lesson:** Always pin Python version in Dockerfile. Check PyPI wheel availability for your full requirements stack before committing to a Python version.

---

## 2. MLflow env variable naming

**Symptom:** `mlflow.set_tracking_uri(dagshub_uri)` works locally but authentication fails with 401.

**Root cause:** The env var name matters. MLflow reads `MLFLOW_TRACKING_PASSWORD` for basic auth, not `DAGSHUB_TOKEN`.

**Fix:**

```env
# Wrong
DAGSHUB_TOKEN=...

# Correct
MLFLOW_TRACKING_PASSWORD=...
```

**Debug steps:**
```bash
python -c "import mlflow, os; mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI']); print(mlflow.search_experiments())"
```

---

## 3. API container crash on startup — "No model available"

**Symptom:** `docker compose up` → API exits immediately with `RuntimeError: No model available: registry down and no fallback artifact found`.

**Root cause (multi-part):**
1. The MLflow champion alias wasn't set yet (pipeline still running).
2. `artifacts/fallback_model.joblib` didn't exist yet.
3. `model_loader._load_fallback()` raised `RuntimeError` instead of gracefully degrading.
4. The lifespan handler didn't catch the exception.

**Fix:**
- Changed `_load_fallback()` to print a warning and leave `_model = None` instead of raising.
- Wrapped `loader.load()` in `try/except` in `lifespan()` so the API starts in degraded mode.
- Created `artifacts/fallback_model.joblib` (lightweight XGBoost, 50 estimators) before building the Docker image.

```python
# model_loader.py — before
def _load_fallback(self):
    if FALLBACK_MODEL_PATH.exists():
        ...
    else:
        raise RuntimeError("No model available...")   # crashed the API

# After
def _load_fallback(self):
    if FALLBACK_MODEL_PATH.exists():
        ...
    else:
        print("[model_loader] WARNING: no fallback — degraded mode")
        # _model stays None; /health returns "degraded"
```

```python
# main.py lifespan — before
async def lifespan(app):
    loader.load()   # exception propagated → startup failure
    yield

# After
async def lifespan(app):
    try:
        loader.load()
    except Exception as exc:
        print(f"[startup] model load failed (degraded mode): {exc}")
    yield
```

---

## 4. MLflow 3.x — `register_model` with `artifact_path` deprecated

**Symptom:** `mlflow.register_model(...)` raises `INVALID_PARAMETER_VALUE`.

**Root cause:** MLflow 3.x introduced LoggedModel entities. `artifact_path` parameter is deprecated; use `name` instead. Also, inline registration via `registered_model_name` in `log_model()` is the preferred path.

**Fix:**

```python
# Old (MLflow 2.x)
mlflow.sklearn.log_model(model, artifact_path="model")
mlflow.register_model(f"runs:/{run_id}/model", "credit_score_model")

# New (MLflow 3.x)
mlflow.sklearn.log_model(
    model,
    name="model",                              # not artifact_path
    registered_model_name="credit_score_model",  # inline registration
)
```

---

## 5. joblib pickle — `__main__.FeaturePipeline` module identity

**Symptom:** Loading `feature_pipeline.joblib` raises `AttributeError: Can't get attribute 'FeaturePipeline' on <module '__main__' from 'features.py'>`.

**Root cause:** When you run `python src/features.py`, Python sets `__name__ == "__main__"`. joblib pickles the class as `__main__.FeaturePipeline`. When you later load it from `train.py` (which imports `from features import FeaturePipeline`), Python can't find `__main__.FeaturePipeline` because the module is now `features`, not `__main__`.

**Fix:**
1. Created `src/save_pipeline.py` — imports `features` as a module (not `__main__`) then calls `FeaturePipeline().fit().save()`.
2. Added guard in `features.py`:
   ```python
   if __name__ == "__main__":
       raise SystemExit("Run src/save_pipeline.py instead.")
   ```
3. In `conftest.py`, added auto-refit fallback if loaded pipeline has wrong module identity.

---

## 6. Test import module identity mismatch

**Symptom:** Setting `loader_mod._loader = mock_loader` in tests had no effect — the real loader still ran.

**Root cause:** In tests, `import api.model_loader as loader_mod` creates a *different module object* than `main.py`'s `from model_loader import get_loader`. They're the same file but different `sys.modules` entries (`api.model_loader` vs `model_loader`).

**Fix:** Changed all test imports to bare module names (matching how `main.py` imports them):

```python
# Wrong (different module object than main.py uses)
import api.model_loader as loader_mod
import api.main as main_mod

# Correct
import model_loader as loader_mod
import main as main_mod
```

Also required adding `sys.path.insert(0, str(Path(__file__).parent.parent / "api"))` in test files.

---

## 7. GroupPCATransformer IndexError during feature pipeline fit

**Symptom:** `IndexError: index X is out of bounds for axis 1 with size Y` during `FeaturePipeline.fit()`.

**Root cause:** `SingleValueDropper` was positioned *before* `GroupPCATransformer` in the pipeline. It removed some columns, invalidating the hard-coded group column indices that `GroupPCATransformer` computed during its `fit()`.

**Fix:** Reordered pipeline — SingleValueDropper must run *after* GroupPCATransformer:

```python
# Wrong
Pipeline([imputer, winsorizer, single_drop, group_pca])

# Correct
Pipeline([imputer, winsorizer, group_pca, single_drop])
```

---

## 8. RFE convergence warning (sklearn 1.8.0)

**Symptom:** `ConvergenceWarning: lbfgs failed to converge` during RFE feature selection.

**Root cause:** sklearn 1.8.0 removed the default `penalty='l2'` parameter from `LogisticRegression`. Also, `lbfgs` struggles with unscaled features.

**Fix:**
- Removed explicit `penalty='l2'` (now default is no penalty warning).
- Changed solver to `saga` (supports L1/L2/elasticnet, better for large feature sets).
- Added `StandardScaler` before RFE.

---

## 9. Docker Compose — API starts before postgres is ready

**Symptom:** API crashes on startup with `psycopg2.OperationalError: could not connect to server`.

**Root cause:** `depends_on: postgres` only waits for the container to *start*, not for PostgreSQL to be *ready* to accept connections.

**Fix:** Added health checks and `condition: service_healthy`:

```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U credituser"]
    interval: 10s
    retries: 5

api:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

---

## 10. XGBoost run — model artifact not uploaded

**Symptom:** After the previous pipeline session was interrupted, the XGBoost run showed in MLflow experiments but had no `model` artifact (only `pipeline/feature_pipeline.joblib`). `mlflow.register_model()` failed with "unable to find logged_model".

**Root cause:** The session ran out of context window during the large DagsHub artifact upload. The run was marked FINISHED but the model artifact upload was incomplete.

**Fix:** Re-ran only the XGBoost training step (`train_xgboost`), which creates a new run and uploads the model artifact. Then set the `champion` alias on the new version.

**Lesson:** For large artifact uploads (XGBoost model ~20MB), use `--timeout` flags or split the upload from the training step. Monitor artifact upload completion before marking a run as done.

---

## 11. sklearn version mismatch — `'LogisticRegression' object has no attribute 'multi_class'`

**Symptom:** `POST /predict` returns `{"detail":"'LogisticRegression' object has no attribute 'multi_class'"}` after `docker compose up`.

**Root cause:** Training ran on sklearn 1.8.0 (local conda env). The Docker image used `scikit-learn==1.7.2` from `requirements.txt`. sklearn 1.8.0 removed the `multi_class` attribute from the fitted `LogisticRegression` state. When Docker's sklearn 1.7.2 loads the pickled model artifact, its internal `predict_proba` tries to access `self.multi_class` → `AttributeError`.

This is a forward-compatibility pickle issue: a model serialised by a newer sklearn version cannot always be deserialised by an older one if attributes were removed between versions.

**Fix:** Pin `requirements.txt` to match the training environment exactly:

```
# Before (wrong)
scikit-learn==1.7.2

# After (correct)
scikit-learn==1.8.0
```

Then rebuild the API image: `docker compose build api && docker compose up -d api`

**Prevention:** After every training run, sync `requirements.txt` with `pip freeze | grep scikit-learn`. Treat model artifacts and their training environment as a matched pair — mismatched sklearn versions are a silent source of predict failures at serving time.
