# Demo Scenario Test Report

**Date:** 2026-06-10
**System under test:** credit-mlops full stack (Docker Compose), all 8 always-on services healthy + NannyML monitor profile
**Serving model:** `credit_score_model@scorecard v7` (WOE logistic-regression scorecard, from DagsHub registry)
**Decision policy** (`api/decision.py`): `default_prob ≥ 0.70 → reject`, `0.45 ≤ p < 0.70 → manual_review`, `p < 0.45 → approve`

Every result below was produced by hitting the **live API** and querying the live Postgres / Prometheus / MLflow registry. Numbers are verbatim from the run — nothing is predicted or cherry-picked for flattery. Where the system behaved differently from the original demo plan, the difference is reported as a finding, not hidden.

---

## How to reproduce — two input modes (READ THIS FIRST)

There are **two different ways** to send a request, and they produce **different numbers**. Every scenario below is tagged with the mode it used. Do not mix them up.

### Mode A — full row from `test_data.csv`, sent via the API (scenarios 1, 2, 3, 4)
`test_data.csv` has **123 columns = 122 features + `label`**. Any single row has some empty (`NaN`) cells. "**109 non-null features**" means: for the *first `label=1` row*, after dropping the `NaN` cells and the `label` column, **109 feature values remain**, and the harness POSTed **all 109** to the API. The count differs per row (the first `label=0` row has 113 non-null) because each applicant has a different missing-data pattern — it is not a fixed number.

The Streamlit UI now supports this directly via **Mode A** (pick ground-truth label + row index), and the programmatic call below is the equivalent raw API path:

```python
# Reproduce scenario 1 (first label=1 row, full features) — gives p=0.8559
import pandas as pd, math, requests
df = pd.read_csv("data/processed/test_data.csv")
row = df[df["label"] == 1].iloc[0]                       # first defaulter
payload = {k: v for k, v in row.drop(labels=["label"]).to_dict().items()
           if not (isinstance(v, float) and math.isnan(v))}   # 109 non-null feats
print(len(payload), "features")
print(requests.post("http://localhost:8000/predict?model=scorecard", json=payload).json())
# -> default_probability ≈ 0.8559, decision=reject, credit_score=379
# Scenario 2: df[df["label"]==0].iloc[0]   Scenario 3: df.iloc[20]
```

### Mode B — 14 features only, the current Streamlit UI path
The current UI (`ui/streamlit_app.py`) exposes **only these 14 features**; everything else is left null and KNN-imputed:

```
NUMBER_OF_LOANS, NUMBER_OF_LOANS_NON_BANK, SHORT_TERM_COUNT_BANK,
SHORT_TERM_COUNT_NON_BANK, NUMBER_OF_CREDIT_CARDS, NUMBER_OF_CREDIT_CARDS_BANK,
NUMBER_OF_RELATIONSHIP_BANK, NUMBER_OF_RELATIONSHIP_NON_BANK,
NUM_NEW_LOAN_TAKEN_3M, NUM_NEW_LOAN_TAKEN_6M, ENQUIRIES_3M, ENQUIRIES_6M,
OUTSTANDING_BAL_LOAN_CURRENT, OUTSTANDING_BAL_ALL_CURRENT
```

> **⚠️ Mode A ≠ Mode B — verified.** Taking the *same* first `label=1` row but sending **only its 14 UI features** gives **`p=0.8167` (score 401)**, not the `p=0.8559` (score 379) of the full row. Same `reject` decision here by luck, but the probability differs and on other rows the decision can flip. The Streamlit UI now exposes **both** paths explicitly: use **Mode A** for scenarios 1–4. Scenarios 5–6 are still **partial-input demonstrations**, but their exact report payloads are API-only because they include 3 fields the current UI does not expose.

---

## UI / command cheat-sheet

