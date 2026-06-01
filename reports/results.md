# Results Summary

All models trained on the same dataset: 16,000 train / 4,000 test (stratified 80/20 split, SHA256: `cac9de3c`). Default rate: 18.2%.

---

## Model Comparison

| Model | Alias | AUC | Gini | KS | PR-AUC | Precision | Recall |
|-------|-------|-----|------|----|--------|-----------|--------|
| XGBoost | champion | 0.8223 | 0.6446 | 0.5006 | 0.6897 | — | — |
| Logistic Regression + SMOTE | challenger | 0.8229 | 0.6459 | 0.5089 | 0.6428 | — | — |
| Scorecard WOE-LR | scorecard | 0.8102 | 0.6205 | — | — | — | — |

> Scorecard v7 (run `2c9e9962`) trained with `scoring='roc_auc'` in GridSearchCV (C=0.1, l1, saga). See DagsHub MLflow for live figures:
> https://dagshub.com/NguyenDucAnforwork/credit-mlops.mlflow

### Key observations

- **LR slightly edges out XGBoost on AUC** (0.8229 vs 0.8223) — the difference is within noise. LR's edge comes from SMOTE oversampling making the decision boundary more robust.
- **XGBoost has higher PR-AUC** (0.6897 vs 0.6428) meaning better precision-recall tradeoff — important for imbalanced credit data where false negatives are costly.
- **Scorecard AUC gap (0.8102 vs 0.8223)** is expected: WOE binning is a lossy transformation that trades some discriminatory power for full interpretability. Scorecard v7 fixed a scorer bug (custom `make_scorer` returned `nan` CV scores → GridSearchCV defaulted to C=0.01 over-regularization → AUC dropped to 0.79). Using `scoring='roc_auc'` resolved this.

---

## Scorecard Feature Importance (IV Table)

Information Value (IV) measures each feature's discriminatory power.
IV > 0.3 is "strong"; IV > 0.1 is "medium"; IV < 0.02 is "useless".

| Rank | Feature | IV | Category |
|------|---------|-----|----------|
| 1 | NUM_NEW_LOAN_TAKEN_PCA_1 | 1.397 | Suspicious (very strong) |
| 2 | NUM_NEW_LOAN_TAKEN_PCA_2 | 1.210 | Suspicious (very strong) |
| 3 | NUMBER_OF_LOANS_NON_BANK | 0.785 | Strong |
| 4 | NUMBER_OF_LOANS | 0.756 | Strong |
| 5 | NUMBER_OF_RELATIONSHIP_NON_BANK | 0.743 | Strong |
| 6 | NUMBER_OF_RELATIONSHIP_BANK | 0.594 | Strong |
| 7 | SHORT_TERM_COUNT_BANK | 0.551 | Strong |
| 8 | ENQUIRIES_PCA_4 | 0.536 | Strong |
| 9 | ENQUIRIES_PCA_3 | 0.523 | Strong |
| 10 | NUMBER_OF_CREDIT_CARDS | 0.448 | Strong |
| 11 | ENQUIRIES_PCA_1 | 0.437 | Strong |
| 12 | ENQUIRIES_PCA_5 | 0.429 | Strong |
| 13 | SHORT_TERM_COUNT_NON_BANK | 0.427 | Strong |
| 14 | OUTSTANDING_BAL_PCA_2 | 0.399 | Strong |
| 15 | ENQUIRIES_PCA_2 | 0.391 | Strong |
| 16 | NUMBER_OF_CREDIT_CARDS_BANK | 0.384 | Strong |
| 17 | OUTSTANDING_BAL_PCA_5 | 0.270 | Medium |
| 18 | OUTSTANDING_BAL_PCA_3 | 0.218 | Medium |

**All 18 features are above the IV=0.02 threshold** — none were filtered out.

