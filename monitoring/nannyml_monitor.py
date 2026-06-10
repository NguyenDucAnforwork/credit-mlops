"""
NannyML performance estimation and feature drift detection.

Compares live predictions (from Postgres) against a labelled reference period
to estimate model performance WITHOUT ground truth labels (CBPE), detect
feature drift, and push metrics to Prometheus Pushgateway.

Why NannyML over Evidently for this project:
  - Evidently detects drift but cannot estimate model performance without labels.
  - In credit scoring, ground truth (did the customer default?) arrives 3–12
    months after the loan decision.  CBPE estimates AUC/F1 from prediction
    probabilities alone — no waiting for labels.

Run on demand:
    python monitoring/nannyml_monitor.py

Run via Docker Compose (monitoring profile):
    docker compose --profile monitoring run --rm nannyml_monitor

Outputs:
    reports/nannyml/latest_summary.json   — machine-readable summary
    reports/nannyml/cbpe_YYYY-MM-DD.html  — CBPE performance chart
    reports/nannyml/drift_YYYY-MM-DD.html — univariate drift chart
    reports/nannyml/mv_drift_YYYY-MM-DD.html — multivariate drift chart
    Prometheus Pushgateway metrics pushed to PUSHGATEWAY_URL
"""
from __future__ import annotations

import json
import os
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── paths ──────────────────────────────────────────────────────────────────────
MONITORING_DIR  = Path(__file__).parent
PROJECT_ROOT    = MONITORING_DIR.parent
REPORTS_DIR     = PROJECT_ROOT / "reports" / "nannyml"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

REF_CACHE_PATH  = MONITORING_DIR / "nannyml_reference.csv"
TEST_DATA_PATH  = PROJECT_ROOT / "data" / "processed" / "test_data.csv"
SCORECARD_PATH  = PROJECT_ROOT / "artifacts" / "scorecard_model.joblib"

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091")

# Decision threshold that matches api/decision.py (manual_review starts at 0.45)
DECISION_THRESHOLD = 0.45

# Features present in typical partial-input API requests (used for drift)
DRIFT_FEATURES = [
    "NUMBER_OF_LOANS",
    "NUMBER_OF_CREDIT_CARDS",
    "NUMBER_OF_RELATIONSHIP",
    "SHORT_TERM_COUNT_BANK",
    "SHORT_TERM_COUNT_NON_BANK",
    "ENQUIRIES_3M",
    "ENQUIRIES_6M",
    "NUM_NEW_LOAN_TAKEN_3M",
    "NUM_NEW_LOAN_TAKEN_6M",
    "OUTSTANDING_BAL_LOAN_CURRENT",
    "OUTSTANDING_BAL_ALL_CURRENT",
    "CREDIT_CARD_MONTH_SINCE_30DPD",
    "CREDIT_CARD_NUMBER_OF_LATE_PAYMENT",
]

# Minimum production rows to run any NannyML estimator
MIN_PROD_ROWS = 50


# ── reference dataset ──────────────────────────────────────────────────────────

def _build_reference() -> pd.DataFrame:
    """
    Load test_data.csv (features + labels), run scorecard model to get
    probabilities, cache as nannyml_reference.csv.

    NannyML CBPE's fit() phase needs: features, y_true, y_pred_proba, y_pred.
    y_pred_proba and y_pred are NOT stored in test_data.csv — we generate
    them here by running the local fallback scorecard model once.

    The cache avoids repeating the model-on-4000-rows step on every monitor run.
    Delete nannyml_reference.csv to force a rebuild after model version changes.
    """
    if REF_CACHE_PATH.exists():
        print(f"[nannyml] loaded cached reference: {REF_CACHE_PATH}")
        return pd.read_csv(REF_CACHE_PATH)

    if not TEST_DATA_PATH.exists():
        raise FileNotFoundError(f"test_data.csv not found: {TEST_DATA_PATH}")
    if not SCORECARD_PATH.exists():
        raise FileNotFoundError(f"scorecard_model.joblib not found: {SCORECARD_PATH}")

    print("[nannyml] building reference predictions (runs once, then cached)…")
    import joblib

    df = pd.read_csv(TEST_DATA_PATH)                    # 4000 rows, 122 features + 'label'
    feature_cols = [c for c in df.columns if c != "label"]

    model = joblib.load(SCORECARD_PATH)
    results = model.predict_all(df[feature_cols])

    df["y_pred_proba"] = np.array(results["proba"]).flatten()
    df["y_pred"]       = (df["y_pred_proba"] >= DECISION_THRESHOLD).astype(int)
    df["y_true"]       = df["label"].astype(int)
    df = df.drop(columns=["label"])

    df.to_csv(REF_CACHE_PATH, index=False)
    print(f"[nannyml] reference saved: {REF_CACHE_PATH}  ({len(df)} rows, "
          f"base_rate={df['y_true'].mean():.3f})")
    return df


