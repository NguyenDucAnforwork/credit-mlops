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

---

## 18. NannyML integration — reference dataset must include model predictions

**Context:** Integrating NannyML CBPE for performance estimation without labels.

**Problem:** `data/processed/reference.csv` (16,000 rows, 122 features) has no `label` column and no model predictions. NannyML's `CBPE.fit()` requires `y_true`, `y_pred_proba`, and `y_pred` on the reference data. Using `reference.csv` directly would fail silently with a KeyError.

**Root cause:** `reference.csv` was created in `data_prep.py` as the train+test split of raw features only (no label). The ground truth labels are in `test_data.csv` (4,000 rows, 123 columns including `label`).

**Fix:** Use `test_data.csv` as the NannyML reference:
1. Load `test_data.csv` (has `label` column).
2. Run the local fallback scorecard model on all 4,000 rows to generate `y_pred_proba` and `y_pred`.
3. Cache the result as `monitoring/nannyml_reference.csv` — this avoids repeating the model run on every monitor execution.
4. Delete `nannyml_reference.csv` to force a rebuild after a model version change.

**Why this matters for CBPE:**
- CBPE fits an internal probability calibration curve on the reference data using `y_true` and `y_pred_proba`.
- If the reference predictions come from a **different** model version than the one making production predictions, the calibration will be wrong and CBPE estimates will be misleading.
- The cache rebuild signal (delete file) must be documented as part of any promote/rollback workflow.

---

## 19. NannyML production data — JSONB unnesting for feature drift

**Context:** Pulling production features from Postgres for NannyML drift detection.

**Problem:** The `predictions` table stores raw request features as a JSONB column. Most API requests only contain 12–14 of the 122 features (partial inputs). NannyML's `UnivariateDriftCalculator` requires consistent non-null columns across the analysis window.

**Approach:**
1. `pd.json_normalize(df["features"].tolist())` unpacks JSONB into a 122-column DataFrame; columns absent from a request are NaN.
2. Before running drift, filter to features where `prod[col].notna().mean() >= 0.30` — only drift-check features that are populated in at least 30% of production requests.
3. This avoids NannyML raising errors on all-null columns while still catching drift in the features that are actually being sent.

**Chunk size selection:**
- NannyML requires minimum ~50 rows per chunk for statistical tests to have any power.
- Formula: `chunk_size = max(50, len(prod) // 7)` — targets 7 chunks, guaranteed ≥50 rows each.
- With small Postgres datasets (< 50 rows), the monitor exits early with a clear log message rather than raising an exception.

---

## 20. Prometheus Pushgateway — batch job metrics pattern

**Context:** NannyML monitor runs as a one-shot batch job (Docker Compose `run --rm`), not a long-running service. Prometheus scrapes running services, not one-shot containers.

**Problem:** A one-shot script cannot expose a `/metrics` endpoint that Prometheus can scrape — the container exits before Prometheus polls it.

**Solution — Pushgateway:**
- Add `prom/pushgateway:v1.10.0` as a persistent service in docker-compose.
- NannyML monitor script uses `prometheus_client.push_to_gateway()` to POST metrics to Pushgateway at job completion.
- Prometheus scrapes Pushgateway with `honor_labels: true` (preserves the `job="nannyml_monitor"` label pushed by the script, not overwritten with `job="pushgateway"`).
- Grafana queries `nannyml_estimated_auc{job="nannyml_monitor"}` etc.

**`honor_labels: true` is critical:**
Without it, Prometheus replaces the pushed `job` label with `pushgateway`, making all NannyML metrics show `job="pushgateway"` in Grafana. The Grafana panel queries would stop matching.

**Stale metrics:**
Pushgateway persists the last pushed value indefinitely. If the monitor hasn't run in a week, Grafana will still show the old AUC. Use the `nannyml_last_run_timestamp_seconds` gauge (also pushed) to detect stale data — if it's > 7 days old, trigger a manual run.

---

## 21. NannyML v0.13 column structure — `to_df()` MultiIndex layout

**Context:** `monitoring/nannyml_monitor.py` needed to extract estimated AUC and drift alert counts from NannyML result objects.

**Problem:** The code was written using column names from the NannyML documentation (`'estimated'`, `'alert'`), but the actual installed version (v0.13) uses different sub-column names. The `_extract_scalar()` helper was passing `sub="estimated"` but the CBPE result DataFrame had no such column, causing:
```
TypeError: unsupported format string passed to NoneType.__format__
```
(because `_extract_scalar` returned `None` when the lookup failed, which was then passed to an f-string formatter).

