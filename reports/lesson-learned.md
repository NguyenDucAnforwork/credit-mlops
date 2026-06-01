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
