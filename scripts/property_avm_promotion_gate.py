from __future__ import annotations

from pathlib import Path

from property_intelligence.lifecycle import (
    AvmAliasState,
    evaluate_avm_promotion,
    load_json,
    plan_alias_update,
    plan_rollback,
    write_lifecycle_report,
)


def main() -> None:
    candidate = load_json(Path("reports/generated/avm_tabular_hgb_quantile_intervals_20260726.json"))
    baseline = load_json(Path("reports/generated/avm_baseline_metrics_20260726.json"))
    gate = evaluate_avm_promotion(candidate, baseline)
    alias_state = AvmAliasState(
        model_name="property_avm",
        champion_version=None,
        challenger_version=gate["candidate_version"],
    )
    report = {
        "gate": gate,
        "alias_update_plan": plan_alias_update(gate, alias_state),
        "rollback_plan": plan_rollback(
            alias_state,
            reason="dry-run rollback check before any promoted AVM alias exists",
        ),
        "registry_status": "dry_run_no_mlflow_mutation",
    }
    reports_path = Path("reports/generated/property_avm_promotion_gate_20260726.json")
    evidence_path = Path("docs/evidence/property_avm_promotion_gate_20260726.json")
    write_lifecycle_report(report, reports_path)
    write_lifecycle_report(report, evidence_path)
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
