from __future__ import annotations

import pandas as pd

from property_intelligence.monitoring import (
    build_property_monitoring_frame,
    evaluate_delayed_label_monitoring,
    evaluate_property_drift,
    inject_synthetic_property_drift,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "area_m2": [50.0, 60.0, 70.0, 80.0],
            "price_per_m2": [40_000_000.0, 42_000_000.0, 44_000_000.0, 46_000_000.0],
            "district": ["Cầu Giấy", "Cầu Giấy", "1", "1"],
            "property_type": ["apartment", "apartment", "house", "house"],
            "interval_width_ratio": [0.45, 0.50, 0.60, 0.65],
            "confidence": ["high", "medium", "medium", "low"],
        }
    )


def test_monitoring_frame_adds_missing_feature_share():
    frame = build_property_monitoring_frame(_frame())

    assert "missing_feature_share" in frame.columns
    assert frame["missing_feature_share"].max() == 0.0


def test_synthetic_drift_triggers_at_least_three_feature_alerts():
    reference = build_property_monitoring_frame(_frame())
    current = inject_synthetic_property_drift(reference)
    report = evaluate_property_drift(reference, current)

    assert report["status"] == "alert"
    assert report["shifted_feature_count"] >= 3
    assert {"area_m2", "price_per_m2", "interval_width_ratio"}.issubset(report["alert_features"])


def test_no_drift_returns_ok():
    reference = build_property_monitoring_frame(_frame())
    report = evaluate_property_drift(reference, reference.copy())

    assert report["status"] == "ok"
    assert report["alert_count"] == 0


def test_delayed_label_monitoring_reports_overall_and_cohort_alerts():
    predictions = pd.DataFrame(
        {
            "district": ["A", "A", "B", "B"],
            "property_type": ["apartment", "apartment", "house", "house"],
            "actual_value_vnd": [100.0, 100.0, 100.0, 100.0],
            "predicted_value_vnd": [100.0, 105.0, 170.0, 180.0],
            "comparable_count": [10, 10, 3, 3],
            "distance_status": ["not_available_missing_coordinates"] * 4,
        }
    )

    report = evaluate_delayed_label_monitoring(
        predictions,
        group_columns=("district", "property_type"),
        min_cohort_rows=2,
        cohort_mdape_alert_delta=0.10,
    )

    assert report["status"] == "alert"
    assert report["overall"]["rows"] == 4
    assert report["overall"]["distance_available_share"] == 0.0
    assert report["cohort_count"] == 2
    assert report["alerts"][0]["cohort"] == {"district": "B", "property_type": "house"}
