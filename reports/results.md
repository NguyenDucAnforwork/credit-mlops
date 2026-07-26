# Results Summary

Last updated: 2026-07-26 21:52:20 Asia/Bangkok

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
| Docker preflight | updated: Docker daemon access works; Compose v5.3.1 installed/reused by later smoke | `docs/evidence/phase6_docker_recheck_20260726.txt` |
| GCP access from VM | updated: Service Usage list works; Cloud Resource Manager project describe blocked | `docs/evidence/phase6_gcp_recheck_20260726.txt` |

The initial Docker/API smoke was not run during baseline preflight. Later Phase 6 evidence built UI/API/monitor images and passed plain-container smokes after Docker daemon access was restored.

## Control-Plane Auth Recovery, 2026-07-26

An intermediate SSH/GitHub auth failure was observed earlier in the session, but later VM runs and Git pushes succeeded from the same local repository.

| Check | Result | Evidence |
|-------|--------|----------|
| VM SSH to `lfm` | recovered; later remote coverage and vulnerability targets executed successfully | `docs/evidence/phase7_coverage_runtime_20260726.txt`, `docs/evidence/phase7_pip_audit_runtime_20260726.txt` |
| GitHub push | recovered; feature branch pushed through commit `334be2f` before vulnerability target work | branch `feat/onemount-property-intelligence` |

Current external blockers remain GCP Cloud Resource Manager/IAM/API access and cost-sensitive deployment approval, not SSH, GitHub push, Docker daemon access, or core Compose smoke.

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

### Remote Reproduction Smoke

| Field | Value |
|-------|-------|
| Target | `make remote-reproduce-smoke` |
| Local precheck | secret/path scan over changed tracked and untracked files |
| Remote sync | `scripts/remote/sync_to_vm.sh` |
| Syntax check | `py_compile` for key API, property scripts, and UI modules |
| Ruff lint | 0 errors |
| Focused tests | 61 passed in 3.24 seconds |
| End-to-end runtime | 5 seconds |
| Docker status | skipped in this older smoke; later `make remote-compose-smoke` passes for core Postgres/Redis/API/UI |
| GCP status | skipped in this older smoke; later checks show Service Usage list works but Cloud Resource Manager project describe remains blocked |
| Evidence | `docs/evidence/remote_reproduce_smoke_20260726.txt` |
| Final verification after report | 139 tests passed in 11.11 seconds; wrapper runtime 13 seconds |
| Criterion status | smoke path <=15 minutes passes for non-Docker/non-cloud scope; full CI Docker/Terraform/cloud checks remain incomplete |

### Remote Type-Check Smoke

| Field | Value |
|-------|-------|
| Command | `make remote-type-smoke` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Type checker | `mypy==1.18.2` |
| Scope | `src/property_intelligence`, `api`, and selected property scripts |
| Runtime | 1 second |
| Result | `type_smoke_exit=0`; 0 issues found in 19 source files |
| Final source verification | Ruff passed; 139 warnings-enabled tests passed in 11.16 seconds; wrapper runtime 13 seconds |
| Evidence | `docs/evidence/phase7_type_smoke_stdout_20260726.txt`, `docs/evidence/phase7_type_smoke_runtime_20260726.txt`, `docs/evidence/phase7_type_smoke_tests_20260726.txt`, `docs/evidence/phase7_type_smoke_tests_runtime_20260726.txt` |
| Criterion status | scoped type-check evidence passes for the new production property/API surface |

### GCP Terraform Source Validation

| Field | Value |
|-------|-------|
| Command | `make remote-terraform-validate` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Terraform/provider | Terraform 1.9.8, Google provider 6.50.0 |
| Resource scope | required APIs, Artifact Registry, GCS, BigQuery, Secret Manager placeholder, Cloud Run service, Cloud Run ETL job, Scheduler, IAM service accounts, optional disabled Cloud SQL/PostGIS |
| Runtime | 2 seconds |
| Result | `terraform_validate_exit=0`; `fmt`, `init -backend=false`, and `validate` passed |
| Evidence | `docs/evidence/phase6_terraform_validate_20260726.txt`, `docs/evidence/phase6_terraform_validate_runtime_20260726.txt`, `infra/terraform/.terraform.lock.hcl` |
| Criterion status | Terraform source validation passes; no plan/apply/deployment claimed |