| Scenario | Exact via current UI? | How to reproduce |
|---|---|---|
| 1 | Yes | **Mode A** -> `label=1` -> `subset index=0` |
| 2 | Yes | **Mode A** -> `label=0` -> `subset index=0` |
| 3 | Yes | **Mode A** -> `label=1` -> `subset index=3` (**not** `20`; this case is `df.iloc[20]`, which becomes subset index 3 after filtering `label=1`) |
| 4 | Yes | Same as scenario 1, then inspect the scorecard breakdown panel |
| 5 | No (exact) | Use the API payload in the reproduction section. Current UI does **not** expose `CREDIT_CARD_NUMBER_OF_LATE_PAYMENT`, `CREDIT_CARD_MONTH_SINCE_30DPD`, or `NUMBER_OF_RELATIONSHIP`, so the report's exact numbers are API-only. |
| 6 | No (exact) | Same payload as scenario 5, but call `?model=champion&source=local` |
| 7 | Partial | UI shows per-request `latency_ms`, but the report's p50/p95 numbers come from a scripted warm loop |
| 8 | Partial | In UI, switch model/source and watch the first `latency_ms`; exact cold-vs-warm comparison is easier with the command below |
| 9 | Yes | Score the same payload twice and change the sidebar `Model alias` / `Registry source` between requests |
| 10 | No | Run `scripts/promote_model.py` and `scripts/rollback_model.py` |
| 11 | No | Run `pytest tests/test_deployment.py -q` |
| 12 | Partial | UI can use `source=local`, but the report's "identical output" claim should be checked with the exact API compare command below |
| 13 | Partial | UI footer shows a short `trace_id`; exact uniqueness / DB lookup is easier with the API commands below |
| 14 | No | Run the NannyML monitor batch job and inspect `reports/nannyml/latest_summary.json` |
| 15 | No | Same as scenario 14; the "12 drifted features" result is from the monitor output, not the UI |
| 16 | No | Use the rate-limit loop command below |
| Observability | Partial | Grafana / Prometheus are browsable, but the exact checks in the report are command-driven |

## Summary table

| # | Scenario | Subsystem | Verdict | One-line result |
|---|----------|-----------|---------|-----------------|
| 1 | High-risk full applicant → reject | Model / decisioning | ✅ GOOD | label=1 row → `p=0.856`, reject, score 379 |
| 2 | Low-risk full applicant → approve | Model / decisioning | ✅ GOOD | label=0 row → `p=0.098`, approve, score 796 |
| 3 | Borderline applicant → manual_review | Decisioning | ✅ GOOD | found real row → `p=0.674`, manual_review, score 479 |
| 4 | Scorecard explainability breakdown | Explainability | ✅ GOOD | 18 WOE contributions sum exactly to score 371.48 |
| 5 | Partial input on scorecard | Robustness | ⚠️ PARTIAL | runs fine, but hand-built "risky" profile scored *low* risk |
| 6 | Same partial input on XGBoost champion | Model failure mode | ❌ FALSE | inversion: "clean" profile → `p=0.997` reject |
| 7 | Single-pass latency (warm) | Latency | ✅ GOOD | p50=215 ms, p95=237 ms |
| 8 | Cold-start latency tail | Latency | ⚠️ PARTIAL | first call 677 ms vs 215 ms warm |
| 9 | Per-request model switching | MLOps | ✅ GOOD | `model_alias` flips scorecard↔champion correctly |
| 10 | Promote → rollback with audit trail | MLOps governance | ✅ GOOD | full cycle + 2 audit rows (host DB-URL footgun fixed) |
| 11 | Non-blocking background reload | MLOps resilience | ✅ GOOD | 14/14 deployment tests pass |
| 12 | Local-source fallback (no registry) | MLOps resilience | ✅ GOOD | `fallback_scorecard_local` serves, identical output |
| 13 | trace_id per request | Observability | ✅ GOOD | unique UUID4 returned + now persisted/queryable in DB |
| 14 | NannyML CBPE (AUC without labels) | Monitoring | ⚠️ PARTIAL | estimates `AUC≈0.830` but on 64 rows / 1 chunk |
| 15 | NannyML drift "12 features drifted" | Monitoring | ❌ FALSE | false-positive: artifact of synthetic seed data |
| 16 | Rate limiting | Reliability | ✅ GOOD | 100×200, 20×429, first 429 at request #101 |
| — | Prometheus + Grafana observability | Monitoring | ✅ GOOD | both targets up, decision distribution live |

