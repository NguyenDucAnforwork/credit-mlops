from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from property_intelligence.crawler import FixtureListingAdapter
from property_intelligence.etl import (
    build_gold,
    build_silver,
    deterministic_listing_id,
    incremental_load,
    normalize_property_type,
    normalize_text,
    write_bronze_snapshot,
)


def _record(i: int, **overrides):
    base = {
        "source_id": f"listing-{i}",
        "title": f"Can ho so {i}",
        "province": "Ha Noi",
        "district": "Cau Giay",
        "property_type": "apartment",
        "price_vnd": 2_500_000_000 + i * 1_000_000,
        "area_m2": 50 + (i % 20),
        "latitude": 21.03 + (i % 10) * 0.001,
        "longitude": 105.78 + (i % 10) * 0.001,
        "listed_at": "2025-10-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_fixture_adapter_resumes_from_checkpoint():
    adapter = FixtureListingAdapter([_record(i) for i in range(5)])

    assert [row["source_id"] for row in adapter.iter_records(checkpoint="2")] == [
        "listing-2",
        "listing-3",
        "listing-4",
    ]
    batch = adapter.crawl()
    assert batch.source_name == "fixture"
    assert batch.parser_version == "fixture-v1"
    assert batch.checkpoint == "5"


def test_bronze_snapshot_is_deterministic_for_same_payload_and_time(tmp_path):
    captured_at = datetime(2025, 1, 1, tzinfo=UTC)
    first = write_bronze_snapshot([_record(1)], tmp_path, "fixture", "v1", captured_at)
    second = write_bronze_snapshot([_record(1)], tmp_path, "fixture", "v1", captured_at)

    assert first.snapshot_id == second.snapshot_id
    assert first.sha256 == second.sha256
    assert first.row_count == 1
    assert first.raw_path.read_text(encoding="utf-8").count("\n") == 1


def test_silver_normalizes_valid_rows_and_quarantines_bad_rows(tmp_path):
    bronze = write_bronze_snapshot(
        [
            _record(1, property_type="can ho", title="  Nice   apartment "),
            _record(1, property_type="can ho"),
            _record(2, latitude=99.0),
            _record(3, price_vnd=0),
        ],
        tmp_path,
        "fixture",
        "v1",
        datetime(2025, 1, 1, tzinfo=UTC),
    )

    silver = build_silver(bronze, tmp_path)
    df = pd.read_parquet(silver.output_path)
    quarantine = pd.read_parquet(silver.quarantine_path)

    assert silver.row_count == 1
    assert silver.quarantine_count == 3
    assert silver.duplicate_count == 1
    assert df.loc[0, "property_type"] == "apartment"
    assert df.loc[0, "title"] == "Nice apartment"
    assert set(quarantine["quarantine_reason"]) == {
        "duplicate_in_snapshot",
        "invalid_coordinates",
        "invalid_price",
    }


def test_gold_adds_price_time_and_cell_features(tmp_path):
    bronze = write_bronze_snapshot([_record(10)], tmp_path, "fixture", "v1")
    silver = build_silver(bronze, tmp_path)
    gold = build_gold(silver, tmp_path)
    df = pd.read_parquet(gold.output_path)

    assert gold.row_count == 1
    assert df.loc[0, "price_per_m2"] > 0
    assert df.loc[0, "listed_year"] == 2025
    assert df.loc[0, "listed_month"] == 10
    assert df.loc[0, "h3_r7"].startswith("r7_")
    assert df.loc[0, "h3_r8"].startswith("r8_")
    assert df.loc[0, "h3_r9"].startswith("r9_")


def test_incremental_fixture_counts_1000_inserts_and_100_duplicates(tmp_path):
    existing = {_listing_id(i) for i in range(100)}
    new_unique = [_record(i + 100) for i in range(1000)]
    duplicates = [_record(i) for i in range(100)]
    records = new_unique + duplicates

    result = incremental_load(records, existing, tmp_path / "incremental.parquet")
    df = pd.read_parquet(result.output_path)

    assert result.inserts == 1000
    assert result.duplicates == 100
    assert len(df) == 1000
    assert df["listing_id"].is_unique


def test_second_identical_incremental_run_inserts_zero(tmp_path):
    records = [_record(i) for i in range(25)]
    first = incremental_load(records, set(), tmp_path / "first.parquet")
    existing = set(pd.read_parquet(first.output_path)["listing_id"])
    second = incremental_load(records, existing, tmp_path / "second.parquet")

    assert first.inserts == 25
    assert second.inserts == 0
    assert second.duplicates == 25


def test_text_and_property_type_normalization():
    assert normalize_text("  A   B  ") == "A B"
    assert normalize_property_type("nhà") == "house"
    assert normalize_property_type("đất") == "land"


def test_listing_id_is_stable_for_equivalent_numeric_values():
    left = _record(7, price_vnd=2500000000, area_m2=50)
    right = _record(7, price_vnd=2500000000.0, area_m2=50.0)

    assert deterministic_listing_id(left) == deterministic_listing_id(right)


def test_bronze_snapshot_id_changes_with_payload(tmp_path):
    captured_at = datetime(2025, 1, 1, tzinfo=UTC)
    first = write_bronze_snapshot([_record(1)], tmp_path, "fixture", "v1", captured_at)
    second = write_bronze_snapshot([_record(2)], tmp_path, "fixture", "v1", captured_at)

    assert first.snapshot_id != second.snapshot_id


def test_bronze_snapshot_id_changes_with_capture_time(tmp_path):
    first = write_bronze_snapshot(
        [_record(1)],
        tmp_path,
        "fixture",
        "v1",
        datetime(2025, 1, 1, tzinfo=UTC),
    )
    second = write_bronze_snapshot(
        [_record(1)],
        tmp_path,
        "fixture",
        "v1",
        datetime(2025, 1, 1, tzinfo=UTC) + timedelta(seconds=1),
    )

    assert first.snapshot_id != second.snapshot_id


def _listing_id(i: int) -> str:
    return deterministic_listing_id(_record(i))