### Docker Context Guard

| Field | Value |
|-------|-------|
| Command | VM source guard captured in evidence |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Source changes | added `.dockerignore`; removed `COPY .env` from API and monitoring Dockerfiles |
| Runtime | 0 seconds |
| Result | `docker_context_guard_exit=0`; `.env`, `data/raw`, and `artifacts/models` exclusions verified; no `COPY .env` remains |
| Docker status | Historical guard run happened before daemon access was refreshed; later daemon and core Compose smokes pass |
| Evidence | `docs/evidence/phase6_docker_context_guard_20260726.txt`, `docs/evidence/phase6_docker_context_guard_runtime_20260726.txt` |
| Criterion status | source packaging guard passes; later image builds and plain-container smokes pass, but Compose service-stack validation remains blocked |

### Container Dependency Alignment

| Field | Value |
|-------|-------|
| Command | UI dependency import plus `pip-audit` for `requirements.txt` and `requirements-monitor.txt` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Runtime | 28 seconds |
| UI dependency import | `UI_DEPS_OK 1.54.0 2.34.2` |
| Main requirements audit | `main_requirements_audit_exit=0`, no known vulnerabilities |
| Monitoring requirements audit | `monitor_requirements_audit_exit=1`, `PYSEC-2024-231` in transitive `lightgbm 4.5.0`, fixed in 4.6.0 |
| Failed fix attempt | `lightgbm==4.6.0` conflicts with available NannyML 0.13.x dependency constraints |
| Evidence | `docs/evidence/phase6_container_dependency_alignment_20260726.txt`, `docs/evidence/phase6_container_dependency_alignment_runtime_20260726.txt` |
| Criterion status | main/UI dependency source aligned; monitoring image vulnerability remains blocked |

### Remote Docker Build And Plain-Container Smoke

| Field | Value |
|-------|-------|
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Docker access | `ducan` is now in group `docker`; Docker client/server 29.1.3 respond |
| Compose status | unavailable during this experiment; later EXP-0038 installs/reuses Compose v5.3.1 and passes core stack smoke |
| Failed probe | `docker build --check` unsupported by the legacy builder; API/UI/monitor checks exited 125 |
| UI image build | passed; image `credit-mlops-ui:codex-20260726`, ID `94df2d30ecb0`, size 837MB, runtime 55s |
| API image build | passed; image `credit-mlops-api:codex-20260726`, ID `b4e4dcd3afd7`, size 3.01GB, runtime 286s |
| Monitoring image build | passed; image `credit-mlops-monitor:codex-20260726`, ID `ab3038d25eeb`, size 3.64GB, runtime 298s |
| API container smoke | passed; `/health` returned `status=ok`, `model_version=fallback_local`; Docker health `healthy`; runtime 21s |
| UI container smoke | passed; `/_stcore/health` returned `ok`; Docker health `healthy`; runtime 19s |
| Monitoring image smoke | passed import check; NannyML 0.13.1, Pandas 2.2.3, LightGBM 4.5.0; runtime 3s |
| Evidence | `docs/evidence/phase6_docker_recheck_20260726.txt`, `docs/evidence/phase6_docker_build_check_20260726.txt`, `docs/evidence/phase6_docker_ui_build_20260726.txt`, `docs/evidence/phase6_docker_api_build_20260726.txt`, `docs/evidence/phase6_docker_monitor_build_20260726.txt`, `docs/evidence/phase6_docker_images_20260726.txt`, `docs/evidence/phase6_docker_api_smoke_20260726.txt`, `docs/evidence/phase6_docker_ui_smoke_20260726.txt`, `docs/evidence/phase6_docker_monitor_smoke_20260726.txt` |
| Criterion status | individual Docker image build and plain-container smoke pass; Docker Compose, service-stack integration, registry push, and cloud deployment remain incomplete |

### Docker Compose Core Stack Smoke

