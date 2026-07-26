from __future__ import annotations

import pandas as pd

from property_intelligence.comparables import (
    ComparableQuery,
    NonGisComparableIndex,
    benchmark_comparable_queries,
    comparable_queries_from_frame,
)


def _listings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "listing_id": "a",
                "published_at": "2025-11-01T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "ward": "Dịch Vọng",
                "street": "Xuân Thủy",
                "project": "",
                "property_type": "apartment",
                "price_vnd": 2_000_000_000,
                "area_m2": 50,
                "price_per_m2": 40_000_000,
            },
            {
                "listing_id": "b",
                "published_at": "2025-11-10T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "ward": "Dịch Vọng",
                "street": "Xuân Thủy",
                "project": "",
                "property_type": "apartment",
                "price_vnd": 2_200_000_000,
                "area_m2": 55,
                "price_per_m2": 40_000_000,
            },
            {
                "listing_id": "future",
                "published_at": "2025-12-30T00:00:00Z",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "ward": "Dịch Vọng",
                "street": "Xuân Thủy",
                "project": "",
                "property_type": "apartment",
                "price_vnd": 2_400_000_000,
                "area_m2": 56,
                "price_per_m2": 42_857_143,
            },
            {
                "listing_id": "fallback",
                "published_at": "2025-11-15T00:00:00Z",
                "province": "Hà Nội",
                "district": "Nam Từ Liêm",
                "ward": "Mỹ Đình",
                "street": "",
                "project": "",
                "property_type": "apartment",
                "price_vnd": 2_100_000_000,
                "area_m2": 54,
                "price_per_m2": 38_888_889,
            },
        ]
    )


def test_non_gis_comparable_query_is_leakage_safe_and_labeled():
    index = NonGisComparableIndex(_listings())
    result = index.query(
        ComparableQuery(
            listing_id="subject",
            published_at="2025-12-01T00:00:00Z",
            province="Hà Nội",
            district="Cầu Giấy",
            property_type="apartment",
            area_m2=54,
        )
    )

    ids = {item["listing_id"] for item in result["comparables"]}
    assert {"a", "b", "fallback"}.issubset(ids)
    assert "future" not in ids
    assert result["distance_status"] == "not_available_missing_coordinates"
    assert result["support_level"] == "medium"
    assert all(item["distance_m"] is None for item in result["comparables"])


def test_comparable_benchmark_reports_latency_and_support():
    queries = comparable_queries_from_frame(_listings().tail(1))
    summary = benchmark_comparable_queries(_listings(), queries)

    assert summary["method"] == "non_gis_pandas_comparable_fallback"
    assert summary["query_count"] == 1
    assert summary["valid_request_error_rate"] == 0.0
    assert summary["latency_ms"]["p95"] >= 0.0
    assert summary["postgis_criterion_status"] == "blocked_missing_coordinates_and_postgis"
