# Lessons Learned

Logic bugs, model evaluation pitfalls, and non-obvious decisions encountered during training and evaluation.

---

## 1. Scorecard: INCREASING_BAL_3M_CC is a PCA-group column

**Bug:** The notebook scorecard used `INCREASING_BAL_3M_CC` as a standalone feature. In the MLOps pipeline, this column is in `OUTSTANDING_BAL_COLS` — it gets compressed into `OUTSTANDING_BAL_PCA_1..5` by GroupPCATransformer and disappears from the feature space.

**Impact:** The scorecard implemented in the MLOps pipeline uses 18 features instead of the notebook's 19. This is correct and intentional — using the PCA-compressed form is more principled (removes correlation within the group).

**Decision:** Excluded `INCREASING_BAL_3M_CC` from `SCORECARD_NBINS`. No workaround needed.

---

## 2. WOE #Bad = 0 requires Laplace smoothing

**Bug:** When a bin has zero bad cases, `WOE = log(#Good / #Bad)` = log(inf) = inf. This propagates NaN through the model.

**Fix:** Replace `#Bad == 0` with 1 before computing WOE:
```python
agg["#Bad"] = agg["#Bad"].replace(0, 1)
```

This is standard practice in credit scoring. Without it, features with low default rates in some bins would silently break the model.

---

## 3. Threshold selection: F1-maximizing vs business-driven

**Observation:** Using `sklearn`'s default 0.5 threshold for a 18% default rate dataset gives high precision but terrible recall (misses most defaults). The notebook used F1-maximizing threshold from the PR curve.

**Implementation:** `evaluate.best_threshold()` computes the threshold that maximizes F1 score on the test set. This is logged as `threshold` in MLflow for reproducibility.

**Caution:** F1-maximizing threshold can change significantly between runs (data splits, model changes). A business-driven threshold (e.g., "reject top 30% by risk") is more stable for production. The current system uses fixed decision boundaries in `decision.py` (≥0.70 reject, ≥0.45 review) which are independent of the threshold.

---

## 4. KNN imputation at scale — memory and time

**Observation:** `KNNImputer(n_neighbors=20)` on 16,000 rows × 122 features takes ~8-10 minutes. It computes pairwise distances, which is O(n²).

**Lesson:** For production re-training at scale:
- Consider `n_neighbors=5` as a compromise.
- Or switch to `IterativeImputer` (MICE) which is more memory-efficient.
- Always time the imputation step separately and log it as a metric.

Current pipeline accepts this cost since re-training is infrequent (not real-time).

---

## 5. SMOTE applied to already-imputed data only

**Bug (potential):** SMOTE must be applied *after* imputation but *before* any test-set transformation. The original code applied SMOTE to the fully-transformed training data, which is correct. But an earlier draft applied SMOTE to raw data with NaN values, causing sklearn to crash.

**Rule:** Pipeline order matters strictly:
```
fit_transform(X_train) → SMOTE(X_train_transformed) → LR.fit()
transform(X_test) → LR.predict()
```
Never apply SMOTE to test data or to raw data with missing values.

---

## 6. LR vs XGBoost — near-identical AUC doesn't mean equivalent models

**Observation:** LR AUC=0.8229, XGBoost AUC=0.8223 — essentially the same. XGBoost was set as champion primarily because of the assumption that tree models handle non-linear credit bureau patterns better. But the difference is statistically negligible.

**Lesson:** Use multiple metrics (Gini, KS, PR-AUC) to break ties. In this dataset:
- Gini: LR=0.646, XGB=0.645 — essentially tied
- KS statistic should be checked for credit scoring specifically

**Recommendation:** Champion selection should use business criteria beyond AUC (e.g., false negative rate, model interpretability for regulatory compliance). The scorecard model is preferred in regulated banking for its interpretability even if AUC is slightly lower.

---

## 7. PCA component ordering is not guaranteed across fits

**Bug (latent):** `GroupPCATransformer` assigns names `OUTSTANDING_BAL_PCA_1..5` based on the order PCA components are computed. PCA components are ordered by explained variance — this is deterministic for a given dataset but can change if the data distribution shifts.