| Field | Value |
|-------|-------|
| Command | `bash scripts/remote/compose_smoke.sh` / `make remote-compose-smoke` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Compose version | Docker Compose `v5.3.1`, user-level plugin under `$HOME/.docker/cli-plugins` |
| Runtime env | VM-only `.env` created if missing; no local `.env` synced or committed |
| Compose project | `credit_mlops_codex_smoke`, isolated from any persistent stack |
| Services | `postgres`, `redis`, `api`, `ui` |
| Runtime | 74 seconds |
| Result | `compose_smoke_exit=0`; `docker compose config --quiet` passed; API/UI builds passed; Postgres, Redis, API, and UI reached Docker health `healthy` |
| HTTP smoke | API `/health` returned `status=ok`, `model_version=fallback_local`; UI health returned `ok` |
| Cleanup | `docker compose down -v --remove-orphans` removed containers, network, and isolated Postgres volume |
| Evidence | `docs/evidence/phase6_compose_smoke_20260726.txt`, `docs/evidence/phase6_compose_smoke_runtime_20260726.txt` |
| Criterion status | core Compose stack passes; monitoring profile, Dockerized load tests, image push, and Cloud Run remain incomplete |

### Read-Only GCP Deployment Prerequisite Smoke

| Field | Value |
|-------|-------|
| Command | `bash scripts/remote/cloud_smoke.sh` / `make remote-cloud-smoke` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Runtime | 10 seconds |
| Active account | `582914829900-compute@developer.gserviceaccount.com` |
| Project | `driven-reef-452414-b5` |
| Result | `gcp_readonly_smoke_exit=1` |
| Passing checks | `auth_exit=0`, `project_config_exit=0`, `services_filter_exit=0`; filtered Service Usage output shows `serviceusage.googleapis.com` enabled |
| Blocking checks | `project_describe_exit=1`, `artifact_repos_exit=1`, `cloud_run_services_exit=1`, `scheduler_jobs_exit=1` |
| Blocking reasons | Cloud Resource Manager disabled/permissioned for consumer project `582914829900`; Artifact Registry, Cloud Run Admin, and Cloud Scheduler APIs disabled for `driven-reef-452414-b5` |
| Mutations | none; no API enablement, Terraform plan/apply, image push, or deployment |
| Evidence | `docs/evidence/phase6_gcp_readonly_smoke_20260726.txt`, `docs/evidence/phase6_gcp_readonly_smoke_runtime_20260726.txt` |
| Criterion status | cloud deployment remains blocked by APIs/IAM; read-only diagnostic path is reusable and correctly fails |

### Docker Compose API Load Smoke

| Field | Value |
|-------|-------|
| Command | `bash scripts/remote/compose_load_smoke.sh` / `make remote-compose-load-smoke` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Compose project | `credit_mlops_codex_load`, isolated and torn down |
| Services | `postgres`, `redis`, `api`, `ui` |
| Data mount | API mounts VM-only `./data:/app/data:ro` and sets `PROPERTY_GOLD_PATH` to the gold parquet |
| Workload | 1,000 AVM requests and 1,000 lending requests at concurrency 10 against Dockerized API |
| Runtime | 78 seconds |
| Health | Postgres, Redis, API, and UI reached Docker health `healthy` |
| AVM result | status 200 only; 0% errors; median 198.94 ms; p95 283.01 ms; p99 353.71 ms |
| Lending result | status 200 only; 0% errors; median 16.55 ms; p95 33.93 ms; p99 76.33 ms |
| Failed approach | initial load attempt returned AVM 503 until Compose mounted/configured the property gold path |
| Evidence | `docs/evidence/phase6_compose_load_smoke_20260726.txt`, `docs/evidence/phase6_compose_load_smoke_runtime_20260726.txt`, `docs/evidence/property_api_docker_compose_benchmark_20260726.json`, `reports/generated/property_api_docker_compose_benchmark_20260726.json` |
| Criterion status | Dockerized API load p95 passes for core property AVM/lending paths; Cloud Run p95 and monitoring-profile Compose remain incomplete |

### Scoped Remote Coverage

| Field | Value |
|-------|-------|
| Command | `make remote-coverage-smoke` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Tests under coverage | 139 passed in 15.91 seconds |
| Wrapper runtime | 19 seconds |
| Total scoped coverage | 81% |
| Weakest modules | `src/data_prep.py` 31%, `src/scorecard.py` 48%, `api/model_loader.py` 49% |
| Evidence | `docs/evidence/phase7_coverage_stdout_20260726.txt`, `docs/evidence/phase7_coverage_report_20260726.txt`, `reports/generated/phase7_coverage_20260726.json` |
| Criterion status | coverage measured; not enforced as a gate yet |

