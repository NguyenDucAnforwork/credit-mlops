from __future__ import annotations

import numpy as np
import pandas as pd

from property_intelligence.avm import (
    compute_avm_metrics,
    evaluate_price_per_m2_baselines,
    evaluate_tabular_hgb_cohort_intervals,
    evaluate_tabular_hgb_intervals,
    evaluate_tabular_hgb_avm,
    evaluate_tabular_hgb_quantile_intervals,
    make_tabular_hgb_pipeline,
    temporal_split,
)


def _gold_frame():
    return pd.DataFrame(
        [
            {
                "published_at": "2025-06-01T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "property_type": "apartment",
                "price_vnd": 2_000_000_000,
                "area_m2": 50,
                "price_per_m2": 40_000_000,
                "floor_count": 5,
                "frontage_width": 5,
                "house_depth": 10,
                "road_width": 6,
                "bedroom_count": 2,
                "bathroom_count": 1,
                "published_month": 6,
                "published_quarter": 2,
                "ward": "Dịch Vọng",
                "house_direction": "",
                "balcony_direction": "",
            },
            {
                "published_at": "2025-10-01T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "property_type": "apartment",
                "price_vnd": 2_400_000_000,
                "area_m2": 60,
                "price_per_m2": 40_000_000,
                "floor_count": 5,
                "frontage_width": 5,
                "house_depth": 10,
                "road_width": 6,
                "bedroom_count": 2,
                "bathroom_count": 1,
                "published_month": 10,
                "published_quarter": 4,
                "ward": "Dịch Vọng",
                "house_direction": "",
                "balcony_direction": "",
            },
            {
                "published_at": "2025-11-15T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "property_type": "apartment",
                "price_vnd": 2_800_000_000,
                "area_m2": 70,
                "price_per_m2": 40_000_000,
                "floor_count": 5,
                "frontage_width": 5,
                "house_depth": 10,
                "road_width": 6,
                "bedroom_count": 2,
                "bathroom_count": 1,
                "published_month": 11,
                "published_quarter": 4,
                "ward": "Dịch Vọng",
                "house_direction": "",
                "balcony_direction": "",
            },
            {
                "published_at": "2025-11-20T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "property_type": "apartment",
                "price_vnd": 3_200_000_000,
                "area_m2": 80,
                "price_per_m2": 40_000_000,
                "floor_count": 5,
                "frontage_width": 5,
                "house_depth": 10,
                "road_width": 6,
                "bedroom_count": 2,
                "bathroom_count": 1,
                "published_month": 11,
                "published_quarter": 4,
                "ward": "Dịch Vọng",
                "house_direction": "",
                "balcony_direction": "",
            },
            {
                "published_at": "2025-12-15T00:00:00Z",
                "province": "Hồ Chí Minh",
                "district": "1",
                "property_type": "house",
                "price_vnd": 5_000_000_000,
                "area_m2": 50,
                "price_per_m2": 100_000_000,
                "floor_count": 3,
                "frontage_width": 4,
                "house_depth": 12,
                "road_width": 8,
                "bedroom_count": 4,
                "bathroom_count": 3,
                "published_month": 12,
                "published_quarter": 4,
                "ward": "Đa Kao",
                "house_direction": "",
                "balcony_direction": "",
            },
            {
                "published_at": "2025-12-20T00:00:00Z",
                "province": "Hồ Chí Minh",
                "district": "1",
                "property_type": "house",
                "price_vnd": 6_000_000_000,
                "area_m2": 60,
                "price_per_m2": 100_000_000,
                "floor_count": 3,
                "frontage_width": 4,
                "house_depth": 12,
                "road_width": 8,
                "bedroom_count": 4,
                "bathroom_count": 3,
                "published_month": 12,
                "published_quarter": 4,
                "ward": "Đa Kao",
                "house_direction": "",
                "balcony_direction": "",
            },
        ]
    )


def test_temporal_split_uses_contract_months():
    splits = temporal_split(_gold_frame())

    assert len(splits["train"]) == 2
    assert len(splits["validation"]) == 2
    assert len(splits["test"]) == 2


def test_compute_avm_metrics_reports_percentage_bands():
    metrics = compute_avm_metrics(
        "baseline",
        "test",
        pd.Series([100.0, 200.0]),
        np.array([110.0, 300.0]),
    )

    assert metrics.rows == 2
    assert metrics.within_10pct == 0.5
    assert metrics.within_20pct == 0.5
    assert metrics.mdape == 0.3


def test_evaluate_price_per_m2_baselines_returns_best_test_metric():
    report = evaluate_price_per_m2_baselines(_gold_frame())

    assert report["split_rows"] == {"train": 2, "validation": 2, "test": 2}
    assert len(report["metrics"]) == 6
    assert report["best_test_by_mdape"]["split_name"] == "test"


def test_tabular_hgb_pipeline_can_fit_and_evaluate_small_frame():
    report = evaluate_tabular_hgb_avm(_gold_frame(), random_state=7)

    assert report["model"] == "hist_gradient_boosting_log_price_per_m2"
    assert report["target"] == "log(price_per_m2)"
    assert report["random_state"] == 7
    assert len(report["metrics"]) == 2
    assert report["best_test_by_mdape"]["split_name"] == "test"


def test_tabular_hgb_intervals_reports_coverage_and_width():
    report = evaluate_tabular_hgb_intervals(_gold_frame(), random_state=7)

    assert report["interval"] == "validation_log_residual_q10_q90"
    assert report["target_coverage"] == 0.80
    assert 0.0 <= report["interval_metrics"]["coverage"] <= 1.0
    assert report["interval_metrics"]["median_interval_width_ratio"] >= 0.0
    assert report["point_metrics"]["split_name"] == "test"


def test_tabular_hgb_cohort_intervals_reports_fallback_usage():
    report = evaluate_tabular_hgb_cohort_intervals(
        _gold_frame(),
        cohort_columns=("property_type",),
        min_cohort_rows=1,
        random_state=7,
    )

    assert report["interval"] == "validation_log_residual_q10_q90_by_cohort"
    assert report["cohort_config"]["columns"] == ["property_type"]
    assert report["cohort_config"]["qualified_cohorts"] == 1
    assert report["cohort_config"]["test_rows_using_global_fallback"] == 2
    assert 0.0 <= report["interval_metrics"]["coverage"] <= 1.0
    assert report["interval_metrics"]["median_interval_width_ratio"] >= 0.0


def test_tabular_hgb_quantile_intervals_reports_validation_and_test_width():
    report = evaluate_tabular_hgb_quantile_intervals(_gold_frame(), random_state=7)

    assert report["interval"] == "hist_gradient_boosting_quantile_log_price_per_m2_q10_q90"
    assert report["target_coverage"] == 0.80
    assert 0.0 <= report["validation_interval_metrics"]["coverage"] <= 1.0
    assert 0.0 <= report["interval_metrics"]["coverage"] <= 1.0
    assert report["interval_metrics"]["median_interval_width_ratio"] >= 0.0
    assert report["point_metrics"]["split_name"] == "test"


def test_make_tabular_hgb_pipeline_has_preprocess_and_model_steps():
    pipeline = make_tabular_hgb_pipeline()

    assert list(pipeline.named_steps) == ["preprocess", "model"]
