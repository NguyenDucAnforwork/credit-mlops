from __future__ import annotations

from pathlib import Path

import pandas as pd

from property_intelligence.avm import evaluate_price_per_m2_baselines, write_avm_report
from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    gold_path = Path("data/gold") / snapshot_id / "listings_gold.parquet"
    gold = pd.read_parquet(
        gold_path,
        columns=[
            "published_at",
            "province",
            "district",
            "property_type",
            "price_vnd",
            "area_m2",
            "price_per_m2",
        ],
    )
    report = evaluate_price_per_m2_baselines(gold)
    reports_path = Path("reports/generated/avm_baseline_metrics_20260726.json")
    evidence_path = Path("docs/evidence/avm_baseline_metrics_20260726.json")
    write_avm_report(report, reports_path)
    write_avm_report(report, evidence_path)
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