### Remote Vulnerability Audit

| Field | Value |
|-------|-------|
| Command | `make remote-vulnerability-smoke` |
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Runtime | 41 seconds |
| Audit status | `pip_audit_exit=0`, `pip_audit_text_exit=0` |
| Vulnerability count | 0 known vulnerabilities after dependency and TestClient warning remediation |
| Affected packages | none in latest audit |
| Skipped package | `credit-mlops` 0.1.0, local package not found on PyPI |
| Evidence | `docs/evidence/phase7_pip_audit_report_20260726.txt`, `docs/evidence/phase7_pip_audit_runtime_20260726.txt`, `reports/generated/phase7_pip_audit_summary_20260726.json` |
| Criterion status | vulnerability audit measured; security gate passes |

### Portfolio Documentation Packaging

| Field | Value |
|-------|-------|
| Updated docs | `README.md`, `reports/reproduce.md` |
| Scope | remote-first project overview, evidence table, blocker table, remote reproduction commands, API surface, documentation map |
| Baseline issue | prior docs described local/Docker-first credit-scoring reproduction and did not represent the active Property Intelligence contract |
| Criterion status | portfolio entrypoint aligned with measured evidence; dependency remediation is now complete for PyPI-auditable packages |

### Dependency Remediation Resolver Probe

| Field | Value |
|-------|-------|
| Probe location | VM `/tmp` sandbox with copied `pyproject.toml` and `uv.lock` only |
| Probe 1 | failed; `mlflow==3.12.0` requires `cryptography<47`, conflicting with audit fix `cryptography==48.0.1` |
| Probe 2 | resolver dry-run passed with 172 packages |
| Required broad upgrades | `mlflow 3.14.0`, `fastapi 0.140.0`, `starlette 1.3.1`, `streamlit 1.54.0`, `pillow 12.3.0`, `nltk 3.10.0`, plus transitives |
| Evidence | `docs/evidence/phase7_dep_remediation_probe1_20260726.txt`, `docs/evidence/phase7_dep_remediation_probe2_20260726.txt` |
| Criterion status | remediation path identified; follow-up compatibility run applied and verified the pin/lock changes |

### Dependency Remediation Compatibility

| Field | Value |
|-------|-------|
| Lock generation | `uv lock --upgrade` passed in 1 second |
| VM dependency sync | `uv sync --frozen --all-extras --dev` passed in 6 seconds |
| Updated direct pins | `mlflow 3.14.0`, `fastapi 0.140.0`, `python-dotenv 1.2.2`, `streamlit 1.54.0`, plus security constraints for affected transitives |
| Ruff/full tests | Ruff passed; 139 tests passed in 22.96 seconds |
| Coverage after remediation | 139 tests passed in 18.58 seconds; scoped coverage 81%; wrapper runtime 23 seconds |
| API smoke after remediation | comparables, AVM, and lending endpoints returned 200; wrapper runtime 5 seconds |
| Vulnerability audit after remediation | `pip_audit_exit=0`, 0 known vulnerabilities, runtime 33 seconds |
| Warning | FastAPI/Starlette TestClient deprecation warning was observed here and resolved in the later `httpx2` remediation |
| Evidence | `docs/evidence/phase7_dep_remediation_lock_20260726.txt`, `docs/evidence/phase7_dep_remediation_sync_20260726.txt`, `docs/evidence/phase7_dep_remediation_tests_20260726.txt`, `docs/evidence/phase7_dep_remediation_api_smoke_runtime_20260726.txt`, `docs/evidence/phase7_pip_audit_report_20260726.txt` |
| Criterion status | dependency security remediation passes non-Docker VM compatibility checks |

### TestClient Warning Remediation