**Tally: 11 GOOD · 3 PARTIAL · 2 FALSE** (plus the observability check). This honestly covers model inference, decisioning, explainability, partial-input robustness, a real model failure mode, latency (warm + cold), per-request switching, promote/rollback governance, reload resilience, local fallback, tracing, CBPE performance estimation, drift, rate limiting, and the metrics pipeline.

---

## ✅ GOOD cases

### 1. High-risk full applicant → REJECT
**Input (Mode A — full row via API):** first `label=1` (defaulter) row from `test_data.csv` — all 109 non-null feature columns POSTed to `/predict`. *Not reproducible via the 14-field UI (that path gives p=0.8167; see "two input modes" above).*
**Result:** `default_probability=0.8559`, `decision=reject`, `credit_score=379`, `risk_band=Very Poor`, `latency_ms=202`.
**Top WOE contributors:** `NUMBER_OF_LOANS=1` (bin `(-inf,4]`, woe −1.12, +41.0), `NUMBER_OF_RELATIONSHIP_NON_BANK=1` (woe −0.59, +37.4), `ENQUIRIES_PCA_2` (+33.4).
**Why it works:** This is the scorecard's home turf — a thin-file applicant (1 loan, 1 relationship) sits in low-count bins that the WOE model has learned carry high default odds. Signal is strong and unambiguous; the model agrees with the ground-truth label.

### 2. Low-risk full applicant → APPROVE
**Input (Mode A — full row via API):** first `label=0` (good) row, all 113 non-null features POSTed to `/predict` (`df[df["label"]==0].iloc[0]`).
**Result:** `default_probability=0.0979`, `decision=approve`, `credit_score=796`, `risk_band=Excellent`, `latency_ms=157`.
**Top contributors:** `NUMBER_OF_LOANS_NON_BANK=10` (bin `(8.57,+inf]`, woe +0.85, +65.8), `NUM_NEW_LOAN_TAKEN_PCA_1` (+51.2), `NUMBER_OF_RELATIONSHIP_BANK=10` (+46.0).
**Why it works:** A thick-file applicant (10 loans, 10 bank relationships) lands in high-count bins with positive WOE — in this Vietnamese-bureau dataset, established credit history is protective. Correctly classified.
**Note for the demo:** scenarios 1 and 2 together reveal the dataset's direction — **higher counts = lower risk** (thick file). This is the opposite of the naive "more loans = riskier" intuition and explains the surprise in scenario 5.

### 3. Borderline applicant → MANUAL_REVIEW
**Input (Mode A — full row via API):** test row #20 (`df.iloc[20]`, `label=1`), all non-null features POSTed to `/predict`. **UI equivalent:** `Mode A` -> `label=1` -> `subset index=3`. (Found by scanning rows 18–70 for a probability in `[0.45, 0.70)`.)
**Result:** `default_probability=0.674`, `decision=manual_review`, `credit_score=479`, `risk_band=Poor`.
**Corroboration:** across the whole test session the live counter `prediction_decision_total` read **approve=118, reject=22, manual_review=6** — the middle band is genuinely exercised, not dead code.
**Why it works:** `0.45 ≤ 0.674 < 0.70` routes to the human-underwriter band exactly as `make_decision()` specifies. The three-tier policy is intentional and business-driven, independent of any F1-maximizing threshold.

### 4. Scorecard explainability breakdown
**Input (Mode A — full row via API):** same request as scenario 1 (first `label=1` row).
**Result:** the response carries an 18-row `scorecard_breakdown`, each with `{feature, raw_value, bin, woe, score_contribution, iv}`. The contributions **sum to 371.48**, exactly equal to the reported `scorecard_score=371.48`.
**Why it works:** WOE logistic regression is additive in log-odds, so every decision decomposes feature-by-feature with no residual. This is the regulatory-grade interpretability that justifies serving the scorecard over the (marginally higher-AUC) XGBoost champion.

