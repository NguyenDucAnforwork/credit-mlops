from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from statistics import median

import pandas as pd
from google.cloud import storage

from property_intelligence.avm import TabularHgbQuantileArtifact
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


def warm_avm_artifact() -> dict:
    artifact = _get_avm_artifact()
    if artifact is None:
        return {"status": "skipped", "reason": "AVM_ARTIFACT_PATH not configured"}
    return {
        "status": "ok",
        "model_version": artifact.metadata.get("model_version", "unknown"),
        "artifact_path": str(_avm_artifact_path()),
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
    artifact: TabularHgbQuantileArtifact | None = None
    artifact_prediction: dict | None = None
    artifact_warnings: list[str] = []
    try:
        artifact = _get_avm_artifact()
        if artifact is not None:
            artifact_prediction = artifact.predict_one(payload.model_dump())
    except Exception as exc:
        artifact_warnings.append(f"configured AVM artifact unavailable: {exc}")

    comparable_result = _get_comparable_index().query(query)
    comparables = comparable_result["comparables"]
    if artifact_prediction is not None:
        estimated_value = artifact_prediction["estimated_value_vnd"]
        estimated_ppm = artifact_prediction["estimated_price_per_m2"]
        lower_value = artifact_prediction["lower_value_vnd"]
        upper_value = artifact_prediction["upper_value_vnd"]
        interval_width_ratio = artifact_prediction["interval_width_ratio"]
        confidence = artifact_prediction["confidence"]
        warnings = comparable_result["warnings"] + artifact_warnings
        model_version = artifact.metadata.get("model_version", MODEL_VERSION) if artifact else MODEL_VERSION
        top_factors = [
            "HGB log(price_per_m2) tabular features",
            "q10/q90 quantile interval models",
            "area_m2 value scaling",
            "non-GIS comparable support metadata",
        ]
    elif not comparables:
        estimated_ppm = 0.0
        lower_ppm = 0.0
        upper_ppm = 0.0
        confidence = "low"
        warnings = comparable_result["warnings"] + artifact_warnings + ["no historical comparable support found"]
        estimated_value = estimated_ppm * query.area_m2
        lower_value = lower_ppm * query.area_m2
        upper_value = upper_ppm * query.area_m2
        interval_width_ratio = 1.0
        model_version = MODEL_VERSION
        top_factors = [
            "median historical comparable price_per_m2",
            "province/district/property_type match tier",
            "area tolerance",
            "listing recency",
        ]
    else:
        ppm_values = sorted(item["price_per_m2"] for item in comparables)
        estimated_ppm = float(median(ppm_values))
        lower_ppm = float(_quantile(ppm_values, 0.10))
        upper_ppm = float(_quantile(ppm_values, 0.90))
        confidence = comparable_result["support_level"]
        warnings = comparable_result["warnings"] + artifact_warnings
        estimated_value = estimated_ppm * query.area_m2
        lower_value = lower_ppm * query.area_m2
        upper_value = upper_ppm * query.area_m2
        interval_width_ratio = (upper_value - lower_value) / estimated_value if estimated_value > 0 else 1.0
        model_version = MODEL_VERSION
        top_factors = [
            "median historical comparable price_per_m2",
            "province/district/property_type match tier",
            "area tolerance",
            "listing recency",
        ]
    if interval_width_ratio > 0.8:
        confidence = "low"
    return {
        "estimated_value_vnd": estimated_value,
        "estimated_price_per_m2": estimated_ppm,
        "lower_value_vnd": lower_value,
        "upper_value_vnd": upper_value,
        "confidence": confidence,
        "interval_width_ratio": interval_width_ratio,
        "top_factors": top_factors,
        "comparables": comparables,
        "model_version": model_version,
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
    local_path = Path("data/gold") / DATA_SNAPSHOT_ID / "listings_gold.parquet"
    if local_path.exists():
        return local_path
    bucket_name = os.getenv("PROPERTY_DATA_BUCKET")
    if not bucket_name:
        return local_path
    cached_path = Path("/tmp/property-data") / DATA_SNAPSHOT_ID / "listings_gold.parquet"
    if not cached_path.exists():
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        storage.Client().bucket(bucket_name).blob(
            f"property/{DATA_SNAPSHOT_ID}/gold/listings.parquet"
        ).download_to_filename(cached_path)
    return cached_path


@lru_cache(maxsize=1)
def _get_avm_artifact() -> TabularHgbQuantileArtifact | None:
    path = _avm_artifact_path()
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Configured AVM artifact not found: {path}")
    return TabularHgbQuantileArtifact.load(path)


def _avm_artifact_path() -> Path | None:
    configured = os.getenv("AVM_ARTIFACT_PATH")
    return Path(configured) if configured else None


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    position = (len(values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight
