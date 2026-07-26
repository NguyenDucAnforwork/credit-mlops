from __future__ import annotations

from pathlib import Path
from statistics import median

import pandas as pd

from property_intelligence.comparables import COMPARABLE_COLUMNS, NonGisComparableIndex, comparable_queries_from_frame
from property_intelligence.monitoring import evaluate_delayed_label_monitoring, write_monitoring_report
from property_intelligence.sources import fetch_hf_dataset_metadata


SAMPLE_ROWS = 2000


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    gold = pd.read_parquet(
        Path("data/gold") / snapshot_id / "listings_gold.parquet",
        columns=COMPARABLE_COLUMNS,
    )
    published = pd.to_datetime(gold["published_at"], utc=True)
    labels = gold.loc[published >= pd.Timestamp("2025-12-01", tz="UTC")].sample(
        n=SAMPLE_ROWS,
        random_state=42,
    )
    index = NonGisComparableIndex(gold)
    prediction_rows = []
    for row, query in zip(labels.itertuples(index=False), comparable_queries_from_frame(labels), strict=True):
        result = index.query(query)
        comparables = result["comparables"]
        if comparables:
            predicted_ppm = float(median(item["price_per_m2"] for item in comparables))
            predicted_value = predicted_ppm * float(row.area_m2)
        else:
            predicted_ppm = 0.0
            predicted_value = 0.0
        prediction_rows.append(
            {
                "listing_id": row.listing_id,
                "district": row.district,
                "property_type": row.property_type,
                "actual_value_vnd": float(row.price_vnd),
                "predicted_value_vnd": predicted_value,
                "predicted_price_per_m2": predicted_ppm,
                "comparable_count": result["count"],
                "distance_status": result["distance_status"],
            }
        )

    predictions = pd.DataFrame(prediction_rows)
    report = {
        "snapshot_id": snapshot_id,
        "label_sample": {
            "rows": len(predictions),
            "split": "published_at >= 2025-12-01",
            "random_state": 42,
            "prediction_source": "non_gis_comparable_fallback",
        },
        **evaluate_delayed_label_monitoring(
            predictions,
            group_columns=("district", "property_type"),
            min_cohort_rows=50,
            cohort_mdape_alert_delta=0.05,
        ),
    }
    reports_path = Path("reports/generated/property_delayed_label_monitoring_20260726.json")
    evidence_path = Path("docs/evidence/property_delayed_label_monitoring_20260726.json")
    write_monitoring_report(report, reports_path)
    write_monitoring_report(report, evidence_path)
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