### 7. Single-pass latency (warm)
**Result (12 warm requests):** server-reported `latency_ms` p50=**214.9**, p95=**236.8**, min=192.3, max=241.3.
**Why it works:** `predict_all()` runs the KNNImputer pipeline once per request and derives probability, score, and the 18-feature breakdown from the same transformed frame — the documented ~11× win over re-running the pipeline per output.

### 9. Per-request model switching (no restart)
**Result:** same payload, `?model=scorecard` → `model_alias=scorecard`, `model_version=...@scorecard v7`; `?model=champion&source=local` → `model_alias=champion`, `model_version=fallback_local`.
**Why it works:** the loader resolves alias/source per request and stamps the answer into the response, so every prediction is self-describing — essential for A/B routing and audit.

### 10. Promote → rollback with audit trail  *(GOOD, with a footgun)*
**Test (on the non-serving `challenger` alias, to avoid disturbing live serving):**
```
promote challenger v1 → v3   →  event #1 logged
rollback challenger v3 → v1   →  event #2 logged (reason recorded)
challenger restored to v1 ✓
```
`model_deployment_events` afterwards:

| id | event_type | alias | from | to | triggered_by | reason |
|----|-----------|-------|------|----|--------------|--------|
| 1 | promote | challenger | 1 | 3 | demo-test | |
| 2 | rollback | challenger | 3 | 1 | demo-test | demo rollback test |

**Why it works:** rollback reads the last `promote` row and reverses it; both events are durably logged with actor and reason.
**⚠️ Footgun found (truthful) — now FIXED:** on the **first** attempt, run directly from the host shell, the MLflow alias change **succeeded** but the Postgres logging **crashed** with `could not translate host name "postgres"`. The `.env` `DATABASE_URL` uses the Docker-internal hostname `postgres`, which doesn't resolve outside the compose network. Net effect: a *partial* success — registry mutated, audit silently lost, and rollback then couldn't find the previous version. **Fix (2026-06-10):** `scripts/_db.py::resolve_engine()` now probes the configured URL and auto-falls-back from `@postgres` to `@localhost` (connection-tested), resolving the engine *before* the registry is mutated. Re-verified from the host shell with no override — events #3/#4 logged, challenger restored. See action item #1.

### 11. Non-blocking background reload
**Result:** `pytest tests/test_deployment.py` → **14 passed in 1.78s**. Covers: health stays 200 during a reload failure; predict works while a reload is in flight; `maybe_reload()` spawns a daemon thread in <50 ms and never double-spawns; promote/rollback set alias + log events.
**Why it works:** the reload runs on a side daemon thread under a global lock, swapping model attributes atomically — in-flight requests keep serving the old model, and a failing reload only bumps `model_reload_failure_total`.

### 12. Local-source fallback (registry bypassed)
**Result:** `?source=local` → `model_version=fallback_scorecard_local`, output `p=0.0381` — **identical** to the same request served from the DagsHub registry.
**Why it works:** the loader can serve from `artifacts/scorecard_model.joblib` without ever contacting MLflow. This is the graceful-degradation path when DagsHub is unreachable (health would report `degraded` but predictions continue).

### 13. trace_id per request  *(GOOD, with a gap)*
**Result:** two consecutive requests returned `trace_id=49591fc2-…` and `af0b8451-…` — both valid 36-char UUID4s, unique per request.
**⚠️ Gap found (truthful) — now FIXED:** the `predictions` audit table originally stored `features, default_probability, credit_score, risk_band, decision, model_version, latency_ms, ts` — **but not `trace_id`**, so a Postgres row couldn't be looked up by it. **Fix (2026-06-10):** added a `trace_id TEXT` column + `idx_predictions_trace_id` index (with an `ALTER TABLE … ADD COLUMN IF NOT EXISTS` migration) and the audit insert now writes it. Re-verified: a response `trace_id` is now found directly in Postgres — e.g. `81497521-…` → `decision=reject, score=372`. See action item #2.

