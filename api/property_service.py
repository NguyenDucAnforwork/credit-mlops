from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from statistics import median

import pandas as pd

from property_intelligence.comparables import (
    COMPARABLE_COLUMNS,
    ComparableQuery,
    NonGisComparableIndex,
)


MODEL_VERSION = "non_gis_comparable_fallback_experimental_20260726"
FEATURE_VERSION = "property_non_gis_v1"
DATA_SNAPSHOT_ID = "a9a66ffa985edcf76b4be59ae2c6f5b1db889c38"


def warm_property_index() -> dict:
    index = _get_comparable_index()
    return {
        "status": "ok",
        "gold_path": str(_gold_path()),
        "listing_rows": len(index.listings),
    }


def make_comparable_query(payload) -> ComparableQuery:
    return ComparableQuery(
        listing_id=getattr(payload, "listing_id", None),
        published_at=getattr(payload, "published_at"),
        province=getattr(payload, "province"),
        district=getattr(payload, "district"),
        property_type=getattr(payload, "property_type"),
        area_m2=float(getattr(payload, "area_m2")),
    )


def predict_avm(payload, trace_id: str, latency_ms: float) -> dict:
    query = make_comparable_query(payload)
    comparable_result = _get_comparable_index().query(query)
    comparables = comparable_result["comparables"]
    if not comparables:
        estimated_ppm = 0.0
        lower_ppm = 0.0
        upper_ppm = 0.0
        confidence = "low"
        warnings = comparable_result["warnings"] + ["no historical comparable support found"]
    else:
        ppm_values = sorted(item["price_per_m2"] for item in comparables)
        estimated_ppm = float(median(ppm_values))
        lower_ppm = float(_quantile(ppm_values, 0.10))
        upper_ppm = float(_quantile(ppm_values, 0.90))
        confidence = comparable_result["support_level"]
        warnings = comparable_result["warnings"]

    estimated_value = estimated_ppm * query.area_m2
    lower_value = lower_ppm * query.area_m2
    upper_value = upper_ppm * query.area_m2
    interval_width_ratio = (upper_value - lower_value) / estimated_value if estimated_value > 0 else 1.0
    if interval_width_ratio > 0.8:
        confidence = "low"
    return {
        "estimated_value_vnd": estimated_value,
        "estimated_price_per_m2": estimated_ppm,
        "lower_value_vnd": lower_value,
        "upper_value_vnd": upper_value,
        "confidence": confidence,
        "interval_width_ratio": interval_width_ratio,
        "top_factors": [
            "median historical comparable price_per_m2",
            "province/district/property_type match tier",
            "area tolerance",
            "listing recency",
        ],
        "comparables": comparables,
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "data_snapshot_id": DATA_SNAPSHOT_ID,
        "trace_id": trace_id,
        "latency_ms": latency_ms,
        "disclaimer": "Experimental listing-based AVM fallback; not a promoted production valuation.",
        "warnings": warnings,
    }


def make_lending_decision(
    credit_decision: str,
    loan_amount_vnd: float,
    lower_value_vnd: float,
    confidence: str,
    ood: bool = False,
) -> dict:
    conservative_ltv = loan_amount_vnd / lower_value_vnd if lower_value_vnd > 0 else float("inf")
    reasons: list[str] = []
    if credit_decision == "reject":
        decision = "reject"
        reasons.append("credit_reject")
    elif conservative_ltv > 0.85:
        decision = "reject"
        reasons.append("conservative_ltv_above_0_85")
    elif credit_decision == "manual_review":
        decision = "manual_review"
        reasons.append("credit_manual_review")
    elif conservative_ltv > 0.75:
        decision = "manual_review"
        reasons.append("conservative_ltv_above_0_75")
    elif confidence == "low":
        decision = "manual_review"
        reasons.append("low_avm_confidence")
    elif ood:
        decision = "manual_review"
        reasons.append("ood")
    else:
        decision = "approve"
        reasons.append("credit_approve_and_ltv_at_or_below_0_75")
    return {
        "decision": decision,
        "conservative_ltv": conservative_ltv,
        "reasons": reasons,
    }


@lru_cache(maxsize=1)
def _get_comparable_index() -> NonGisComparableIndex:
    path = _gold_path()
    if not path.exists():
        raise FileNotFoundError(f"Property gold parquet not found: {path}")
    gold = pd.read_parquet(path, columns=COMPARABLE_COLUMNS)
    return NonGisComparableIndex(gold)


def _gold_path() -> Path:
    configured = os.getenv("PROPERTY_GOLD_PATH")
    if configured:
        return Path(configured)
    return Path("data/gold") / DATA_SNAPSHOT_ID / "listings_gold.parquet"


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight
