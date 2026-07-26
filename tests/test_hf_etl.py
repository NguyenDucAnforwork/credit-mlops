from __future__ import annotations

import json

import pandas as pd

from property_intelligence.hf_etl import (
    build_hf_gold,
    normalize_hf_frame,
    run_hf_silver_gold_etl,
    write_hf_etl_summary,
)


def _raw_frame():
    return pd.DataFrame(
        [
            {
                "name": "  Căn hộ A  ",
                "description": "  Mô tả  ",
                "property_type_name": "Căn hộ",
                "province_name": "Hà Nội",
                "district_name": "Cầu Giấy",
                "ward_name": "Dịch Vọng",
                "street_name": "Xuân Thủy",
                "project_name": "Dự án",
                "price": 2_000_000_000,
                "area": 50,
                "floor_count": 10,
                "frontage_width": None,
                "house_depth": None,
                "road_width": None,
                "bedroom_count": 2,
                "bathroom_count": 2,
                "house_direction": None,
                "balcony_direction": None,
                "published_at": "2025-10-01T00:00:00Z",
            },
            {
                "name": "Nhà B",
                "description": "",
                "property_type_name": "Nhà",
                "province_name": "Đà Nẵng",
                "district_name": "Hải Châu",
                "ward_name": "",
                "street_name": "",
                "project_name": "",
                "price": 0,
                "area": 80,
                "floor_count": None,
                "frontage_width": None,
                "house_depth": None,
                "road_width": None,
                "bedroom_count": None,
                "bathroom_count": None,
                "house_direction": None,
                "balcony_direction": None,
                "published_at": "2025-10-01T00:00:00Z",
            },
        ]
    )


def test_normalize_hf_frame_maps_actual_dataset_schema():
    normalized = normalize_hf_frame(_raw_frame(), "shard.parquet", "snapshot-1")

    assert normalized.loc[0, "title"] == "Căn hộ A"
    assert normalized.loc[0, "property_type"] == "apartment"
    assert normalized.loc[0, "coordinate_status"] == "missing_source_columns"
    assert normalized.loc[0, "quarantine_reason"] is pd.NA
    assert normalized.loc[1, "quarantine_reason"] == "invalid_price"


def test_build_hf_gold_filters_mvp_cities_and_adds_features():
    normalized = normalize_hf_frame(_raw_frame(), "shard.parquet", "snapshot-1")
    silver = normalized.loc[normalized["quarantine_reason"].isna()].drop(columns=["quarantine_reason"])
    gold = build_hf_gold(silver)

    assert len(gold) == 1
    assert gold.loc[0, "price_per_m2"] == 40_000_000
    assert gold.loc[0, "published_year"] == 2025
    assert gold.loc[0, "city_key"] == "hà nội"


def test_run_hf_silver_gold_etl_writes_layers(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _raw_frame().to_parquet(raw_dir / "shard_0000.parquet", index=False)

    summary = run_hf_silver_gold_etl(raw_dir, tmp_path / "layers", "snapshot-1")
    write_hf_etl_summary(summary, tmp_path / "summary.json")
    payload = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert payload["raw_rows"] == 2
    assert payload["silver_rows"] == 1
    assert payload["gold_rows"] == 1
    assert payload["quarantine_rows"] == 1
    assert payload["missing_coordinate_columns"] == ["latitude", "longitude"]
    assert pd.read_parquet(summary.silver_path).loc[0, "coordinate_status"] == "missing_source_columns"