### 16. Rate limiting
**Result (120 rapid requests):** `200×100, 429×20`, **first 429 at request #101**, over 28 s.
**Why it works:** the Redis-backed limiter enforces exactly 100 req/min; request 101 within the window is rejected with `{"detail":"Rate limit exceeded (100 req/min)"}`. (This also explains why the test harness had to be throttled to ~80 req/min.)

### Observability (Prometheus + Grafana)
**Prometheus targets:** `credit_scoring_api` UP, `pushgateway` UP.
**Live API metrics confirmed:** `prediction_decision_total{approve=118,reject=22,manual_review=6}`, `prediction_default_prob` histogram (146 obs), `api_latency_seconds` histogram, `feature_missing_rate` (146 obs), `model_version_info{alias=scorecard}=1`, `model_reload_success_total=1`.
**NannyML metrics in Prometheus** (after the Pushgateway-persistence fix): `nannyml_estimated_auc=0.830`, `nannyml_estimated_f1=0.645`, `nannyml_drifted_features_count=12`, `nannyml_production_rows=64`.
**Grafana:** healthy (v11.3.0, `database: ok`). The 3-row dashboard (System / Model / NannyML) renders these series.

---

## ⚠️ PARTIAL cases

### 5. Partial input on the scorecard — runs, but not as intuitive as advertised
**Input (partial payload via API; not exactly enterable in the current UI):** two hand-built profiles, each only ~13 raw/count-ish features. These are *typed in*, not taken from `test_data.csv`:
- "high-risk": 8 loans, 6 cards, 7 enquiries, 3 late payments, recent 30DPD
- "low-risk": 1 loan, 1 card, 0 enquiries, 0 late payments

Reproduce:
```python
import requests
high = {"NUMBER_OF_LOANS":8,"NUMBER_OF_CREDIT_CARDS":6,"ENQUIRIES_3M":7,"ENQUIRIES_6M":10,
        "SHORT_TERM_COUNT_BANK":5,"SHORT_TERM_COUNT_NON_BANK":6,"NUM_NEW_LOAN_TAKEN_3M":4,
        "NUM_NEW_LOAN_TAKEN_6M":6,"CREDIT_CARD_NUMBER_OF_LATE_PAYMENT":3,
        "CREDIT_CARD_MONTH_SINCE_30DPD":1,"OUTSTANDING_BAL_LOAN_CURRENT":50000,
        "OUTSTANDING_BAL_ALL_CURRENT":80000,"NUMBER_OF_RELATIONSHIP":4}
low  = {"NUMBER_OF_LOANS":1,"NUMBER_OF_CREDIT_CARDS":1,"ENQUIRIES_3M":0,"ENQUIRIES_6M":0,
        "SHORT_TERM_COUNT_BANK":0,"SHORT_TERM_COUNT_NON_BANK":0,"NUM_NEW_LOAN_TAKEN_3M":0,
        "NUM_NEW_LOAN_TAKEN_6M":0,"CREDIT_CARD_NUMBER_OF_LATE_PAYMENT":0,
        "CREDIT_CARD_MONTH_SINCE_30DPD":0,"OUTSTANDING_BAL_LOAN_CURRENT":0,
        "OUTSTANDING_BAL_ALL_CURRENT":0,"NUMBER_OF_RELATIONSHIP":1}
for name, payload in [("high", high), ("low", low)]:
    print(name, requests.post("http://localhost:8000/predict?model=scorecard", json=payload).json())
```

**Result (scorecard):**
| profile | default_probability | decision | credit_score |
|---------|--------------------|----------|--------------|
| "high-risk" | **0.0381** | approve | 829 |
| "low-risk" | 0.0811 | approve | 805 |

