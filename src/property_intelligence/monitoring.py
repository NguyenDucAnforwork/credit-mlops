from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DriftRule:
    feature: str
    metric: str
    threshold: float


DEFAULT_DRIFT_RULES = [
    DriftRule("area_m2", "relative_mean_change", 0.20),
    DriftRule("price_per_m2", "relative_mean_change", 0.20),
    DriftRule("interval_width_ratio", "absolute_mean_change", 0.10),
    DriftRule("confidence_low_share", "absolute_share_change", 0.10),
    DriftRule("missing_feature_share", "absolute_share_change", 0.05),
]


def build_property_monitoring_frame(listings: pd.DataFrame) -> pd.DataFrame:
    frame = listings.copy()
    frame["interval_width_ratio"] = frame.get("interval_width_ratio", 0.77)
    frame["confidence"] = frame.get("confidence", "low")
    feature_columns = ["area_m2", "price_per_m2", "district", "property_type"]
    frame["missing_feature_share"] = frame[feature_columns].isna().mean(axis=1)
    return frame


def inject_synthetic_property_drift(frame: pd.DataFrame) -> pd.DataFrame:
    drifted = frame.copy()
    drifted["area_m2"] = drifted["area_m2"] * 1.35
    drifted["price_per_m2"] = drifted["price_per_m2"] * 0.65
    drifted["interval_width_ratio"] = drifted["interval_width_ratio"] + 0.25
    drifted.loc[drifted.index[: max(1, len(drifted) // 3)], "district"] = pd.NA
    drifted["missing_feature_share"] = drifted[["area_m2", "price_per_m2", "district", "property_type"]].isna().mean(axis=1)
    drifted["confidence"] = "low"
    return drifted


def evaluate_property_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    rules: Iterable[DriftRule] = DEFAULT_DRIFT_RULES,
) -> dict:
    ref = build_property_monitoring_frame(reference)
    cur = build_property_monitoring_frame(current)
    checks = [_evaluate_rule(rule, ref, cur) for rule in rules]
    alerts = [check for check in checks if check["alert"]]
    return {
        "status": "alert" if alerts else "ok",
        "checks": checks,
        "alert_count": len(alerts),
        "alert_features": [alert["feature"] for alert in alerts],
        "shifted_feature_count": _shifted_feature_count(checks),
    }


def write_monitoring_report(report: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def _evaluate_rule(rule: DriftRule, reference: pd.DataFrame, current: pd.DataFrame) -> dict:
    if rule.metric == "relative_mean_change":
        ref_value = float(reference[rule.feature].mean())
        cur_value = float(current[rule.feature].mean())
        value = abs(cur_value - ref_value) / max(abs(ref_value), 1e-9)
    elif rule.metric == "absolute_mean_change":
        ref_value = float(reference[rule.feature].mean())
        cur_value = float(current[rule.feature].mean())
        value = abs(cur_value - ref_value)
    elif rule.metric == "absolute_share_change":
        if rule.feature == "confidence_low_share":
            ref_value = float((reference["confidence"] == "low").mean())
            cur_value = float((current["confidence"] == "low").mean())
        else:
            ref_value = float(reference[rule.feature].mean())
            cur_value = float(current[rule.feature].mean())
        value = abs(cur_value - ref_value)
    else:
        raise ValueError(f"Unsupported drift metric: {rule.metric}")
    return {
        "feature": rule.feature,
        "metric": rule.metric,
        "reference_value": ref_value,
        "current_value": cur_value,
        "value": value,
        "threshold": rule.threshold,
        "alert": bool(value > rule.threshold),
    }


def _shifted_feature_count(checks: list[dict]) -> int:
    return int(np.sum([check["alert"] for check in checks]))
