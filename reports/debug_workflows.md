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

---

## 12. KNNImputer called 3× per request — latency 3221 ms

**Symptom:** `POST /predict` takes ~3200 ms. Profiling shows the bottleneck is the feature pipeline, not model inference.

**Root cause:** `predict_proba`, `predict_credit_score`, and `explain` each call `_get_df()` independently, which runs the full feature pipeline (KNNImputer → Winsorizer → PCA) every time. At inference, KNNImputer scans all ~16,000 training rows × 122 features to find 20 nearest neighbors for each call — O(n_train × n_features) per request, and it ran 3× per request.

**Fix:** Added `predict_all()` method to both `ScorecardModel` and `ModelLoader`. It runs `_get_df()` once and reuses the resulting DataFrame for probability, credit score, and breakdown:

```python
# Before: 3 separate pipeline runs
proba   = loader.predict_proba(df)          # KNN runs #1
score   = loader.predict_credit_score(df)   # KNN runs #2
explain = loader.explain(df)                # KNN runs #3

# After: single pipeline run
all_results = loader.predict_all(df)        # KNN runs once
default_prob = float(all_results["proba"][0])
scorecard_score = float(all_results["credit_score"][0])
sc_breakdown = all_results["breakdown"]
```

**Result:** 3221 ms → 288 ms (11× speedup).

---

## 13. PostgreSQL JSONB: `str()` produces invalid JSON

**Symptom:** `POST /predict` succeeds (200 OK) but no rows appear in the `predictions` table. No error logged.

**Root cause:** The audit log inserted `str(features)` into a `JSONB` column. Python's `str(dict)` produces `{'key': None}` — Python repr syntax with single quotes and `None`, both invalid JSON. PostgreSQL silently rejects rows with invalid JSONB on some driver versions, or the driver raises an exception that was swallowed.

**Fix:**

```python
# Wrong — Python repr, not valid JSON
"features": str(features)

# Correct — valid JSON with double quotes and null
"features": json.dumps(features)
```

**Lesson:** Any dict inserted into a JSONB column must go through `json.dumps()`. Never rely on Python's `str(dict)` for serialization.

---

## 14. MLflow 3.x pyfunc returns 2-column DataFrame — wrong probability column

**Symptom:** Default probability for all predictions is near 0 (e.g., 0.27 on a known high-risk profile that should score ~0.73).

**Root cause:** MLflow 3.x sklearn/xgboost pyfunc `predict()` returns a DataFrame shaped `(n, 2)` with columns `[P(class=0), P(class=1)]`. The code took `preds[0]` (first column = P(no_default)) instead of `preds[1]` (last column = P(default)).

**Fix:** Detect the 2-column DataFrame and take the last column:

```python
preds = self._model.predict(pd.DataFrame(X_transformed))
if hasattr(preds, "values"):
    arr = preds.values
    if arr.ndim == 2 and arr.shape[1] >= 2:
        return arr[:, -1].astype(float)   # P(class=last) = P(default)
    preds = arr.flatten()
```

**Lesson:** MLflow 3.x changed pyfunc predict() return shape. Always check output dimensionality when upgrading MLflow. Taking `arr[:, -1]` is safe for both binary and multi-class (last class = highest label).

---

## 15. Winsorizer bounds — suspiciously narrow range for balance columns

**Symptom:** Changing `OUTSTANDING_BAL_LOAN_CURRENT` from 50M VND to 80M VND produces identical credit score.

**Root cause:** `Winsorizer(capping_method='iqr', tail='both', fold=1.5)` clips at 5th–95th percentile of training data. For balance columns the learned bounds are `(1,000,000 – 1,001,790)` — a 1,790 VND range. Any value above 1,001,790 is clipped to the same maximum.

**Likely cause:** Training data balance columns were stored in a different unit (e.g., thousands of VND) and the deployed UI sends raw VND. Re-training on correctly-scaled data would fix this; the Winsorizer bounds would become (e.g., 1,000 – 1,002) when the training data is in thousands.

**Workaround applied:** UI shows the clipped range as a warning; the clipped value is sent to the API. Root fix requires retraining with consistent units.

---

## 16. KNN segment bias with partial inputs — XGBoost over-predicts P(default)

**Symptom:** API request with only 14 count-based features (all balance/enquiry fields = null) returns P(default) ≈ 0.93 even for a profile that the scorecard correctly scores as medium risk (P ≈ 0.45).

**Root cause:** With 108 null fields, KNNImputer finds 20 nearest neighbors using only the 14 provided count features. These neighbors are NOT a representative sample of the population — they are specifically the customers in the training set who match the count profile, which in this dataset is a high-risk segment (customers with 1 loan, 0 enquiries are disproportionately first-time defaulters). KNN then imputes all null balance fields with the MEDIAN OF THAT SEGMENT, not the population median.

