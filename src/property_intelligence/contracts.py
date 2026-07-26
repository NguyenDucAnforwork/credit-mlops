from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_SILVER_COLUMNS = {
    "listing_id",
    "snapshot_id",
    "source_shard",
    "title",
    "description",
    "property_type",
    "province",
    "district",
    "ward",
    "street",
    "price_vnd",
    "area_m2",
    "published_at",
    "coordinate_status",
}

REQUIRED_GOLD_COLUMNS = REQUIRED_SILVER_COLUMNS | {
    "price_per_m2",
    "published_year",
    "published_month",
    "published_quarter",
    "city_key",
    "district_key",
}

MVP_CITIES = {"Hà Nội", "Hồ Chí Minh"}


@dataclass(frozen=True)
class ContractCheck:
    name: str
    status: str
    observed: object
    expected: object
    severity: str = "error"


@dataclass(frozen=True)
class ContractReport:
    snapshot_id: str
    status: str
    checks: list[ContractCheck]
    metrics: dict[str, object]


def validate_hf_layers(
    silver_path: Path,
    gold_path: Path,
    quarantine_path: Path,
    snapshot_id: str,
    min_gold_rows: int = 500_000,
) -> ContractReport:
    silver = pd.read_parquet(silver_path)
    gold = pd.read_parquet(gold_path)
    quarantine = pd.read_parquet(quarantine_path)
    checks = [
        _column_check("silver_required_columns", silver.columns, REQUIRED_SILVER_COLUMNS),
        _column_check("gold_required_columns", gold.columns, REQUIRED_GOLD_COLUMNS),
        _pass_fail("silver_listing_id_unique", bool(silver["listing_id"].is_unique), True),
        _pass_fail("gold_mvp_city_filter", set(gold["province"].dropna().unique()) <= MVP_CITIES, True),
        _pass_fail("gold_min_rows", len(gold), f">={min_gold_rows}", len(gold) >= min_gold_rows),
        _pass_fail("silver_positive_price", bool((silver["price_vnd"] > 0).all()), True),
        _pass_fail("silver_positive_area", bool((silver["area_m2"] > 0).all()), True),
        _pass_fail("gold_positive_price_per_m2", bool((gold["price_per_m2"] > 0).all()), True),
        _pass_fail("quarantine_has_reason", bool(quarantine["quarantine_reason"].notna().all()), True),
        ContractCheck(
            name="coordinate_source_columns_present",
            status="fail",
            observed=["latitude", "longitude"]
            if _has_real_coordinates(silver)
            else "missing_source_columns",
            expected=["latitude", "longitude"],
            severity="blocker",
        ),
    ]
    metrics = {
        "silver_rows": len(silver),
        "gold_rows": len(gold),
        "quarantine_rows": len(quarantine),
        "mvp_city_counts": gold["province"].value_counts(dropna=False).to_dict(),
        "property_type_counts": gold["property_type"].value_counts(dropna=False).to_dict(),
        "quarantine_reason_counts": quarantine["quarantine_reason"].value_counts(dropna=False).to_dict(),
        "price_per_m2_min": float(gold["price_per_m2"].min()) if not gold.empty else None,
        "price_per_m2_median": float(gold["price_per_m2"].median()) if not gold.empty else None,
        "price_per_m2_max": float(gold["price_per_m2"].max()) if not gold.empty else None,
    }
    hard_failures = [check for check in checks if check.status != "pass" and check.severity == "error"]
    status = "pass_with_blockers" if not hard_failures else "fail"
    return ContractReport(snapshot_id=snapshot_id, status=status, checks=checks, metrics=metrics)


def write_contract_report(report: ContractReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "snapshot_id": report.snapshot_id,
        "status": report.status,
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "observed": check.observed,
                "expected": check.expected,
                "severity": check.severity,
            }
            for check in report.checks
        ],
        "metrics": report.metrics,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return output_path


def _column_check(name: str, columns: pd.Index, required: set[str]) -> ContractCheck:
    missing = sorted(required - set(columns))
    return ContractCheck(
        name=name,
        status="pass" if not missing else "fail",
        observed={"missing": missing},
        expected=sorted(required),
    )


def _pass_fail(name: str, observed: object, expected: object, passed: bool | None = None) -> ContractCheck:
    if passed is None:
        passed = observed == expected
    return ContractCheck(name=name, status="pass" if passed else "fail", observed=observed, expected=expected)


def _has_real_coordinates(silver: pd.DataFrame) -> bool:
    if "latitude" not in silver.columns or "longitude" not in silver.columns:
        return False
    return bool(silver["latitude"].notna().any() and silver["longitude"].notna().any())