| Field | Value |
|-------|-------|
| Dependency change | added dev-only `httpx2==2.9.1`; lock added `httpcore2==2.9.1` and `truststore==0.10.4` |
| Lock generation | `uv lock` passed in 0 seconds |
| VM dependency sync | `uv sync --frozen --all-extras --dev` passed in 0 seconds |
| Focused probe | 39 API/deployment/chaos tests passed in 4.89 seconds with `httpx2` injected |
| Ruff/full tests | Ruff passed; `uv run pytest -q -W default` passed 139 tests in 11.20 seconds with no warning summary; wrapper runtime 14 seconds |
| Coverage after remediation | 139 tests passed in 15.91 seconds; scoped coverage 81%; wrapper runtime 19 seconds |
| Vulnerability audit after remediation | `pip_audit_exit=0`, 0 known vulnerabilities, runtime 41 seconds |
| Evidence | `docs/evidence/phase7_httpx2_lock_20260726.txt`, `docs/evidence/phase7_httpx2_sync_20260726.txt`, `docs/evidence/phase7_httpx2_tests_20260726.txt`, `docs/evidence/phase7_coverage_stdout_20260726.txt`, `docs/evidence/phase7_pip_audit_report_20260726.txt` |
| Criterion status | TestClient deprecation warning resolved for the VM test path; Docker, GCP, and coordinate-backed GIS remain blocked |

### GCP Deployer Smoke And Terraform Plan

| Field | Value |
|-------|-------|
| Execution location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| Cloud smoke | exit 0 in 10 seconds with deployer account `credit-mlops-deployer@driven-reef-452414-b5.iam.gserviceaccount.com` |
| Terraform | Terraform 1.9.8/provider 6.50.0; init and plan exit 0 in 3 seconds |
| Plan | 30 to add, 0 to change, 0 to destroy; Cloud SQL disabled |
| Cost | Not numerically estimated: plan has no provider cost model and approved usage assumptions are absent; no resources were created |
| Remaining blockers | Placeholder image tags, image push, MLflow secret population, apply-time IAM/cost approval, apply, Cloud Run/API/scheduler smoke, and rollback evidence |
| Evidence | `docs/evidence/phase6_gcp_readonly_smoke_20260726.txt`, `docs/evidence/phase6_terraform_init_plan_20260727.txt` |
| Criterion status | Remote GCP prerequisite and Terraform plan gates pass; no apply was run |

### Targeted Artifact Registry Apply And Immutable Image Push

| Field | Value |
|-------|-------|
| Target | `google_artifact_registry_repository.images` |
| Safety check | Initial target plan was 14 additions due to broad API-service dependency; after narrowing, target plan was exactly 1 addition |
| Apply result | 1 Artifact Registry repository added, 0 changed, 0 destroyed |
| Repository | `projects/driven-reef-452414-b5/locations/asia-southeast1/repositories/credit-mlops`; Docker Standard; Google-managed key; 1665.702MB measured |
| API image | `asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-api:codex-20260727-5de2e58`; digest `sha256:b4e4dcd3afd7171a29b808afe45fc913d9c8b4a35d8e1b273f14dd725650f0d6` |
| Job image | `asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-job:codex-20260727-5de2e58`; digest `sha256:d74322f93c6b0fb33176cfb3208835303a5d960e6edeaefd60cade902a2b03a1` |
| Final plan | 29 to add, 0 to change, 0 to destroy; API/job references use immutable digests; no placeholders |
| Remaining blockers | Secret value population, apply-time IAM/cost approval, full apply, Cloud Run/API smoke, Scheduler execution, and rollback evidence |
| Criterion status | Repository and image push gates pass; final plan recorded; stopped before full apply |

### Immutable Production Image Build And Push Blocker

| Field | Value |
|-------|-------|
| Build location | VM `lfm`, workspace `/home/ducan/credit-mlops-codex` |
| API image | `asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-api:codex-20260727-5de2e58`; digest `sha256:b4e4dcd3afd7171a29b808afe45fc913d9c8b4a35d8e1b273f14dd725650f0d6`; 856,410,496 bytes |
| Job image | `asia-southeast1-docker.pkg.dev/driven-reef-452414-b5/credit-mlops/property-job:codex-20260727-5de2e58`; digest `sha256:d74322f93c6b0fb33176cfb3208835303a5d960e6edeaefd60cade902a2b03a1`; 852,474,397 bytes |
| Push result | Docker auth configured with active deployer account; both pushes exit 1 because Artifact Registry repository `credit-mlops` does not exist |
| Source change | Added `Dockerfile.job`; Terraform ETL command now invokes `python scripts/property_etl.py` |
| Remaining blockers | Terraform apply or separately approved repository creation, then image pushes; Secret Manager verification and final no-placeholder plan are not yet run |
| Criterion status | Image build passes; image push gate is blocked; no cloud resource was created |