**Partial fix:** Pre-fill NaN with global training column medians before running the pipeline. KNN then finds no NaN to process and returns immediately:

```python
def _fill_nulls_with_medians(self, df):
    knn = self._pipeline.pipeline_.named_steps.get("imputer")
    self._train_medians = np.nanmedian(knn._fit_X, axis=0)
    arr = df.values.astype(float)
    for j, med in enumerate(self._train_medians):
        arr[np.isnan(arr[:, j]), j] = med
    return pd.DataFrame(arr, columns=df.columns)
```

Mean P(default) dropped from 0.926 to 0.850 with this fix, but XGBoost still cannot correctly discriminate risk for partial inputs.

**Root cause of residual failure:** XGBoost was trained on fully-populated features. The model has learned feature interactions that require accurate values in multiple correlated features. Median-filled values for 108/122 features violate those learned feature interactions.

**Architectural recommendation:** Use the scorecard as the default for partial-input use cases. The scorecard only uses 18 features and handles partial inputs well. XGBoost with median-fill is unreliable for incomplete profiles.

---

## 17. Grafana "Default Probability Distribution" — double-bucketing with `type: histogram`

**Symptom:** The "Default Probability Distribution" panel shows X-axis from 0 to 4 (not 0 to 1), and sometimes Y-axis in range [0, 0.006]. Bars do not represent probability buckets.

**Root cause (two layers):**

**Layer 1 — `rate()` Y-axis confusion:** Using `rate(prediction_default_prob_bucket[10m])` returns observations per second, not probability values. With 2–3 predictions in a 10-minute window, the rate is `3/600 ≈ 0.005` — which is why Y-axis showed [0, 0.006]. The user misread this as the probability range.

**Layer 2 — Double-bucketing with `type: "histogram"`:** This is the deeper bug. Prometheus already pre-buckets the data into fixed bins [0.1, 0.2, ..., 1.0]. When Grafana's `"type": "histogram"` panel receives these pre-bucketed count values (e.g., `le="0.7" → 2`), it treats `2` as a raw data point and creates NEW histogram buckets of those count values. Result: X-axis becomes [0, 4] (count ranges like "0–0.8", "0.8–1.6" counts), not [0, 1] (probability values).

```
Prometheus sends: le=0.1→0, le=0.2→0, ..., le=0.7→2, le=0.8→2, ..., le=1.0→2
Grafana histogram type re-buckets count values: [0-0.4], [0.4-0.8], ... → wrong
Correct approach: use barchart type to read le labels directly as X-axis
```

**Fix attempt 1 — barchart (failed: empty panel):**
Changed `"type": "histogram"` → `"type": "barchart"` with `increase()` + Reduce transformation.
Empty because:
- `instant: true` + `$__range`: if no predictions in the dashboard time window, `increase()` returns nothing
- `instant: true` + Reduce transformation: instant frames are a different data type than time-series frames; Reduce may produce an empty or mis-typed output the barchart cannot render
- Missing `"xField": "Field"` in options: without it, barchart has no X-axis field and renders blank

**Fix attempt 2 — barchart with raw counter (still empty):**
Switched to `prediction_default_prob_bucket` (raw cumulative counter, no `instant: true`).
Still empty because the barchart + Reduce pipeline still had the `xField` misconfiguration.

**Final fix — heatmap with `calculate: false`:**

```json
{
  "type": "heatmap",
  "targets": [{"expr": "sum(increase(prediction_default_prob_bucket[$__rate_interval])) by (le)", "legendFormat": "{{le}}"}],
  "options": {
    "calculate": false,
    "color": {"scheme": "YlOrRd", "mode": "scheme"},
    "filterValues": {"le": 1e-9},
    "yAxis": {"label": "P(default)"}
  }
}
```

Key flags:
- `calculate: false` — tells Grafana NOT to re-bucket (Prometheus data already bucketed)
- `sum(...) by (le)` — aggregates across multiple API instances safely
- `$__rate_interval` — auto-selects window size based on dashboard zoom level
- `filterValues.le: 1e-9` — hides empty cells, focuses color on populated buckets
- `scheme: "YlOrRd"` — yellow (sparse) → red (dense) intuitive density coloring

**Why heatmap beats barchart for this use case:**
- Shows distribution OVER TIME (not just a snapshot) → enables drift detection
- X=time, Y=P(default) bucket, Color=prediction density → one glance shows if distribution shifts
- Handles Prometheus cumulative histogram correctly via the native `le` label detection
- No transformation pipeline needed — the panel type natively understands Prometheus histogram format
