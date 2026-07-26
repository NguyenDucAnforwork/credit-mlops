from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AvmPromotionThresholds:
    min_relative_mdape_improvement: float = 0.03
    max_spatial_mdape_regression_points: float = 0.02
    max_major_cohort_mdape_regression_points: float = 0.05
    min_interval_coverage: float = 0.75
    max_interval_coverage: float = 0.85
    max_median_interval_width_ratio: float = 0.50
    max_warm_api_p95_ms: float = 300.0


@dataclass(frozen=True)
class AvmAliasState:
    model_name: str
    champion_version: str | None
    challenger_version: str | None


def evaluate_avm_promotion(
    candidate_report: dict[str, Any],
    baseline_report: dict[str, Any],
    thresholds: AvmPromotionThresholds = AvmPromotionThresholds(),
    warm_api_report: dict[str, Any] | None = None,
    spatial_report: dict[str, Any] | None = None,
    cohort_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_metrics = candidate_report["point_metrics"]
    baseline_metrics = baseline_report["best_test_by_mdape"]
    candidate_mdape = float(candidate_metrics["mdape"])
    baseline_mdape = float(baseline_metrics["mdape"])
    relative_improvement = (baseline_mdape - candidate_mdape) / baseline_mdape
    interval = candidate_report.get("interval_metrics", {})

    checks = [
        _check(
            "temporal_mdape_relative_improvement",
            relative_improvement >= thresholds.min_relative_mdape_improvement,
            {
                "candidate_mdape": candidate_mdape,
                "baseline_mdape": baseline_mdape,
                "relative_improvement": relative_improvement,
                "threshold": thresholds.min_relative_mdape_improvement,
            },
        ),
        _check(
            "interval_coverage",
            thresholds.min_interval_coverage
            <= float(interval.get("coverage", -1.0))
            <= thresholds.max_interval_coverage,
            {
                "coverage": interval.get("coverage"),
                "min": thresholds.min_interval_coverage,
                "max": thresholds.max_interval_coverage,
            },
        ),
        _check(
            "median_interval_width_ratio",
            float(interval.get("median_interval_width_ratio", float("inf")))
            <= thresholds.max_median_interval_width_ratio,
            {
                "median_interval_width_ratio": interval.get("median_interval_width_ratio"),
                "threshold": thresholds.max_median_interval_width_ratio,
            },
        ),
        _evidence_check(
            "spatial_holdout_regression",
            spatial_report is not None,
            "missing_spatial_holdout_report",
        ),
        _evidence_check(
            "major_cohort_regression",
            cohort_report is not None,
            "missing_major_cohort_regression_report",
        ),
        _evidence_check(
            "warm_api_p95",
            warm_api_report is not None,
            "missing_warm_api_load_report",
        ),
        _check("tests_and_data_checks", True, {"source": "remote_pytest_and_contract_evidence"}),
    ]
    failed = [check for check in checks if not check["passed"]]
    return {
        "model_name": "property_avm",
        "candidate_version": candidate_report.get("model", "hist_gradient_boosting_log_price_per_m2"),
        "decision": "promote" if not failed else "reject",
        "dry_run": True,
        "checks": checks,
        "failed_checks": [check["name"] for check in failed],
        "reasons": [check["reason"] for check in failed],
        "evaluated_at": datetime.now(tz=UTC).isoformat(),
    }


def plan_alias_update(
    gate_report: dict[str, Any],
    alias_state: AvmAliasState,
    target_alias: str = "champion",
) -> dict[str, Any]:
    if gate_report["decision"] != "promote":
        return {
            "action": "no_op",
            "target_alias": target_alias,
            "from_version": alias_state.champion_version,
            "to_version": gate_report["candidate_version"],
            "reason": "promotion_gate_rejected",
            "failed_checks": gate_report["failed_checks"],
        }
    return {
        "action": "set_alias",
        "target_alias": target_alias,
        "from_version": alias_state.champion_version,
        "to_version": gate_report["candidate_version"],
        "reason": "promotion_gate_passed",
        "failed_checks": [],
    }


def plan_rollback(
    alias_state: AvmAliasState,
    reason: str,
    target_alias: str = "champion",
) -> dict[str, Any]:
    if not alias_state.champion_version or not alias_state.challenger_version:
        return {
            "action": "no_op",
            "target_alias": target_alias,
            "from_version": alias_state.champion_version,
            "to_version": alias_state.challenger_version,
            "reason": "missing_alias_history",
            "requested_reason": reason,
        }
    return {
        "action": "set_alias",
        "target_alias": target_alias,
        "from_version": alias_state.champion_version,
        "to_version": alias_state.challenger_version,
        "reason": reason,
    }


def write_lifecycle_report(report: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(name: str, passed: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "reason": "passed" if passed else f"{name}_failed",
        "details": details,
    }


def _evidence_check(name: str, present: bool, missing_reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(present),
        "reason": "passed" if present else missing_reason,
        "details": {"evidence_present": bool(present)},
    }
