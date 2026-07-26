from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    gold_path = Path("data/gold") / metadata.revision / "listings_gold.parquet"
    os.environ["PROPERTY_GOLD_PATH"] = str(gold_path)
    sys.path.insert(0, str(Path("api").resolve()))
    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    property_payload = {
        "published_at": "2025-12-15T00:00:00Z",
        "province": "Hà Nội",
        "district": "Cầu Giấy",
        "property_type": "apartment",
        "area_m2": 55,
    }
    timings: dict[str, float] = {}
    responses: dict[str, dict] = {}
    for name, method, path, kwargs in [
        ("comparables", "get", "/v1/comparables", {"params": property_payload}),
        ("avm", "post", "/v1/avm/predict", {"json": property_payload}),
        (
            "lending",
            "post",
            "/v1/lending/decision",
            {
                "json": {
                    "credit_decision": "approve",
                    "loan_amount_vnd": 1_500_000_000,
                    "lower_value_vnd": 2_000_000_000,
                    "confidence": "high",
                }
            },
        ),
    ]:
        start = perf_counter()
        response = getattr(client, method)(path, **kwargs)
        timings[name] = (perf_counter() - start) * 1000
        responses[name] = {"status_code": response.status_code, "body": response.json()}

    report = {
        "snapshot_id": metadata.revision,
        "gold_path_exists": gold_path.exists(),
        "endpoint_latency_ms": timings,
        "responses": responses,
    }
    reports_path = Path("reports/generated/property_api_smoke_20260726.json")
    evidence_path = Path("docs/evidence/property_api_smoke_20260726.json")
    for output_path in (reports_path, evidence_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(evidence_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
