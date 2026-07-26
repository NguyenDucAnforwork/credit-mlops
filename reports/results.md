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
76 tests  |  0 failures
├── test_api.py        (8)   — endpoint integration
├── test_chaos.py      (7)   — fault injection (registry down, 503, 429)
├── test_contract.py   (9)   — Pydantic schema validation
├── test_decision.py   (15)  — threshold + score band logic
├── test_evaluate.py   (7)   — metric computation
├── test_features.py   (6)   — pipeline transform correctness
└── test_scorecard.py  (8)   — WOE binning + credit score formula
```

---

## Phase 0 Remote Baseline, 2026-07-26

Measured on VM `lfm` in `/home/ducan/credit-mlops-codex`.

| Check | Result | Evidence |
|-------|--------|----------|
| SSH preflight | pass | `docs/remote_environment.md` |
| VM resources | 4 vCPU, 15 GiB RAM, 66 GiB free disk, no GPU | `docs/remote_environment.md` |
| Dependency sync | pass, 168 packages installed with `uv sync --frozen --all-extras --dev` | `docs/experiments.md` |
| Baseline data prep | version `cac9de3c`, 16,000 train rows, 4,000 test rows | `docs/evidence/baseline_processed_files_20260726.txt` |
| Original pytest suite | 76 passed in 7.42 seconds; wrapper runtime 9 seconds | `docs/evidence/baseline_pytest_20260726.txt` |
| Docker preflight | blocked: `ducan` cannot access `/var/run/docker.sock`; `docker compose` unavailable | `docs/evidence/docker_permission_20260726.txt` |
| GCP access from VM | blocked: `ACCESS_TOKEN_SCOPE_INSUFFICIENT` | `docs/remote_environment.md` |

Docker/API smoke tests were not run because Docker access requires an approved VM permission/configuration change.

---

## Phase 1 ETL Foundation, 2026-07-26

Measured on VM `lfm` in `/home/ducan/credit-mlops-codex`.

| Check | Result | Evidence |
|-------|--------|----------|
| Fixture ETL tests | 10 passed in 0.27 seconds | remote pytest output |
| Full suite after ETL foundation | 86 passed in 12.79 seconds; wrapper runtime 15 seconds | `docs/evidence/phase1_etl_pytest_20260726.txt` |
| Incremental fixture first run | exactly 1,000 inserts and exactly 100 duplicates | `docs/evidence/phase1_incremental_fixture_20260726.json` |
| Incremental fixture identical rerun | 0 inserts | `docs/evidence/phase1_incremental_fixture_20260726.json` |

Full Hugging Face ingestion, row counts, checksums, ETL runtime, and peak RAM are not measured yet.

### HF Metadata

| Field | Value |
|-------|-------|
| Dataset | `vduydong/vietnam-real-estates` |
| Revision | `a9a66ffa985edcf76b4be59ae2c6f5b1db889c38` |
| Last modified | `2026-04-08T06:51:21.000Z` |
| Parquet shard count | 5 |
| Metadata evidence | `reports/generated/hf_vietnam_real_estates_metadata_20260726.json` |
| Full suite after metadata module | 89 passed in 7.36 seconds; wrapper runtime 9 seconds |

### HF Shard Footer Manifest

| Field | Value |
|-------|-------|
| Total rows from Parquet footers | 1,000,000 |
| Rows per shard | 200,000 |
| Columns per shard | 19 |
| Total remote object size | 469,122,864 bytes |
| Shard count | 5 |
| ETags | captured in `reports/generated/hf_vietnam_real_estates_shard_manifest_20260726.json` |
| Full SHA256 | not measured |
| Footer summary evidence | `docs/evidence/hf_shard_footer_summary_20260726.json` |
| Full suite after shard manifest module | 93 passed in 7.31 seconds; wrapper runtime 9 seconds |

### HF Raw Snapshot

| Field | Value |
|-------|-------|
| Remote raw path | `data/raw/vietnam-real-estates/a9a66ffa985edcf76b4be59ae2c6f5b1db889c38` |
| Local raw data copied | no |
| Shards downloaded | 5 |
| Total rows from footers | 1,000,000 |
| Total size | 469,122,864 bytes |
| VM disk use | 448M |
| First download runtime | 74 seconds |
| Verified rerun runtime | 12 seconds |
| Full SHA256 | captured for every shard in `reports/generated/hf_vietnam_real_estates_snapshot_manifest_20260726.json` |
| Full suite after snapshot downloader | 96 passed in 7.35 seconds; wrapper runtime 9 seconds |

### HF Silver/Gold ETL

| Field | Value |
|-------|-------|
| Raw rows | 1,000,000 |
| Silver rows | 893,830 |
| Gold MVP rows | 638,123 |
| Hà Nội gold rows | 311,266 |
| Hồ Chí Minh gold rows | 326,857 |
| Quarantine rows | 106,170 |
| Duplicate rows | 8 |
| Quarantine reasons | `invalid_price=78,418`, `missing_district=26,476`, `invalid_published_at=1,267`, `duplicate_listing_id=8`, `invalid_area=1` |
| Coordinate status | source lacks `latitude` and `longitude`; no coordinates fabricated |
| ETL runtime | 48 seconds |
| Layer disk use | 407M silver, 287M gold, 52M quarantine |
| Evidence | `docs/evidence/hf_etl_summary_20260726.json`, `docs/evidence/hf_etl_profile_20260726.json` |
| Full suite after ETL | 99 passed in 7.38 seconds; wrapper runtime 9 seconds |

### HF Data Contracts

| Field | Value |
|-------|-------|
| Contract status | `pass_with_blockers` |
| Core checks | 9 passed |
| Blocker checks | 1 failed: `coordinate_source_columns_present` |
| MVP row threshold | pass, 638,123 gold rows >= 500,000 |
| Coordinate evidence | source schema lacks `latitude` and `longitude`; `coordinate_status=missing_source_columns` |
| Contract runtime | 16 seconds |
| Evidence | `docs/evidence/hf_contract_report_20260726.json` |
| Full suite after contracts | 102 passed in 7.98 seconds; wrapper runtime 10 seconds |

### AVM Baseline Experiment 1

| Field | Value |
|-------|-------|
| Split | June-October 2025 train, November 2025 validation, December 2025 test |
| Train rows | 429,682 |
| Validation rows | 100,105 |
| Test rows | 108,336 |
| Best simple baseline | `district_property_type_median_price_per_m2` |
| Test MdAPE | 22.85% |
| Test RMSLE | 0.4426 |
| Test MAE | 18.52B VND |
| Test median absolute error | 1.85B VND |
| Test R2 | 0.387 |
| Within 10% | 23.42% |
| Within 20% | 44.42% |
| Runtime | 2 seconds |
| Evidence | `docs/evidence/avm_baseline_metrics_20260726.json` |
| Full suite after baseline | 105 passed in 7.57 seconds; wrapper runtime 9 seconds |

### AVM Experiment 2: Non-GIS Tabular HGB

| Field | Value |
|-------|-------|
| Model | `hist_gradient_boosting_log_price_per_m2` |
| Target | `log(price_per_m2)` |
| Split | June-October 2025 train, November 2025 validation, December 2025 test |
| Train rows | 429,682 |
| Validation rows | 100,105 |
| Test rows | 108,336 |
| Test MdAPE | 19.16% |
| Test RMSLE | 0.3850 |
| Test MAE | 18.66B VND |
| Test median absolute error | 1.58B VND |
| Test R2 | 0.313 |
| Within 10% | 27.67% |
| Within 20% | 51.79% |
| Relative MdAPE improvement over strongest simple baseline | 16.14% |
| Runtime | 9 seconds |
| Evidence | `docs/evidence/avm_tabular_hgb_metrics_20260726.json` |
| Full suite after tabular AVM | 107 passed in 7.69 seconds; wrapper runtime 9 seconds |

### AVM Experiment 3: Residual Intervals

| Field | Value |
|-------|-------|
| Interval method | validation log-residual q10/q90 |
| Target coverage | 80% |
| Empirical test coverage | 79.61% |
| Median interval-width ratio | 83.79% |
| p90 interval-width ratio | 83.79% |
| High-confidence share | 0% |
| Low-confidence share | 100% |
| Coverage decision | pass |
| Width decision | fail, target <=50% |
| Runtime | 9 seconds |
| Evidence | `docs/evidence/avm_tabular_hgb_intervals_20260726.json` |
| Full suite after intervals | 108 passed in 7.73 seconds; wrapper runtime 10 seconds |

### AVM Experiment 4: Cohort Residual Intervals

| Field | Value |
|-------|-------|
| Interval method | validation log-residual q10/q90 by province/property-type cohort, with global fallback |
| Target coverage | 80% |
| Qualified validation cohorts | 6 |
| Test rows using cohort band | 107,356 |
| Test rows using global fallback | 980 |
| Global fallback share | 0.90% |
| Empirical test coverage | 79.29% |
| Median interval-width ratio | 82.32% |
| p90 interval-width ratio | 107.48% |
| High-confidence share | 0% |
| Medium-confidence share | 21.63% |
| Low-confidence share | 78.37% |
| Coverage decision | pass |
| Width decision | fail, target <=50% |
| Runtime | 9 seconds |
| Evidence | `docs/evidence/avm_tabular_hgb_cohort_intervals_20260726.json` |
| Verification before experiment | 7 AVM tests passed in 0.90 seconds; 109 total tests passed in 7.81 seconds |
| Final verification after docs/evidence | 109 tests passed in 9.44 seconds; wrapper runtime 12 seconds |

### AVM Experiment 5: Direct Quantile Intervals

| Field | Value |
|-------|-------|
| Interval method | HGB q10/q90 quantile models for log(price/m2) |
| Target coverage | 80% |
| Validation empirical coverage | 79.64% |
| Validation median interval-width ratio | 77.74% |
| Empirical test coverage | 78.67% |
| Median interval-width ratio | 76.99% |
| p90 interval-width ratio | 134.16% |
| High-confidence share | 14.33% |
| Medium-confidence share | 39.30% |
| Low-confidence share | 46.37% |
| Coverage decision | pass |
| Width decision | fail, target <=50% |
| Runtime | 30 seconds |
| Evidence | `docs/evidence/avm_tabular_hgb_quantile_intervals_20260726.json` |
| Verification before experiment | 8 AVM tests passed in 1.13 seconds; 110 total tests passed in 8.02 seconds |
| Final verification after docs/evidence | 110 tests passed in 7.98 seconds; wrapper runtime 10 seconds |

### Comparable Fallback Benchmark

| Field | Value |
|-------|-------|
| Method | non-GIS pandas comparable fallback |
| Query sample | 1,000 December 2025 gold listings, `random_state=42` |
| Leakage guard | candidates must be published before subject listing time |
| Max results | 10 |
| Area tolerance | ±25% |
| Valid-request error rate | 0% |
| Median latency | 8.65 ms |
| p95 latency | 14.88 ms |
| Max latency | 18.64 ms |
| Comparable count | median 10, mean 10, min 10, max 10 |
| Support share | high 100%, medium 0%, low 0% |
| Distance status | `not_available_missing_coordinates` |
| PostGIS criterion status | blocked: missing coordinates and PostGIS |
| Runtime | 13 seconds |
| Evidence | `docs/evidence/property_comparables_fallback_benchmark_20260726.json` |
| Verification before benchmark | 2 comparable tests passed in 0.65 seconds; 112 total tests passed in 8.13 seconds |
| Final verification after docs/evidence | 112 tests passed in 8.12 seconds; wrapper runtime 10 seconds |

### Property API Scaffold Smoke

| Field | Value |
|-------|-------|
| Endpoints | `POST /v1/avm/predict`, `GET /v1/comparables`, `POST /v1/lending/decision` |
| Execution | VM FastAPI TestClient with `PROPERTY_GOLD_PATH` pointing to real gold parquet |
| `/v1/comparables` | status 200, 10 comparables, 2,624.48 ms cold index-build latency |
| `/v1/avm/predict` | status 200, estimated value 4.95B VND, lower 4.245B VND, upper 5.02B VND, interval-width ratio 15.66%, high confidence, 13.13 ms after index build |
| `/v1/lending/decision` | status 200, conservative LTV 0.75, decision `approve`, 2.63 ms |
| Boundary tests | exact conservative LTV 0.75 approves; 0.7501 manual review; 0.85 manual review; 0.8501 rejects |
| Runtime | 6 seconds |
| Evidence | `docs/evidence/property_api_smoke_20260726.json` |
| Verification before smoke | 14 focused API tests passed in 1.98 seconds; 118 total tests passed in 8.16 seconds |
| Final verification after docs/evidence | 118 tests passed in 8.16 seconds; wrapper runtime 10 seconds |
| Load criterion status | not measured; Docker/service runtime remains blocked |

### AVM Promotion Gate Dry-Run

| Field | Value |
|-------|-------|
| Model name | `property_avm` |
| Candidate version | `hist_gradient_boosting_log_price_per_m2` |
| Registry action | dry-run only, no MLflow mutation |
| Gate decision | `reject` |
| Temporal MdAPE improvement | pass, 16.14% relative improvement vs strongest simple baseline |
| Interval coverage | pass, 78.67% within 75%-85% |
| Median interval-width ratio | fail, 76.99% vs <=50% target |
| Spatial holdout regression | fail, missing evidence |
| Major cohort regression | fail, missing evidence |
| Warm API p95 | fail, missing evidence |
| Alias update plan | `no_op`, reason `promotion_gate_rejected` |
| Rollback plan | `no_op`, reason `missing_alias_history` |
| Runtime | 1 second |
| Evidence | `docs/evidence/property_avm_promotion_gate_20260726.json` |
| Verification before gate | 8 lifecycle tests passed in 0.65 seconds; 126 total tests passed in 8.20 seconds |
| Final verification after docs/evidence | 126 tests passed in 8.27 seconds; wrapper runtime 10 seconds |
| Test-count criterion | pass, >=125 total tests |

### Synthetic Property Monitoring Drift

| Field | Value |
|-------|-------|
| Reference sample | 5,000 pre-November gold listings, `random_state=42` |
| Synthetic shifted features | `area_m2`, `price_per_m2`, `interval_width_ratio`, `district_missingness`, `confidence` |
| Monitoring status | `alert` |
| Alert count | 4 |
| Alerting features | `area_m2`, `price_per_m2`, `interval_width_ratio`, `missing_feature_share` |
| Area mean shift | 35.00% |
| Price/m2 mean shift | 35.00% |
| Interval-width mean shift | 0.25 |
| Missing-feature share shift | 0.0833 |
| Runtime | 1 second |
| Evidence | `docs/evidence/property_monitoring_synthetic_drift_20260726.json` |
| Verification before drift run | 3 monitoring tests passed in 0.63 seconds; 129 total tests passed in 8.26 seconds |
| Final verification after docs/evidence | 129 tests passed in 8.15 seconds; wrapper runtime 10 seconds |

### Warm Property API TestClient Load Benchmark

| Field | Value |
|-------|-------|
| Execution scope | VM FastAPI TestClient threads, not Docker/uvicorn service |
| Requests | 1,000 AVM requests and 1,000 lending requests |
| Concurrency | 10 |
| AVM status codes | `[200]` |
| AVM valid-request error rate | 0% |
| AVM p95 latency | 176.43 ms |
| AVM p99 latency | 249.01 ms |
| AVM throughput | 74.51 rps |
| Lending status codes | `[200]` |
| Lending valid-request error rate | 0% |
| Lending p95 latency | 64.71 ms |
| Lending p99 latency | 94.07 ms |
| Lending throughput | 220.49 rps |
| Runtime | 23 seconds |
| Evidence | `docs/evidence/property_api_load_benchmark_20260726.json` |
| Final verification after benchmark | 129 tests passed in 8.20 seconds; wrapper runtime 10 seconds |
| Criterion status | passes p95/error targets only for in-process TestClient scope; service and Cloud Run criteria remain unmeasured |

### Warm Property API Uvicorn HTTP Benchmark

| Field | Value |
|-------|-------|
| Execution scope | VM uvicorn HTTP service, non-Docker |
| Requests | 1,000 AVM requests and 1,000 lending requests |
| Concurrency | 10 |
| Warmup | `/v1/comparables` status 200, 2,640.39 ms cold index-build latency |
| AVM status codes | `[200]` |
| AVM valid-request error rate | 0% |
| AVM p95 latency | 140.84 ms |
| AVM p99 latency | 173.39 ms |
| AVM max latency | 242.26 ms |
| AVM throughput | 98.38 rps |
| Lending status codes | `[200]` |
| Lending valid-request error rate | 0% |
| Lending p95 latency | 24.21 ms |
| Lending p99 latency | 224.35 ms |
| Lending max latency | 354.39 ms |
| Lending throughput | 649.09 rps |
| Runtime | 19 seconds |
| Evidence | `docs/evidence/property_api_http_benchmark_20260726.json` |
| Final verification after benchmark | 129 tests passed in 8.24 seconds; wrapper runtime 10 seconds |
| Criterion status | local-on-VM AVM and lending HTTP service p95/error targets pass for fallback service; Docker and Cloud Run criteria remain unmeasured |

### Delayed-Label AVM Monitoring

| Field | Value |
|-------|-------|
| Prediction source | non-GIS comparable fallback |
| Label sample | 2,000 December 2025 gold listings, `random_state=42` |
| Overall MAE | 5.30B VND |
| Overall median absolute error | 1.4225B VND |
| Overall MdAPE | 16.73% |
| Within 10% | 36.10% |
| Within 20% | 56.55% |
| Median comparable count | 10 |
| Distance availability | 0%, source coordinates absent |
| Cohort groups | district + property type |
| Monitored cohorts | 10 cohorts with at least 50 rows |
| Cohort alerts | 0 above +5 MdAPE points vs overall |
| Worst monitored cohort | Bình Thạnh house, 85 rows, MdAPE 20.56%, +3.83 points vs overall |
| Runtime | 22 seconds |
| Evidence | `docs/evidence/property_delayed_label_monitoring_20260726.json` |
| Final verification after report | 130 tests passed in 8.20 seconds; wrapper runtime 10 seconds |

### Property API Startup Warm-Up

| Field | Value |
|-------|-------|
| Change | Warm non-GIS comparable index during FastAPI lifespan startup |
| Startup latency | 4,849.08 ms |
| First comparable request after startup | 10.99 ms, status 200 |
| Previous comparable cold request | 2,640.39 ms |
| Post-startup comparable latency reduction | 99.58% |
| AVM HTTP p95 after warm-up | 137.81 ms |
| AVM valid-request error rate | 0% |
| Lending HTTP p95 after warm-up | 13.56 ms |
| Lending valid-request error rate | 0% |
| Lingering service process | none; only the `pgrep` check matched itself |
| Evidence | `docs/evidence/property_api_http_warmup_benchmark_20260726.json` |
| Final verification after report | 132 tests passed in 10.73 seconds; wrapper runtime 13 seconds |
| Criterion status | local VM uvicorn service warm path remains under AVM/lending p95 targets; Docker and Cloud Run criteria remain unmeasured |

### HGB Quantile AVM Artifact

| Field | Value |
|-------|-------|
| Artifact path on VM | `artifacts/models/property_avm_hgb_quantile_20260726.joblib` |
| Artifact committed locally | no |
| Artifact size | 2,480,557 bytes / 2.37 MB |
| Artifact size criterion | pass, <=150 MB |
| Artifact load latency | 87.13 ms |
| Single prediction latency | 21.32 ms |
| Train/evaluation runtime | 26.40 seconds |
| Script runtime including same-seed rerun | 55 seconds |
| Same-seed MdAPE delta | 0.0 percentage points |
| December test MdAPE | 19.16% |
| December test RMSLE | 0.3850 |
| Interval coverage | 78.67% |
| Median interval width ratio | 76.99%, still fails <=50% target |
| Artifact-backed AVM HTTP p95 | 136.63 ms, 0% valid-request errors |
| Artifact-backed lending HTTP p95 | 15.53 ms, 0% valid-request errors |
| Evidence | `docs/evidence/avm_hgb_quantile_artifact_20260726.json`; `docs/evidence/property_api_http_artifact_benchmark_20260726.json` |
| Final verification after report | 135 tests passed in 11.15 seconds; wrapper runtime 13 seconds |
| Criterion status | artifact size, same-seed reproducibility, train runtime, and local VM artifact-backed API p95 pass; interval width, spatial holdout, Docker, and Cloud Run remain incomplete |

### Property Intelligence UI

| Field | Value |
|-------|-------|
| UI surface | Streamlit workspace selector with Property Intelligence & Lending mode |
| Location input | province/district plus city reference map marker; exact source coordinates remain unavailable |
| Property inputs | published timestamp, property type, area |
| AVM display | estimate, lower/upper interval, confidence, interval width |
| Comparable display | API comparables table and support metadata |
| Factor display | API top factors list |
| Credit/LTV inputs | credit decision and requested loan amount |
| LTV policy | calls `/v1/lending/decision` using AVM lower interval value |
| Required scenarios | Hà Nội apartment, Hồ Chí Minh City house, low-support manual review |
| UI focused verification | 4 helper tests passed in 0.04 seconds; Streamlit files compiled |
| Evidence | `docs/evidence/phase7_property_ui_pytest_20260726.txt` |
| Final verification after report | 139 tests passed in 11.06 seconds; wrapper runtime 13 seconds |
| Criterion status | UI source/test requirement partially met; live Streamlit/Docker smoke remains blocked by Docker runtime access |
