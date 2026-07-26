from __future__ import annotations

from pathlib import Path

from property_intelligence.lifecycle import (
    AvmAliasState,
    evaluate_avm_promotion,
    plan_alias_update,
    plan_rollback,
    write_lifecycle_report,
)


def _candidate(width: float = 0.7699, coverage: float = 0.7867) -> dict:
    return {
        "model": "hist_gradient_boosting_log_price_per_m2",
        "point_metrics": {
            "mdape": 0.1916,
        },
        "interval_metrics": {
            "coverage": coverage,
            "median_interval_width_ratio": width,
        },
    }


def _baseline() -> dict:
    return {
        "best_test_by_mdape": {
            "mdape": 0.2285,
        }
    }


def test_promotion_gate_rejects_current_width_and_missing_evidence():
    report = evaluate_avm_promotion(_candidate(), _baseline())

    assert report["decision"] == "reject"
    assert report["dry_run"] is True
    assert "median_interval_width_ratio" in report["failed_checks"]
    assert "spatial_holdout_regression" in report["failed_checks"]
    assert "major_cohort_regression" in report["failed_checks"]
    assert "warm_api_p95" in report["failed_checks"]


def test_promotion_gate_passes_when_all_evidence_satisfies_thresholds():
    report = evaluate_avm_promotion(
        _candidate(width=0.40),
        _baseline(),
        warm_api_report={"p95_ms": 250},
        spatial_report={"mdape_regression_points": 0.0},
        cohort_report={"max_major_cohort_regression_points": 0.0},
    )

    assert report["decision"] == "promote"
    assert report["failed_checks"] == []


def test_promotion_gate_rejects_when_coverage_is_outside_band():
    report = evaluate_avm_promotion(
        _candidate(width=0.40, coverage=0.90),
        _baseline(),
        warm_api_report={"p95_ms": 250},
        spatial_report={"mdape_regression_points": 0.0},
        cohort_report={"max_major_cohort_regression_points": 0.0},
    )

    assert report["decision"] == "reject"
    assert report["failed_checks"] == ["interval_coverage"]


def test_alias_update_is_no_op_when_gate_rejects():
    gate = evaluate_avm_promotion(_candidate(), _baseline())
    plan = plan_alias_update(
        gate,
        AvmAliasState(
            model_name="property_avm",
            champion_version="v1",
            challenger_version="v2",
        ),
    )

    assert plan["action"] == "no_op"
    assert plan["reason"] == "promotion_gate_rejected"
    assert plan["from_version"] == "v1"


def test_alias_update_sets_champion_when_gate_passes():
    gate = evaluate_avm_promotion(
        _candidate(width=0.40),
        _baseline(),
        warm_api_report={"p95_ms": 250},
        spatial_report={"mdape_regression_points": 0.0},
        cohort_report={"max_major_cohort_regression_points": 0.0},
    )
    plan = plan_alias_update(
        gate,
        AvmAliasState(
            model_name="property_avm",
            champion_version="v1",
            challenger_version="v2",
        ),
    )

    assert plan["action"] == "set_alias"
    assert plan["target_alias"] == "champion"


def test_rollback_plan_requires_alias_history():
    plan = plan_rollback(
        AvmAliasState(
            model_name="property_avm",
            champion_version="v2",
            challenger_version=None,
        ),
        reason="bad calibration",
    )

    assert plan["action"] == "no_op"
    assert plan["reason"] == "missing_alias_history"


def test_rollback_plan_targets_previous_challenger():
    plan = plan_rollback(
        AvmAliasState(
            model_name="property_avm",
            champion_version="v2",
            challenger_version="v1",
        ),
        reason="bad calibration",
    )

    assert plan["action"] == "set_alias"
    assert plan["from_version"] == "v2"
    assert plan["to_version"] == "v1"


def test_write_lifecycle_report_round_trips_json(tmp_path: Path):
    output = write_lifecycle_report({"decision": "reject"}, tmp_path / "gate.json")

    assert output.read_text(encoding="utf-8").strip() == '{\n  "decision": "reject"\n}'
