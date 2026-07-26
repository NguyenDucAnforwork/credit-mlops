from __future__ import annotations

from pathlib import Path

from property_intelligence.contracts import validate_hf_layers, write_contract_report
from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    report = validate_hf_layers(
        silver_path=Path("data/silver") / snapshot_id / "listings.parquet",
        gold_path=Path("data/gold") / snapshot_id / "listings_gold.parquet",
        quarantine_path=Path("data/quarantine") / snapshot_id / "listings_quarantine.parquet",
        snapshot_id=snapshot_id,
    )
    reports_path = Path("reports/generated/hf_vietnam_real_estates_contract_report_20260726.json")
    evidence_path = Path("docs/evidence/hf_contract_report_20260726.json")
    write_contract_report(report, reports_path)
    write_contract_report(report, evidence_path)
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
