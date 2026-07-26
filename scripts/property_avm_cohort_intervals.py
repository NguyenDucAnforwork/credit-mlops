from __future__ import annotations

from pathlib import Path

import pandas as pd

from property_intelligence.avm import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    evaluate_tabular_hgb_cohort_intervals,
    write_avm_report,
)
from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    columns = sorted(
        set(
            [
                "published_at",
                "price_vnd",
                "price_per_m2",
                *NUMERIC_FEATURES,
                *CATEGORICAL_FEATURES,
            ]
        )
    )
    gold = pd.read_parquet(Path("data/gold") / snapshot_id / "listings_gold.parquet", columns=columns)
    report = evaluate_tabular_hgb_cohort_intervals(gold)
    reports_path = Path("reports/generated/avm_tabular_hgb_cohort_intervals_20260726.json")
    evidence_path = Path("docs/evidence/avm_tabular_hgb_cohort_intervals_20260726.json")
    write_avm_report(report, reports_path)
    write_avm_report(report, evidence_path)
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