**Top predictors by category:**
- **New loan activity** (NUM_NEW_LOAN_TAKEN_PCA): IV>1.0 — strongest signal. Customers who recently took many new loans are high risk.
- **Loan portfolio size** (NUMBER_OF_LOANS, NUMBER_OF_RELATIONSHIP): IV~0.5-0.8 — breadth of credit relationships matters.
- **Enquiry patterns** (ENQUIRIES_PCA): IV~0.4-0.5 — frequent credit checks signal financial stress.
- **Outstanding balances** (OUTSTANDING_BAL_PCA): IV~0.2-0.4 — balance trends are weaker but still useful.

---

## Scorecard Interpretability Example

When using `MLFLOW_MODEL_ALIAS=scorecard`, the `/predict` endpoint returns a full breakdown per customer:

```json
{
  "default_probability": 0.31,
  "credit_score": 582,
  "risk_band": "Fair",
  "decision": "manual_review",
  "scorecard_score": 582.4,
  "scorecard_breakdown": [
    {
      "feature": "NUM_NEW_LOAN_TAKEN_PCA_1",
      "raw_value": 1.23,
      "bin": "(0.8, +inf]",
      "woe": -0.94,
      "score_contribution": -68.3,
      "iv": 1.40
    },
    {
      "feature": "NUMBER_OF_LOANS_NON_BANK",
      "raw_value": 8.0,
      "bin": "(6.0, +inf]",
      "woe": -0.71,
      "score_contribution": -51.2,
      "iv": 0.79
    },
    ...
  ]
}
```

**How to read:** Negative `score_contribution` = feature is pulling the score DOWN (higher risk). Positive = pulling UP (lower risk). Regulators and loan officers can see exactly which factors drove the decision.

---

## Decision Thresholds

| default_probability | decision | typical action |
|---------------------|----------|----------------|
| < 0.45 | **approve** | Auto-approve loan |
| 0.45 – 0.69 | **manual_review** | Escalate to loan officer |
| ≥ 0.70 | **reject** | Auto-reject loan |

### Credit score bands

| Score range | Risk band | Typical rate |
|-------------|-----------|--------------|
| 750 – 850 | Excellent | < 5% default |
| 670 – 749 | Good | 5–15% |
| 580 – 669 | Fair | 15–30% |
| 440 – 579 | Poor | 30–50% |
| 300 – 439 | Very Poor | > 50% |

---

## Infrastructure

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| api | credit-mlops-api (Python 3.12) | 8000 | FastAPI inference |
| postgres | postgres:16-alpine | 5432 | Prediction audit log |
| redis | redis:7-alpine | 6379 | Rate limiting (100 req/min) |
| prometheus | prom/prometheus:v2.55.0 | 9090 | Metrics collection |
| alertmanager | prom/alertmanager:v0.27.0 | 9093 | Alert routing |
| grafana | grafana/grafana:11.3.0 | 3000 | Dashboards |

**Rate limiting:** 100 requests/minute per IP via Redis sliding window.  
**Audit log:** Every prediction stored in PostgreSQL `predictions` table with features, probabilities, decision, latency.  
**Reload interval:** API re-checks MLflow champion alias every 60 seconds (zero-downtime model updates).

---

## Pipeline Performance

| Step | Description | Time |
|------|-------------|------|
| data_prep | SHA256 hash + 80/20 split (16K rows) | ~2s |
| feature_fit | KNNImputer(k=20) on 16K×122 | ~8-10 min |
| train_lr | LR + SMOTE + StandardScaler | ~2 min |
| train_xgb | XGBoost 150 estimators | ~1 min |
| train_scorecard | WOE bins + GridSearchCV 5-fold (60 models) | ~3 min |
| register | MLflow alias promotion + DagsHub upload | ~2 min |

**Total pipeline runtime:** ~15-20 minutes (dominated by KNN imputation).

---

## Test Coverage

```
62 tests  |  0 failures
├── test_api.py        (8)   — endpoint integration
├── test_chaos.py      (7)   — fault injection (registry down, 503, 429)
├── test_contract.py   (9)   — Pydantic schema validation
├── test_decision.py   (15)  — threshold + score band logic
├── test_evaluate.py   (7)   — metric computation
├── test_features.py   (6)   — pipeline transform correctness
└── test_scorecard.py  (8)   — WOE binning + credit score formula
```