**Impact:** If the pipeline is re-fitted on new data, `OUTSTANDING_BAL_PCA_2` might capture a *different* variance direction than before. The scorecard's WOE bins (fitted on the original PCA) become misaligned.

**Rule:** Always re-fit the scorecard WOE bins whenever the feature pipeline is re-fitted. Never use a scorecard fitted on old PCA components with a re-fitted pipeline.

---

## 8. Decision tree binning can produce single-bucket features

**Bug:** For features with very low cardinality (e.g., `SHORT_TERM_COUNT_BANK` with mostly 0/1 values), `DecisionTreeClassifier(max_leaf_nodes=2)` sometimes produces only 1 bin if the feature has no predictive power. WOE cannot be computed for a single bin.

**Fix:** Used `max(2, n_bins)` to ensure at least 2 leaf nodes. Also added `replace({np.inf: 0, -np.inf: 0})` on WOE values to handle edge cases.

---

## 9. GridSearchCV trains 5×8=40 models — time cost

**Observation:** Scorecard `GridSearchCV` with 4 C values × 2 penalties × 5 folds = 40 LR fits. Each LR fit on 16,000 WOE-encoded samples takes <1s, so total is ~1 minute. Acceptable.

**Caution:** If extended to 3 solvers or more C values, time grows linearly. Use `n_jobs=-1` (parallel) — already set in the implementation.

---

## 10. Evidently drift detection — reference data must match production features

**Observation:** `monitoring/drift_report.py` uses `data/processed/reference.csv` (training features before pipeline transform) as the baseline. If compared directly to live `/predict` request payloads (which are also raw features), this is correct.

**Caution:** Do not compare `reference.csv` (raw) against pipeline-transformed features — the distributions are entirely different after winsorization and PCA. The Evidently report would always show drift.

**Rule:** Reference dataset format must match the format of the data being monitored. In this system: both reference and current are raw 122-feature vectors.

---

## 11. Scorecard n parameter — use actual feature count

**Bug (notebook):** The notebook hardcodes `n=12` in the credit score formula. This was the number of features used in the notebook's final scorecard. In the MLOps implementation, we have 18 features.

**Impact:** Using n=12 with 18 features shifts all score values (the offset term `alpha/n` changes). The score scale would be inconsistent.

**Fix:** Set `N_FEATURES = len(SCORECARD_NBINS)` (18) and pass it to `_credit_score_formula`. The 300-850 range is preserved since it's controlled by `thres_score=600` and `pdo=-50`.

---

## 12. KNN imputer causes segment bias for partial-input requests

**Context:** The production API accepts partial requests — only 14 of 122 features are provided; the rest are null.

**What happens:** `KNNImputer(n_neighbors=20)` selects the 20 nearest training neighbors using only non-null columns. With 14 count-based features (number of loans, enquiries), it selects neighbors from a specific demographic: thin-file customers (1 loan, 0 enquiries). In the Vietnamese credit market, thin-file customers are genuinely higher-risk than thick-file customers. The imputed values reflect that segment's balance/behaviour patterns, not the population average.

**Effect on models:**
- **Scorecard:** Handles this correctly — its features are the same 14 count-based ones. The score is based on what's actually provided.
- **XGBoost:** Fails — it was trained on fully-populated 122-feature rows. Median-filled values for 108 features violate the feature interactions the model learned. Even after switching from KNN-imputed to median-imputed, XGBoost inverts predictions (low-risk → P=0.999, high-risk → P=0.64).

**Rule:** XGBoost (and tree models trained on dense features) should NEVER be used for inference on sparse/partial inputs. Use the scorecard for partial-input workflows. Only use XGBoost when most features are populated.

---

## 13. Inference optimization: `predict_all()` pattern to deduplicate pipeline runs

**Problem:** If `predict_proba()`, `predict_credit_score()`, and `explain()` are separate methods that each call the feature pipeline internally, a single API request runs the pipeline N times. With KNNImputer, each pipeline run is O(n_train × n_features) ≈ 300 ms.

**Pattern:** Add a `predict_all()` method that runs the pipeline once and computes all outputs from the same transformed DataFrame:

