from __future__ import annotations

from pathlib import Path

import pandas as pd

from property_intelligence.monitoring import (
    build_property_monitoring_frame,
    evaluate_property_drift,
    inject_synthetic_property_drift,
    write_monitoring_report,
)
from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    columns = [
        "published_at",
        "area_m2",
        "price_per_m2",
        "district",
        "property_type",
    ]
    gold = pd.read_parquet(Path("data/gold") / snapshot_id / "listings_gold.parquet", columns=columns)
    published = pd.to_datetime(gold["published_at"], utc=True)
    reference = gold.loc[published < pd.Timestamp("2025-11-01", tz="UTC")].sample(
        n=5000,
        random_state=42,
    )
    current = inject_synthetic_property_drift(build_property_monitoring_frame(reference))
    report = {
        "snapshot_id": snapshot_id,
        "reference_rows": len(reference),
        "current_rows": len(current),
        "synthetic_shifted_features": [
            "area_m2",
            "price_per_m2",
            "interval_width_ratio",
            "district_missingness",
            "confidence",
        ],
        **evaluate_property_drift(reference, current),
    }
    reports_path = Path("reports/generated/property_monitoring_synthetic_drift_20260726.json")
    evidence_path = Path("docs/evidence/property_monitoring_synthetic_drift_20260726.json")
    write_monitoring_report(report, reports_path)
    write_monitoring_report(report, evidence_path)
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
