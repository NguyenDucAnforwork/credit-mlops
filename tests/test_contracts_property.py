from __future__ import annotations

import json

import pandas as pd

from property_intelligence.contracts import validate_hf_layers, write_contract_report


def _silver():
    return pd.DataFrame(
        [
            {
                "listing_id": "1",
                "snapshot_id": "snap",
                "source_shard": "shard.parquet",
                "title": "A",
                "description": "",
                "property_type": "apartment",
                "province": "Hà Nội",
                "district": "Cầu Giấy",
                "ward": "",
                "street": "",
                "price_vnd": 2_000_000_000,
                "area_m2": 50,
                "published_at": pd.Timestamp("2025-01-01", tz="UTC"),
                "coordinate_status": "missing_source_columns",
                "latitude": pd.NA,
                "longitude": pd.NA,
            }
        ]
    )


def _gold():
    gold = _silver().copy()
    gold["price_per_m2"] = gold["price_vnd"] / gold["area_m2"]
    gold["published_year"] = 2025
    gold["published_month"] = 1
    gold["published_quarter"] = 1
    gold["city_key"] = "hà nội"
    gold["district_key"] = "cầu giấy"
    return gold


def test_validate_hf_layers_passes_core_checks_and_flags_coordinate_blocker(tmp_path):
    silver_path = tmp_path / "silver.parquet"
    gold_path = tmp_path / "gold.parquet"
    quarantine_path = tmp_path / "quarantine.parquet"
    _silver().to_parquet(silver_path, index=False)
    pd.concat([_gold()] * 3, ignore_index=True).to_parquet(gold_path, index=False)
    pd.DataFrame([{"quarantine_reason": "invalid_price"}]).to_parquet(quarantine_path, index=False)

    report = validate_hf_layers(silver_path, gold_path, quarantine_path, "snap", min_gold_rows=3)

    assert report.status == "pass_with_blockers"
    assert report.metrics["gold_rows"] == 3
    coordinate_check = next(check for check in report.checks if check.name == "coordinate_source_columns_present")
    assert coordinate_check.status == "fail"
    assert coordinate_check.severity == "blocker"


def test_validate_hf_layers_fails_core_row_threshold(tmp_path):
    silver_path = tmp_path / "silver.parquet"
    gold_path = tmp_path / "gold.parquet"
    quarantine_path = tmp_path / "quarantine.parquet"
    _silver().to_parquet(silver_path, index=False)
    _gold().to_parquet(gold_path, index=False)
    pd.DataFrame([{"quarantine_reason": "invalid_price"}]).to_parquet(quarantine_path, index=False)

    report = validate_hf_layers(silver_path, gold_path, quarantine_path, "snap")

    assert report.status == "fail"
    assert any(check.name == "gold_min_rows" and check.status == "fail" for check in report.checks)


def test_write_contract_report_serializes_checks(tmp_path):
    silver_path = tmp_path / "silver.parquet"
    gold_path = tmp_path / "gold.parquet"
    quarantine_path = tmp_path / "quarantine.parquet"
    _silver().to_parquet(silver_path, index=False)
    pd.concat([_gold()] * 3, ignore_index=True).to_parquet(gold_path, index=False)
    pd.DataFrame([{"quarantine_reason": "invalid_price"}]).to_parquet(quarantine_path, index=False)
    report = validate_hf_layers(silver_path, gold_path, quarantine_path, "snap", min_gold_rows=3)

    output_path = write_contract_report(report, tmp_path / "report.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["snapshot_id"] == "snap"
    assert payload["status"] == "pass_with_blockers"
    assert payload["metrics"]["gold_rows"] == 3
