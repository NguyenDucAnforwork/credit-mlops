from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

import numpy as np
from fastapi.testclient import TestClient

from property_intelligence.sources import fetch_hf_dataset_metadata


REQUESTS = 1000
CONCURRENCY = 10


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    gold_path = Path("data/gold") / metadata.revision / "listings_gold.parquet"
    os.environ["PROPERTY_GOLD_PATH"] = str(gold_path)
    sys.path.insert(0, str(Path("api").resolve()))
    from main import app

    property_payload = {
        "published_at": "2025-12-15T00:00:00Z",
        "province": "Hà Nội",
        "district": "Cầu Giấy",
        "property_type": "apartment",
        "area_m2": 55,
    }
    lending_payload = {
        "credit_decision": "approve",
        "loan_amount_vnd": 1_500_000_000,
        "lower_value_vnd": 2_000_000_000,
        "confidence": "high",
    }

    warm_client = TestClient(app, raise_server_exceptions=False)
    warm_client.get("/v1/comparables", params=property_payload)
    report = {
        "snapshot_id": metadata.revision,
        "execution": "fastapi_testclient_threads",
        "requests_per_endpoint": REQUESTS,
        "concurrency": CONCURRENCY,
        "gold_path_exists": gold_path.exists(),
        "avm": _benchmark_endpoint("post", "/v1/avm/predict", {"json": property_payload}, app),
        "lending": _benchmark_endpoint("post", "/v1/lending/decision", {"json": lending_payload}, app),
        "criterion_scope": "vm_testclient_warm_path_not_docker_service",
    }
    reports_path = Path("reports/generated/property_api_load_benchmark_20260726.json")
    evidence_path = Path("docs/evidence/property_api_load_benchmark_20260726.json")
    for path in (reports_path, evidence_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(evidence_path.read_text(encoding="utf-8"))


def _benchmark_endpoint(method: str, path: str, kwargs: dict, app) -> dict:
    latencies_ms: list[float] = []
    statuses: list[int] = []
    start = perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(_request_once, method, path, kwargs, app) for _ in range(REQUESTS)]
        for future in as_completed(futures):
            status_code, latency_ms = future.result()
            statuses.append(status_code)
            latencies_ms.append(latency_ms)
    total_runtime = perf_counter() - start
    lat = np.array(latencies_ms, dtype=float)
    valid_errors = sum(1 for status in statuses if status >= 400)
    return {
        "status_codes": sorted(set(statuses)),
        "valid_request_error_rate": float(valid_errors / REQUESTS),
        "latency_ms": {
            "median": float(np.median(lat)),
            "p95": float(np.quantile(lat, 0.95)),
            "p99": float(np.quantile(lat, 0.99)),
            "max": float(np.max(lat)),
        },
        "total_runtime_seconds": total_runtime,
        "throughput_rps": REQUESTS / total_runtime,
    }


def _request_once(method: str, path: str, kwargs: dict, app) -> tuple[int, float]:
    client = TestClient(app, raise_server_exceptions=False)
    start = perf_counter()
    response = getattr(client, method)(path, **kwargs)
    return response.status_code, (perf_counter() - start) * 1000


if __name__ == "__main__":
    main()
