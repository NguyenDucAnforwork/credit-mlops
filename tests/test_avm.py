from __future__ import annotations

import numpy as np
import pandas as pd

from property_intelligence.avm import (
    compute_avm_metrics,
    evaluate_price_per_m2_baselines,
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
            },
            {
                "published_at": "2025-10-01T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "property_type": "apartment",
                "price_vnd": 2_400_000_000,
                "area_m2": 60,
                "price_per_m2": 40_000_000,
            },
            {
                "published_at": "2025-11-15T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "property_type": "apartment",
                "price_vnd": 2_800_000_000,
                "area_m2": 70,
                "price_per_m2": 40_000_000,
            },
            {
                "published_at": "2025-11-20T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "property_type": "apartment",
                "price_vnd": 3_200_000_000,
                "area_m2": 80,
                "price_per_m2": 40_000_000,
            },
            {
                "published_at": "2025-12-15T00:00:00Z",
                "province": "Hồ Chí Minh",
                "district": "1",
                "property_type": "house",
                "price_vnd": 5_000_000_000,
                "area_m2": 50,
                "price_per_m2": 100_000_000,
            },
            {
                "published_at": "2025-12-20T00:00:00Z",
                "province": "Hồ Chí Minh",
                "district": "1",
                "property_type": "house",
                "price_vnd": 6_000_000_000,
                "area_m2": 60,
                "price_per_m2": 100_000_000,
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