**The honest finding:** the profile I *intended* to be risky scored as the **lowest** risk of the two. This is **not** the model handling partial input cleanly — it's two compounding effects:
1. **Counterintuitive WOE direction** (see scenarios 1–2): high counts = thick file = *protective* in this dataset, so "8 loans, 6 cards" pushes the score *up*, not down.
2. **Imputation dominates the PCA features.** 10 of the scorecard's 18 features are PCA-derived (`ENQUIRIES_PCA_*`, `OUTSTANDING_BAL_PCA_*`, `NUM_NEW_LOAN_TAKEN_PCA_*`). With only raw counts supplied, the PCA-source columns are KNN-imputed from a thin-file neighbourhood, so the PCA features — which carry large IV — reflect the imputed segment, not the caller's intent.

**Verdict:** partial input is *robust* (no error, fast, fully explained) but **not reliably steerable** by a handful of raw counts. A naive "risky-looking" partial payload can score as low-risk. **Demo guidance:** present this as a real limitation — the scorecard needs its actual feature vector to be trustworthy; thin partial payloads produce confident-but-unsteerable scores. (Contrast sharply with scenario 6, where XGBoost does far worse on the very same inputs.)

### 8. Cold-start latency tail
**Result:** the **first** partial-input request after a model/source change took **676.8 ms**; once warm, p50 settled at **214.9 ms** (scenario 7). The `?source=local` first-load call was 241 ms.
**Why:** first touch of a freshly-resolved model pays deserialization + pipeline warm-up. Steady-state is ~3× faster. **Demo guidance:** show this so the p95 panel isn't misread as "always ~215 ms" — there is a real cold tail on first use of each (alias, source) combination.

### 14. NannyML CBPE — estimates AUC with no labels, but underpowered here
**Result:** `cbpe_estimated_auc=0.8301`, `cbpe_estimated_f1=0.6446`, `cbpe_n_alerts=0`, on `production_rows=64`, `chunk_size=50` → **1 chunk**.
**Why it's valuable:** CBPE estimates ROC-AUC from prediction probabilities alone — the only early-warning signal available for credit scoring, where true default labels arrive 3–12 months later. The estimate (0.830) is in the right neighbourhood of the scorecard's offline AUC (~0.81).
**Why it's only PARTIAL:** 64 production rows is **one chunk** — the estimate has wide sampling error and no trend. It is *directional*, not a precise AUC. CBPE is also only trustworthy because the scorecard is **calibrated** (WOE-LR); the same estimate on the XGBoost champion would be unreliable (uncalibrated probabilities). **Demo guidance:** frame as "earliest possible degradation signal," explicitly caveated on sample size and calibration.

---

## ❌ FALSE cases (genuine failure / misleading-signal demonstrations)

### 6. XGBoost champion on partial input → prediction inversion
**Input (partial payload via API; not exactly enterable in the current UI):** the **exact same** two ~13-feature profiles from scenario 5 (see that snippet), but served with `?model=champion&source=local` (XGBoost) instead of `?model=scorecard`.
**Result:**
| profile | scorecard `p` | **XGBoost champion `p`** | XGBoost decision |
|---------|--------------|--------------------------|------------------|
| "high-risk" | 0.0381 | **0.2057** | approve (score 737) |
| "low-risk" | 0.0811 | **0.9974** | **reject (score 301)** |

**The failure:** XGBoost rates the *cleaner* profile (1 loan, 0 enquiries, 0 late payments) at **99.7% default probability** — a confident, nonsensical inversion — while rating the busier profile as lower risk. The two models, on identical inputs, disagree wildly.
**Why it happens:** XGBoost was trained on dense 122-feature rows. On partial input, 100+ features are KNN/median-imputed, which violates the feature interactions the tree ensemble learned. The model extrapolates into a region it never saw and produces garbage with high confidence. This is the documented reason the **scorecard**, not the higher-AUC champion, serves partial-input production traffic.
**Demo guidance:** the headline honesty moment — "best offline AUC" ≠ "right model for this input distribution." Show both numbers side by side.

