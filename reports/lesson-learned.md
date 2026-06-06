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
