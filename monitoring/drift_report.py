"""
Data drift monitoring with Evidently.
Compares production batch against training reference data.
Run daily (or triggered manually) to generate HTML drift reports.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

REPORTS_DIR = Path(__file__).parent / "reports"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

DRIFT_FEATURES = [
    "ENQUIRIES_3M",
    "ENQUIRIES_6M",
    "NUM_NEW_LOAN_TAKEN_3M",
    "NUM_NEW_LOAN_TAKEN_6M",
    "OUTSTANDING_BAL_LOAN_CURRENT",
    "OUTSTANDING_BAL_ALL_CURRENT",
    "NUMBER_OF_LOANS",
    "NUMBER_OF_CREDIT_CARDS",
    "CREDIT_CARD_MONTH_SINCE_30DPD",
    "CREDIT_CARD_NUMBER_OF_LATE_PAYMENT",
]


def generate_drift_report(
    production_data: pd.DataFrame,
    reference_path: Path = PROCESSED_DIR / "reference.csv",
    output_dir: Path = REPORTS_DIR,
) -> dict:
    """
    Run Evidently DataDriftPreset on provided production batch vs reference.
    Returns a summary dict with drift flags per feature.
    """
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset
    from evidently.metrics import DatasetMissingValuesSummaryMetric

    output_dir.mkdir(parents=True, exist_ok=True)
    reference_df = pd.read_csv(reference_path)

    # Only compare common drift features that exist in both datasets
    common_cols = [
        c for c in DRIFT_FEATURES
        if c in reference_df.columns and c in production_data.columns
    ]
    ref = reference_df[common_cols].copy()
    cur = production_data[common_cols].copy()

    report = Report(metrics=[
        DataDriftPreset(),
        DatasetMissingValuesSummaryMetric(),
    ])
    report.run(reference_data=ref, current_data=cur)

    today = date.today().isoformat()
    html_path = output_dir / f"drift_report_{today}.html"
    report.save_html(str(html_path))

    # Extract summary
    report_dict = report.as_dict()
    drift_results = {}
    for metric in report_dict.get("metrics", []):
        if metric.get("metric") == "DataDriftTable":
            for col, info in metric.get("result", {}).get("drift_by_columns", {}).items():
                drift_results[col] = {
                    "drift_detected": info.get("drift_detected", False),
                    "drift_score": round(info.get("drift_score", 0.0), 4),
                    "stattest": info.get("stattest_name", ""),
                }

    summary = {
        "date": today,
        "report_path": str(html_path),
        "n_drifted": sum(1 for v in drift_results.values() if v["drift_detected"]),
        "n_checked": len(drift_results),
        "features": drift_results,
    }

    summary_path = output_dir / f"drift_summary_{today}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[drift] {summary['n_drifted']}/{summary['n_checked']} features drifted → {html_path}")
    return summary


if __name__ == "__main__":
    # Quick self-test: use test set as a proxy for "production batch"
    test_df = pd.read_csv(PROCESSED_DIR / "test_data.csv")
    generate_drift_report(test_df.drop(columns=["label"], errors="ignore"))