### 15. NannyML "12 features drifted" → false-positive drift alert
**Result:** `drifted_features_count=12`, multivariate `reconstruction_error=1.30`, listing `NUMBER_OF_LOANS, ENQUIRIES_3M, …` as drifted.
**Why it's a false positive (in this demo):** the 64 production rows were **seeded with `random.uniform(...)`** during testing. That synthetic distribution differs from the `test_data.csv` reference on essentially every populated feature, so the Jensen-Shannon drift test fires on all of them. The detector is **working correctly** — but the "drift" is an artifact of how the demo data was generated, **not** a real population shift or model degradation.
**Demo guidance:** a teaching moment on alert hygiene. A red drift panel is a *prompt to investigate*, not proof of decay. The correct response is to check the data source (here: "oh, that's our synthetic seed traffic") before paging anyone. Pair with the stale-metric guard (`nannyml_last_run_timestamp_seconds`) to show the difference between "alert" and "incident."

---

## Reproduction

> Scenarios 1–4 are now exactly reproducible in the Streamlit UI via **Mode A**. Scenarios 5–6 still require API calls for the report's exact numbers because the current UI does not expose all of the fields used in those payloads. Note the API enforces **100 req/min**; throttle any scan loop to ~80/min or you will hit `429`.

```text
UI equivalents for scenarios 1-4
1: Mode A -> label=1 -> subset index=0
2: Mode A -> label=0 -> subset index=0
3: Mode A -> label=1 -> subset index=3   # this is absolute df.iloc[20]
4: same as 1, then inspect the breakdown panel
```

```python
# Scenarios 1-4 via API
import math, pandas as pd, requests

df = pd.read_csv("data/processed/test_data.csv")
rows = {
    1: df[df["label"] == 1].iloc[0],
    2: df[df["label"] == 0].iloc[0],
    3: df.iloc[20],
    4: df[df["label"] == 1].iloc[0],
}

for scenario, row in rows.items():
    payload = {k: float(v) for k, v in row.drop(labels=["label"]).to_dict().items()
               if not (isinstance(v, float) and math.isnan(v))}
    data = requests.post("http://localhost:8000/predict?model=scorecard", json=payload).json()
    print("scenario", scenario, "label", int(row["label"]), "features", len(payload),
          "p", round(data["default_probability"], 4), "decision", data["decision"],
          "score", data["credit_score"])
```

```python
# Scenarios 5-6 via API (exact report payloads; not exactly enterable in the current UI)
import requests

high = {
    "NUMBER_OF_LOANS": 8,
    "NUMBER_OF_CREDIT_CARDS": 6,
    "ENQUIRIES_3M": 7,
    "ENQUIRIES_6M": 10,
    "SHORT_TERM_COUNT_BANK": 5,
    "SHORT_TERM_COUNT_NON_BANK": 6,
    "NUM_NEW_LOAN_TAKEN_3M": 4,
    "NUM_NEW_LOAN_TAKEN_6M": 6,
    "CREDIT_CARD_NUMBER_OF_LATE_PAYMENT": 3,
    "CREDIT_CARD_MONTH_SINCE_30DPD": 1,
    "OUTSTANDING_BAL_LOAN_CURRENT": 50000,
    "OUTSTANDING_BAL_ALL_CURRENT": 80000,
    "NUMBER_OF_RELATIONSHIP": 4,
}
low = {
    "NUMBER_OF_LOANS": 1,
    "NUMBER_OF_CREDIT_CARDS": 1,
    "ENQUIRIES_3M": 0,
    "ENQUIRIES_6M": 0,
    "SHORT_TERM_COUNT_BANK": 0,
    "SHORT_TERM_COUNT_NON_BANK": 0,
    "NUM_NEW_LOAN_TAKEN_3M": 0,
    "NUM_NEW_LOAN_TAKEN_6M": 0,
    "CREDIT_CARD_NUMBER_OF_LATE_PAYMENT": 0,
    "CREDIT_CARD_MONTH_SINCE_30DPD": 0,
    "OUTSTANDING_BAL_LOAN_CURRENT": 0,
    "OUTSTANDING_BAL_ALL_CURRENT": 0,
    "NUMBER_OF_RELATIONSHIP": 1,
}

for model, source in [("scorecard", "auto"), ("champion", "local")]:
    for name, payload in [("high", high), ("low", low)]:
        data = requests.post(
            "http://localhost:8000/predict",
            params={"model": model, "source": source},
            json=payload,
        ).json()
        print(model, source, name, round(data["default_probability"], 4),
              data["decision"], data["credit_score"])
```

