from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from property_intelligence.comparables import (
    COMPARABLE_COLUMNS,
    benchmark_comparable_queries,
    comparable_queries_from_frame,
)
from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    gold = pd.read_parquet(
        Path("data/gold") / snapshot_id / "listings_gold.parquet",
        columns=COMPARABLE_COLUMNS,
    )
    published = pd.to_datetime(gold["published_at"], utc=True)
    test = gold.loc[published >= pd.Timestamp("2025-12-01", tz="UTC")].sample(
        n=1000,
        random_state=42,
    )
    queries = comparable_queries_from_frame(test)
    report = {
        "snapshot_id": snapshot_id,
        "query_sample": {
            "rows": len(queries),
            "split": "published_at >= 2025-12-01",
            "random_state": 42,
        },
        **benchmark_comparable_queries(gold, queries),
    }
    reports_path = Path("reports/generated/property_comparables_fallback_benchmark_20260726.json")
    evidence_path = Path("docs/evidence/property_comparables_fallback_benchmark_20260726.json")
    for path in (reports_path, evidence_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