```python
def predict_all(self, X_raw) -> dict:
    df = self._get_df(X_raw)          # KNN runs exactly once
    woe_per_feature = {col: binner.transform(df[col]) for col, binner in ...}
    proba = self.lr_.predict_proba(woe_matrix)[:, 1]
    scores = sum(contributions)
    breakdown = [per_feature_details...]
    return {"proba": proba, "credit_score": scores, "breakdown": breakdown}
```

**Result:** 3221 ms → 288 ms (11× speedup). This pattern applies to any multi-output inference pipeline where computing outputs from the same transformed representation is cheap.

**Rule:** Any inference endpoint that computes multiple outputs from one model should go through a single-pass method. Never expose separate `predict_X()` methods that each re-run a shared expensive step.

---

## 14. Prometheus histogram + Grafana panel type — know the difference between raw and pre-bucketed data

**Core distinction:**
- Grafana `"type": "histogram"` — designed for **raw data**. Grafana bins the data itself. Correct for: `[0.12, 0.34, 0.78, ...]` (list of raw values).
- Prometheus `Histogram` metric — data is **already pre-bucketed** server-side with `le` labels. Grafana should NOT re-bucket it.

**Double-bucketing failure:** When you attach a Prometheus pre-bucketed histogram (`_bucket` metric with `le` labels) to a Grafana `"histogram"` panel, Grafana sees count values like `2, 2, 3` and runs them through its internal bucketer. X-axis becomes count ranges `[0–1], [1–2], [2–3]` instead of probability values `[0.1, 0.2, ..., 1.0]`.

**Correct panel types for Prometheus histograms:**
- `"barchart"` + Reduce transformation: shows one bar per `le` value (CDF shape). Best for low-traffic systems where you want a static snapshot.
- `"heatmap"` + "Time series buckets": shows how the distribution changes over time. Best for production traffic monitoring.
- `"timeseries"` with `histogram_quantile()`: shows P50/P90/P99 lines over time. Best for SLA monitoring.

**Never use `"type": "histogram"` for Prometheus `_bucket` metrics.**

**Heatmap is the best panel type for P(default) distribution in production MLOps:**
- X=time, Y=probability bucket, Color=density → drift is visible at a glance
- A horizontal color band that shifts upward over weeks means the model is outputting higher risk scores than before (potential data drift or population shift)
- `calculate: false` is the critical flag — without it, Grafana re-buckets already-bucketed data
- `filterValues.le: 1e-9` hides empty cells, making rare-bucket colors more salient
- `scheme: "YlOrRd"` (yellow→orange→red) is intuitive: brighter = more predictions clustered there

**The correct full configuration for a Prometheus histogram heatmap:**
```json
{
  "type": "heatmap",
  "targets": [{
    "expr": "sum(increase(prediction_default_prob_bucket[$__rate_interval])) by (le)",
    "legendFormat": "{{le}}"
  }],
  "options": {
    "calculate": false,
    "color": {"scheme": "YlOrRd", "mode": "scheme", "scale": "exponential", "exponent": 0.5},
    "filterValues": {"le": 1e-9},
    "yAxis": {"label": "P(default)", "decimals": 1}
  }
}
```

---

## 16. NannyML CBPE — reference data must contain model predictions, not just features

**Context:** Integrating NannyML for performance estimation without ground truth labels.

**Rule:** NannyML's `CBPE.fit()` requires three columns on the reference dataset: `y_true` (actual labels), `y_pred_proba` (model probability), and `y_pred` (binary prediction). A feature-only CSV (like `reference.csv`) will cause a `KeyError` at fit time.

**Why:** CBPE fits an internal calibration curve that maps predicted probabilities to true positive rates. Without `y_true` on the reference data, it has no ground truth to calibrate against.

**Implementation pattern for this project:**
1. Use `test_data.csv` as the NannyML reference (it has `label` column).
2. Run the local scorecard model once on those 4,000 rows to generate `y_pred_proba` / `y_pred`.
3. Cache as `monitoring/nannyml_reference.csv`. Delete this file whenever the model version is promoted — stale reference predictions cause miscalibrated CBPE estimates.