```python
# Scenarios 7-9, 12, 13, 16
import math, pandas as pd, requests, statistics, time

df = pd.read_csv("data/processed/test_data.csv")
row = df[df["label"] == 1].iloc[0]
payload = {k: float(v) for k, v in row.drop(labels=["label"]).to_dict().items()
           if not (isinstance(v, float) and math.isnan(v))}

# 7: warm latency
warm = []
for _ in range(12):
    data = requests.post("http://localhost:8000/predict?model=scorecard", json=payload).json()
    warm.append(data["latency_ms"])
print("warm p50", round(statistics.median(warm), 1), "min", round(min(warm), 1), "max", round(max(warm), 1))

# 8 + 9 + 12: switch source/model and inspect first response metadata
for params in [
    {"model": "scorecard", "source": "auto"},
    {"model": "scorecard", "source": "local"},
    {"model": "champion", "source": "local"},
]:
    data = requests.post("http://localhost:8000/predict", params=params, json=payload).json()
    print(params, data["latency_ms"], data["model_alias"], data["model_version"], round(data["default_probability"], 4))

# 13: trace_id changes per request
ids = [requests.post("http://localhost:8000/predict?model=scorecard", json=payload).json()["trace_id"] for _ in range(2)]
print("trace_ids", ids)

# 16: rate limit
statuses = []
for _ in range(120):
    r = requests.post("http://localhost:8000/predict?model=scorecard", json={"NUMBER_OF_LOANS": 1})
    statuses.append(r.status_code)
    time.sleep(0.2)
print("200s", statuses.count(200), "429s", statuses.count(429), "first_429_at",
      next((i + 1 for i, s in enumerate(statuses) if s == 429), None))
```

```bash
# Scenario 10: promote / rollback
python scripts/promote_model.py  --version 3 --alias challenger --promoted-by demo
python scripts/rollback_model.py --alias challenger --reason "demo" --triggered-by demo

# Scenario 11: non-blocking reload
pytest tests/test_deployment.py -q

# Scenarios 14-15: NannyML / drift
docker compose --profile monitoring run --rm nannyml_monitor

# Observability
curl -s localhost:9090/api/v1/targets
curl -s localhost:8000/metrics | grep prediction_decision_total
```

## Known issues surfaced by this demo (action items)
1. ~~**promote/rollback scripts assume the Docker-internal DB hostname**~~ — **FIXED (2026-06-10).** Added `scripts/_db.py::resolve_engine()`, which probes the configured `DATABASE_URL` and, if the `@postgres` host is unreachable, retries against `@localhost` (connection-tested). The engine is now resolved *before* the registry is mutated, so promote warns clearly instead of crashing post-mutation. Verified from the host shell with no override: both scripts now print `using localhost fallback` and log events #3/#4.
2. ~~**`trace_id` is not persisted** to the `predictions` table~~ — **FIXED (2026-06-10).** Added `trace_id TEXT` column + `idx_predictions_trace_id` index (with an `ALTER TABLE … ADD COLUMN IF NOT EXISTS` migration for existing tables), and the audit insert now writes it. Verified: a response `trace_id` is now looked up directly in Postgres.
3. **Scorecard partial-input scores are not steerable** by a few raw counts (PCA features dominate via imputation) — document the minimum feature set for a trustworthy score, or expose a confidence/coverage indicator in the response. *(open)*
4. **`datetime.utcnow()` deprecation** warning in `nannyml_monitor.py` — swap for `datetime.now(datetime.UTC)`. *(open)*