# ── production data ────────────────────────────────────────────────────────────

def _load_production_data() -> pd.DataFrame | None:
    """
    Pull predictions from Postgres, unnest JSONB features column.

    The predictions table stores each request's raw feature dict as JSONB.
    pd.json_normalize unpacks it into flat columns matching the 122-feature schema.
    Many columns will be NaN for partial-input requests — that's fine; NannyML
    handles missing values and we filter drift columns to those with ≥30% fill.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[nannyml] DATABASE_URL not set — skipping production pull")
        return None

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text("""
                    SELECT ts, default_probability, decision, features
                    FROM   predictions
                    ORDER  BY ts ASC
                """),
                conn,
            )
    except Exception as exc:
        print(f"[nannyml] Postgres read failed: {exc}")
        return None

    if len(df) == 0:
        print("[nannyml] predictions table is empty")
        return None

    # Unnest JSONB — psycopg2 returns dicts; older drivers return JSON strings
    try:
        raw = df["features"].apply(
            lambda x: x if isinstance(x, dict) else json.loads(x)
        )
        features_df = pd.json_normalize(raw.tolist())
    except Exception as exc:
        print(f"[nannyml] JSONB unnest failed: {exc}")
        return None

    prod = pd.concat([df.drop(columns=["features"]), features_df], axis=1)
    prod["y_pred_proba"] = prod["default_probability"].astype(float)
    prod["y_pred"]       = (prod["y_pred_proba"] >= DECISION_THRESHOLD).astype(int)
    prod["timestamp"]    = pd.to_datetime(prod["ts"])

    print(f"[nannyml] production: {len(prod)} rows  "
          f"{prod['timestamp'].min().date()} → {prod['timestamp'].max().date()}")
    return prod


# ── helpers for NannyML result parsing ────────────────────────────────────────

def _extract_scalar(df: pd.DataFrame, keyword: str, sub: str = "value") -> float | None:
    """
    Find the latest value of a metric column in a NannyML result DataFrame.
    NannyML v0.13 uses MultiIndex columns: (metric_name, sub_metric).
    CBPE sub-columns: 'value', 'sampling_error', 'alert', etc.
    """
    try:
        cols = df.columns
        if isinstance(cols, pd.MultiIndex):
            # Depth-2: (metric, sub) — CBPE style
            # Depth-3: (feature, method, sub) — drift style; skip these here
            depth2 = [c for c in cols if len(c) == 2
                      and keyword in str(c[0]).lower() and sub in str(c[1]).lower()]
            if depth2:
                return float(df[depth2[0]].iloc[-1])
            # Fallback: depth-3 search
            depth3 = [c for c in cols if len(c) == 3
                      and keyword in str(c[0]).lower() and sub in str(c[2]).lower()]
            return float(df[depth3[0]].iloc[-1]) if depth3 else None
        else:
            matches = [c for c in cols if keyword in str(c).lower() and sub in str(c).lower()]
            return float(df[matches[0]].iloc[-1]) if matches else None
    except Exception:
        return None


def _count_alerts(df: pd.DataFrame, keyword: str = "") -> int:
    """Count chunks that triggered an alert for the given metric keyword."""
    try:
        cols = df.columns
        if isinstance(cols, pd.MultiIndex):
            # CBPE: 2-level (metric, sub); only look at depth-2 alert cols
            alert_cols = [c for c in cols if len(c) == 2
                          and c[1] == "alert"
                          and (not keyword or keyword in str(c[0]).lower())]
        else:
            alert_cols = [c for c in cols if "alert" in str(c).lower()
                          and (not keyword or keyword in str(c).lower())]
        return int(sum(bool(df[c].any()) for c in alert_cols))
    except Exception:
        return 0


def _drifted_features(drift_df: pd.DataFrame) -> list[str]:
    """
    Extract names of features that have at least one alert chunk.
    Drift results use 3-level MultiIndex: (feature, method, sub_metric).
    """
    drifted: set[str] = set()
    try:
        cols = drift_df.columns
        if isinstance(cols, pd.MultiIndex):
            for col in cols:
                # col is (feature, method, sub) — depth 3
                if len(col) == 3 and col[2] == "alert":
                    if drift_df[col].any():
                        drifted.add(col[0])
                # Also handle depth-2 drift results
                elif len(col) == 2 and col[1] == "alert":
                    if drift_df[col].any():
                        drifted.add(col[0])
        else:
            for col in cols:
                col_s = str(col)
                if "alert" in col_s.lower() and drift_df[col].any():
                    for feat in DRIFT_FEATURES:
                        if col_s.startswith(feat):
                            drifted.add(feat)
                            break
    except Exception:
        pass
    return sorted(drifted)


# ── NannyML estimators ─────────────────────────────────────────────────────────

def run_cbpe(ref: pd.DataFrame, prod: pd.DataFrame, chunk_size: int) -> dict:
    """
    Confidence-Based Performance Estimation.
    Estimates ROC AUC and F1 from prediction probabilities — no labels needed.
    ref must have y_true for the fit() phase only; prod does NOT need y_true.
    """
    import nannyml as nml
    warnings.filterwarnings("ignore", module="nannyml")

    try:
        estimator = nml.CBPE(
            y_pred_proba="y_pred_proba",
            y_pred="y_pred",
            y_true="y_true",
            problem_type="binary",
            metrics=["roc_auc", "f1"],
            chunk_size=chunk_size,
        )
        estimator.fit(ref)

        # prod does not need y_true — that's the whole point of CBPE
        prod_no_labels = prod.drop(columns=["y_true"], errors="ignore")
        results = estimator.estimate(prod_no_labels)
        results_df = results.to_df()

        latest_auc = _extract_scalar(results_df, "roc_auc", "value")
        latest_f1  = _extract_scalar(results_df, "f1",      "value")
        n_alerts   = _count_alerts(results_df, "roc_auc")

        try:
            results.plot(kind="performance").write_html(
                str(REPORTS_DIR / f"cbpe_{date.today()}.html")
            )
        except Exception:
            pass

        return {
            "estimated_auc": latest_auc,
            "estimated_f1":  latest_f1,
            "n_chunks":      len(results_df),
            "n_alerts":      n_alerts,
            "ok":            True,
        }
    except Exception as exc:
        print(f"[nannyml] CBPE failed: {exc}")
        return {"estimated_auc": None, "estimated_f1": None, "n_chunks": 0, "n_alerts": 0, "ok": False}


def run_univariate_drift(ref: pd.DataFrame, prod: pd.DataFrame,
                         feature_cols: list[str], chunk_size: int) -> dict:
    """
    Univariate drift per feature using KS / Chi-squared / Jensen-Shannon tests.
    Only uses features with at least 30% non-null values in production data.
    """
    import nannyml as nml
    warnings.filterwarnings("ignore", module="nannyml")

    # Keep only features present and sufficiently populated in both datasets
    available = [
        c for c in feature_cols
        if c in ref.columns and c in prod.columns
        and prod[c].notna().mean() >= 0.30
    ]
    if len(available) < 2:
        print(f"[nannyml] univariate drift: only {len(available)} features available — skipping")
        return {"drifted_features": [], "drifted_count": 0, "ok": False}

    try:
        calc = nml.UnivariateDriftCalculator(
            column_names=available,
            chunk_size=chunk_size,
        )
        calc.fit(ref[available])
        results = calc.calculate(prod[available])
        results_df = results.to_df()

        drifted = _drifted_features(results_df)

        try:
            results.plot(kind="drift").write_html(
                str(REPORTS_DIR / f"drift_{date.today()}.html")
            )
        except Exception:
            pass

        return {"drifted_features": drifted, "drifted_count": len(drifted), "ok": True}
    except Exception as exc:
        print(f"[nannyml] univariate drift failed: {exc}")
        return {"drifted_features": [], "drifted_count": 0, "ok": False}


def run_multivariate_drift(ref: pd.DataFrame, prod: pd.DataFrame,
                           feature_cols: list[str], chunk_size: int) -> dict:
    """
    PCA-based data reconstruction drift — catches multivariate shift not
    visible in any single feature's distribution.
    """
    import nannyml as nml
    warnings.filterwarnings("ignore", module="nannyml")

    available = [
        c for c in feature_cols
        if c in ref.columns and c in prod.columns
        and prod[c].notna().mean() >= 0.30
    ]
    if len(available) < 4:
        return {"reconstruction_error": None, "ok": False}

    try:
        calc = nml.DataReconstructionDriftCalculator(
            column_names=available,
            chunk_size=chunk_size,
        )
        calc.fit(ref[available])
        results = calc.calculate(prod[available])
        results_df = results.to_df()

        rec_error = _extract_scalar(results_df, "reconstruction_error", "value")
        if rec_error is None:
            # Some NannyML versions use a flat 'reconstruction_error' column
            if "reconstruction_error" in results_df.columns:
                rec_error = float(results_df["reconstruction_error"].iloc[-1])

        try:
            results.plot().write_html(
                str(REPORTS_DIR / f"mv_drift_{date.today()}.html")
            )
        except Exception:
            pass

        return {"reconstruction_error": rec_error, "ok": True}
    except Exception as exc:
        print(f"[nannyml] multivariate drift failed: {exc}")
        return {"reconstruction_error": None, "ok": False}


# ── Prometheus Pushgateway ─────────────────────────────────────────────────────

def _push_metrics(summary: dict) -> None:
    """Push NannyML summary metrics to Prometheus Pushgateway for Grafana display."""
    try:
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
        reg = CollectorRegistry()

        def g(name: str, doc: str) -> Gauge:
            return Gauge(name, doc, registry=reg)

        g("nannyml_estimated_auc",
          "CBPE-estimated ROC AUC without ground truth labels").set(
            summary.get("cbpe_estimated_auc") or 0)

        g("nannyml_estimated_f1",
          "CBPE-estimated F1 score without ground truth labels").set(
            summary.get("cbpe_estimated_f1") or 0)

        g("nannyml_drifted_features_count",
          "Number of features with detected univariate drift").set(
            summary.get("drifted_features_count") or 0)

        g("nannyml_production_rows",
          "Production prediction rows analysed in this run").set(
            summary.get("production_rows") or 0)

        g("nannyml_last_run_timestamp_seconds",
          "Unix timestamp of the last successful NannyML monitor run").set(
            datetime.utcnow().timestamp())

        push_to_gateway(PUSHGATEWAY_URL, job="nannyml_monitor", registry=reg)
        print(f"[nannyml] metrics pushed to {PUSHGATEWAY_URL}")
    except Exception as exc:
        print(f"[nannyml] pushgateway push failed (non-fatal): {exc}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[nannyml] run started at {datetime.utcnow().isoformat()}Z")

    # 1. Reference dataset (labelled, with model predictions)
    ref = _build_reference()

    # 2. Production data from Postgres
    prod = _load_production_data()
    if prod is None or len(prod) < MIN_PROD_ROWS:
        n = len(prod) if prod is not None else 0
        print(f"[nannyml] insufficient production data ({n} rows, need ≥{MIN_PROD_ROWS}) — exiting")
        return

    # 3. Chunk size: target ~5–8 chunks; minimum 50 rows each
    chunk_size = max(MIN_PROD_ROWS, len(prod) // 7)
    print(f"[nannyml] chunk_size={chunk_size}  ({len(prod) // chunk_size} chunks)")

    summary: dict = {
        "run_ts":          datetime.utcnow().isoformat() + "Z",
        "production_rows": len(prod),
        "chunk_size":      chunk_size,
    }

    # 4. CBPE — estimate performance without labels
    print("[nannyml] CBPE…")
    cbpe = run_cbpe(ref, prod, chunk_size)
    summary["cbpe_estimated_auc"] = cbpe["estimated_auc"]
    summary["cbpe_estimated_f1"]  = cbpe["estimated_f1"]
    summary["cbpe_n_alerts"]      = cbpe["n_alerts"]
    if cbpe["ok"] and cbpe["estimated_auc"] is not None:
        print(f"[nannyml] CBPE → AUC≈{cbpe['estimated_auc']:.4f}  "
              f"F1≈{(cbpe['estimated_f1'] or 0):.4f}  alerts={cbpe['n_alerts']}")
    elif cbpe["ok"]:
        print("[nannyml] CBPE ran but could not extract AUC — check column structure")

    # 5. Univariate drift
    print("[nannyml] univariate drift…")
    udrift = run_univariate_drift(ref, prod, DRIFT_FEATURES, chunk_size)
    summary["drifted_features_count"] = udrift["drifted_count"]
    summary["drifted_features"]       = udrift["drifted_features"]
    if udrift["ok"]:
        print(f"[nannyml] drift → {udrift['drifted_count']} features drifted: {udrift['drifted_features']}")

    # 6. Multivariate drift
    print("[nannyml] multivariate drift…")
    mvdrift = run_multivariate_drift(ref, prod, DRIFT_FEATURES, chunk_size)
    summary["reconstruction_error"] = mvdrift.get("reconstruction_error")

    # 7. Write summary JSON
    summary_path = REPORTS_DIR / "latest_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"[nannyml] summary → {summary_path}")

    # 8. Push metrics to Prometheus Pushgateway
    _push_metrics(summary)

    print(f"[nannyml] done  estimated_auc={summary.get('cbpe_estimated_auc')}  "
          f"drifted={summary.get('drifted_features_count')}")


if __name__ == "__main__":
    main()