**The calibration consistency requirement:**
CBPE's probability calibration is only valid if the reference predictions and production predictions come from the **same model version**. If you promote a new model but forget to delete `nannyml_reference.csv`, CBPE will estimate AUC using a calibration curve fitted on the old model's probabilities — and the estimate will be silently wrong.

---

## 17. NannyML vs Evidently — when to use which

**Core distinction:**

| | Evidently | NannyML |
|---|---|---|
| Detects feature drift | ✅ | ✅ |
| Detects data quality issues | ✅ | partial |
| Estimates performance without labels | ❌ | ✅ CBPE |
| Requires ground truth | for performance metrics | only for reference fit |
| Best for | per-request HTML reports | weekly batch monitoring |
| Output | HTML reports | Prometheus + HTML |

**Rule for this project:**
- **Evidently** → use for ad-hoc drift reports triggered by the data team; output is a standalone HTML file suitable for sharing.
- **NannyML** → use for weekly automated monitoring; output feeds into Grafana via Pushgateway for trend visibility.

**Why NannyML is uniquely valuable for credit scoring:**
Ground truth labels (did the customer default?) arrive 3–12 months after the loan decision. Any monitoring system that requires labels cannot give an early warning. CBPE provides a statistically principled AUC estimate from probabilities alone — the earliest possible signal that the model is degrading, before a single confirmed default arrives.

**CBPE's one hard requirement:** The model's probabilities must be well-calibrated. WOE logistic regression (our scorecard) is naturally well-calibrated. XGBoost and tree ensembles are typically not — they need isotonic or Platt scaling before CBPE will give reliable estimates.

---

## 18. Batch monitoring jobs need Pushgateway, not a scrape endpoint

**Problem:** NannyML runs as a one-shot Docker Compose job (`run --rm`). Prometheus scrapes running HTTP endpoints. A container that exits cannot serve `/metrics`.

**Solution — Pushgateway pattern:**
```
Batch job → push_to_gateway(url, job="nannyml_monitor", registry=reg)
           ↑
Prometheus scrapes pushgateway with honor_labels=true
           ↓
Grafana queries nannyml_estimated_auc{job="nannyml_monitor"}
```

**`honor_labels: true` in prometheus.yml is not optional.** Without it, Prometheus overwrites the pushed `job` label with `"pushgateway"`, and all NannyML Grafana panels stop matching.

**Stale metric risk:** Pushgateway never expires values. Add a `nannyml_last_run_timestamp_seconds` gauge to every push. In Grafana, show this as "Last NannyML Run" — if it's > 7 days old, the team knows to trigger a manual run.

---

## 15. GridSearchCV `make_scorer` returns NaN in sklearn 1.8

**Bug:** Custom `make_scorer(roc_auc_score, needs_proba=True)` returns `cv_gini=nan` for all hyperparameter combinations in sklearn 1.8.

**Root cause:** sklearn 1.8 changed internal validation in `make_scorer`. The custom scorer silently fails (returns NaN) when the estimator's `predict_proba` output shape doesn't match internal expectations — likely related to WOE-encoded features producing outputs that trip a new validation check.

**Fix:** Use the built-in string scorer instead of a custom scorer object:

```python
# Wrong (NaN in sklearn 1.8)
scorer = make_scorer(roc_auc_score, needs_proba=True)
gs = GridSearchCV(lr, param_grid, scoring=scorer, cv=5)

# Correct
gs = GridSearchCV(lr, param_grid, scoring='roc_auc', cv=5)
cv_gini = 2 * gs.best_score_ - 1   # convert AUC to Gini
```

**Lesson:** Prefer built-in sklearn scorer strings over `make_scorer` when the built-in exists. They are version-stable and tested. Custom scorers can silently fail on version upgrades.

---

## 19. NannyML library version contracts — always inspect `to_df().columns` before coding

**Context:** Integrating NannyML v0.13 CBPE into the monitoring stack.

