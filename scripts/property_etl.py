from __future__ import annotations

from pathlib import Path

from property_intelligence.hf_etl import run_hf_silver_gold_etl, write_hf_etl_summary
from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    raw_dir = Path("data/raw/vietnam-real-estates") / snapshot_id
    summary = run_hf_silver_gold_etl(raw_dir, Path("data"), snapshot_id)
    output_path = Path("reports/generated/hf_vietnam_real_estates_etl_summary_20260726.json")
    evidence_path = Path("docs/evidence/hf_etl_summary_20260726.json")
    write_hf_etl_summary(summary, output_path)
    write_hf_etl_summary(summary, evidence_path)
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