**Diagnosis:** Run inside the container to inspect actual column structure:
```bash
docker compose run --rm nannyml_monitor python3 -c "
import nannyml as nml, pandas as pd
ref = pd.read_csv('monitoring/nannyml_reference.csv')
prod = pd.read_csv('monitoring/test_dump.csv')  # or any prod slice
cbpe = nml.CBPE(y_pred_proba='y_pred_proba', y_pred='y_pred', y_true='y_true',
                problem_type='binary_classification', metrics=['roc_auc', 'f1'],
                chunk_size=50)
cbpe.fit(ref)
res = cbpe.estimate(prod)
print(res.to_df().columns.tolist())
"
```
Actual output:
```
[('roc_auc', 'value'), ('roc_auc', 'sampling_error'), ('roc_auc', 'realized'),
 ('roc_auc', 'upper_confidence_boundary'), ('roc_auc', 'lower_confidence_boundary'),
 ('roc_auc', 'upper_threshold'), ('roc_auc', 'lower_threshold'), ('roc_auc', 'alert'), ...]
```
CBPE uses a **2-level MultiIndex** `(metric, sub)` where sub is `'value'`, not `'estimated'`.

Drift calculators (`UnivariateDriftCalculator`, `DataReconstructionDriftCalculator`) use a **3-level MultiIndex** `(feature, method, sub)` — e.g. `('NUMBER_OF_LOANS', 'jensen_shannon', 'alert')`.

**Fix — two helpers that handle both structures:**
```python
def _extract_scalar(df, keyword, sub="value"):
    """keyword matches 2-level (CBPE) or outer level of 3-level (drift) MultiIndex."""
    for col in df.columns:
        if keyword.lower() in str(col[0]).lower() and col[1] == sub:
            v = df[col].dropna()
            return float(v.iloc[-1]) if len(v) else None
    return None

def _count_alerts(df, keyword):
    """Count alert chunks; skip 3-level drift columns (they use len(col)==3)."""
    for col in df.columns:
        if len(col) == 2 and keyword.lower() in str(col[0]).lower() and col[1] == "alert":
            return int(df[col].sum())
    return 0

def _drifted_features(drift_df):
    """Return feature names where jensen_shannon alert fired."""
    drifted = []
    for col in drift_df.columns:
        if len(col) == 3 and col[2] == "alert":
            if drift_df[col].any():
                drifted.append(col[0])
    return list(set(drifted))
```

**Rule:** When integrating any NannyML version, always run `result.to_df().columns.tolist()` interactively before writing column-extraction code. The library does not guarantee stable column names across minor versions. The installed version's actual output is the authoritative spec, not the docs.

---

## 22. NannyML Grafana panels show "No data" after a reboot — Pushgateway is ephemeral

**Symptom:** The Grafana "NannyML — Estimated Performance & Drift" row (Estimated AUC, F1, Drifted Features, Last NannyML Run) all show **No data**, even though the monitor ran successfully in a previous session.

**Diagnosis — walk the metric chain backwards:**
```bash
# 1. Is the metric in Pushgateway?
curl -s http://localhost:9091/metrics | grep '^nannyml'      # → EMPTY

# 2. Is Pushgateway even up?
curl -s http://localhost:9091/metrics | grep pushgateway_build_info   # → up, v1.10.0

# 3. How long has it been up?
docker compose ps pushgateway    # → "Up 14 minutes"  (recently restarted)
```
Pushgateway was up but held **zero** metrics. Both conditions were true:
1. **Pushgateway stores metrics in memory by default** — a container restart (here, after an out-of-disk reboot) wipes every pushed value.
2. The `nannyml_monitor` is a one-shot `run --rm` job — nothing re-pushes automatically after a restart.

So the panels were correct: there genuinely was no data. This is **not** a Grafana query bug or a metric-name mismatch.

**Immediate fix:** re-run the monitor.
```bash
docker compose --profile monitoring run --rm nannyml_monitor
```

**Durable fix:** enable Pushgateway persistence so pushed metrics survive restarts. Two parts are both required:
```yaml
pushgateway:
  image: prom/pushgateway:v1.10.0
  user: root                                       # <-- see permission trap below
  command:
    - "--persistence.file=/data/pushgateway.store"
    - "--persistence.interval=1m"
  volumes:
    - pushgateway_data:/data
```

**The permission trap (second bug, surfaced only after enabling persistence):**
After adding the volume, the store file still never appeared and metrics still vanished on restart. The logs revealed why:
```
level=error msg="error persisting metrics" err="open /data/pushgateway.store.in_progress.3605873923: permission denied"
```
The `prom/pushgateway` image runs as the unprivileged `nobody` user (UID 65534), but a fresh named volume is created **root-owned** — so the process cannot write the store file. Adding `user: root` to the service resolves it.

**Validation that the fix actually works (don't trust config alone):**
```bash
docker compose up -d pushgateway
docker compose --profile monitoring run --rm nannyml_monitor   # push
sleep 65                                                       # wait > persistence.interval
docker compose exec pushgateway ls -la /data/                  # store file should now exist
docker compose restart pushgateway && sleep 4
curl -s http://localhost:9091/metrics | grep '^nannyml_estimated_auc'   # should SURVIVE
```
The metric surviving a deliberate restart is the only proof the persistence actually took — the `permission denied` failure mode passes config validation but silently loses data.

**Rule:** Any Prometheus Pushgateway holding batch-job metrics MUST have `--persistence.file` on a writable volume, and you MUST verify writability (file present after `persistence.interval`, value survives a restart). A Pushgateway without persistence is a single reboot away from blank dashboards.