**Problem:** The NannyML documentation (and training data) described CBPE result columns using the sub-key `'estimated'`. The installed v0.13 library uses `'value'` instead. The mismatch was silent: `_extract_scalar()` returned `None`, which then failed only when the `None` was passed to an f-string formatter:
```
TypeError: unsupported format string passed to NoneType.__format__
```
The root cause was one level deeper than the visible error.

**Rule:** Never write column-extraction code for a new monitoring library without first running `result.to_df().columns.tolist()` interactively against the installed version. Documentation may describe a different version or a planned API; the running library is authoritative.

**Diagnostic pattern:**
```bash
docker compose run --rm nannyml_monitor python3 -c "
import nannyml as nml, pandas as pd
# ... minimal fit/estimate ...
print(nml.__version__)
print(result.to_df().columns.tolist())
"
```

**NannyML v0.13 column layout (verified):**
- **CBPE** (`CBPE.estimate().to_df()`): 2-level MultiIndex `(metric, sub)` — sub values include `'value'`, `'alert'`, `'upper_confidence_boundary'`, `'lower_confidence_boundary'`
- **UnivariateDrift** (`UnivariateDriftCalculator.calculate().to_df()`): 3-level MultiIndex `(feature, method, sub)` — e.g. `('NUMBER_OF_LOANS', 'jensen_shannon', 'alert')`
- **MultivariateDrift** (`DataReconstructionDriftCalculator.calculate().to_df()`): 2-level MultiIndex similar to CBPE

**The broader lesson:** Any library that returns structured DataFrames with MultiIndex columns (NannyML, Evidently, some sklearn CV results) may change column naming between minor versions. Treat column extraction code as version-pinned and add a version check comment next to any hardcoded column name.

**Related:** [[debug_workflows#21]] — full code for the two helpers (`_extract_scalar`, `_count_alerts`, `_drifted_features`) that correctly handle both 2-level and 3-level MultiIndex layouts.

---

## 20. Pushgateway is ephemeral by default — batch-job metrics need persistence + a writable volume

**Context:** After a reboot (out-of-disk restart), the entire NannyML row in Grafana showed "No data" despite the monitor having run successfully before.

**Root cause (two stacked bugs):**
1. **Pushgateway holds metrics in memory only by default.** A container restart wipes everything pushed to it. Because the NannyML monitor is a one-shot `run --rm` job, nothing re-pushes after a restart — the gateway stays empty until the next manual run. Prometheus then scrapes nothing, and Grafana correctly shows "No data."
2. **Enabling persistence is necessary but not sufficient.** Adding `--persistence.file=/data/pushgateway.store` + a named volume still failed silently with `permission denied`, because the `prom/pushgateway` image runs as `nobody` (UID 65534) while a fresh named volume is root-owned. The process could not write the store file. `user: root` on the service fixed it.

**The deeper lesson — distinguish "correct empty" from "broken":**
A dashboard showing "No data" is ambiguous. It can mean (a) the query is wrong, (b) the metric name changed, or (c) there genuinely is no data. Here it was (c) twice over. The debugging discipline that paid off was walking the metric chain backwards — Grafana panel → Prometheus query → Pushgateway `/metrics` → did the job ever push? — instead of assuming the dashboard JSON was broken. The panels were faithfully reporting reality.

**The architectural lesson — ephemeral receivers are a reboot away from data loss:**
Any component that *accumulates* state pushed from elsewhere (Pushgateway, in-memory caches, unpersisted queues) must have that state on durable storage if the data matters across restarts. For Pushgateway specifically:
- `--persistence.file` on a **writable** volume is mandatory, not optional, for production batch-job monitoring.
- Always verify writability empirically: the store file must appear after `persistence.interval`, and the value must survive a deliberate `docker compose restart`. A misconfigured volume passes config validation but silently drops data — the worst kind of failure because the dashboard looks fine until the next reboot.

**Rule:** Persistence config you haven't watched survive a restart is not persistence — it's a hypothesis. Validate it by restarting and re-querying.

**Related:** [[debug_workflows#22]] — full diagnosis, the `permission denied` log signature, and the restart-survival validation procedure. [[debug_workflows#20]] — the original Pushgateway + `honor_labels` wiring.
