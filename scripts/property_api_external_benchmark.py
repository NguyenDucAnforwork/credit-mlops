from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from time import perf_counter

import httpx
import numpy as np

from property_intelligence.sources import fetch_hf_dataset_metadata


REQUESTS = int(os.getenv("BENCHMARK_REQUESTS", "1000"))
CONCURRENCY = int(os.getenv("BENCHMARK_CONCURRENCY", "10"))
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
OUTPUT_NAME = os.getenv("BENCHMARK_OUTPUT_NAME", "property_api_external_benchmark_20260726.json")


async def main() -> None:
    metadata = fetch_hf_dataset_metadata()
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

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        await _wait_for_server(client)
        warm_start = perf_counter()
        warm_response = await client.get("/v1/comparables", params=property_payload)
        warm_latency_ms = (perf_counter() - warm_start) * 1000
        report = {
            "snapshot_id": metadata.revision,
            "execution": "external_httpx_async",
            "api_base_url": API_BASE_URL,
            "requests_per_endpoint": REQUESTS,
            "concurrency": CONCURRENCY,
            "server": {
                "health_status": "ok",
                "warmup_status_code": warm_response.status_code,
                "warmup_latency_ms": warm_latency_ms,
            },
            "avm": await _benchmark_endpoint(
                client,
                "POST",
                "/v1/avm/predict",
                json_payload=property_payload,
            ),
            "lending": await _benchmark_endpoint(
                client,
                "POST",
                "/v1/lending/decision",
                json_payload=lending_payload,
            ),
            "criterion_scope": os.getenv("BENCHMARK_SCOPE", "external_http_service"),
        }

    reports_path = Path("reports/generated") / OUTPUT_NAME
    evidence_path = Path("docs/evidence") / OUTPUT_NAME
    for path in (reports_path, evidence_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(evidence_path.read_text(encoding="utf-8"))
    if os.getenv("BENCHMARK_FAIL_ON_ERROR", "0") == "1":
        failed = warm_response.status_code >= 400 or any(
            result["valid_request_error_rate"] > 0 for result in (report["avm"], report["lending"])
        )
        if failed:
            raise SystemExit(1)


async def _benchmark_endpoint(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_payload: dict,
) -> dict:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    start = perf_counter()
    results = await asyncio.gather(
        *[_request_once(client, method, path, json_payload, semaphore) for _ in range(REQUESTS)]
    )
    total_runtime = perf_counter() - start
    statuses = [status for status, _ in results]
    latencies = np.array([latency for _, latency in results], dtype=float)
    valid_errors = sum(1 for status in statuses if status >= 400)
    return {
        "status_codes": sorted(set(statuses)),
        "valid_request_error_rate": float(valid_errors / REQUESTS),
        "latency_ms": {
            "median": float(np.median(latencies)),
            "p95": float(np.quantile(latencies, 0.95)),
            "p99": float(np.quantile(latencies, 0.99)),
            "max": float(np.max(latencies)),
        },
        "total_runtime_seconds": total_runtime,
        "throughput_rps": REQUESTS / total_runtime,
    }


async def _request_once(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_payload: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[int, float]:
    async with semaphore:
        start = perf_counter()
        response = await client.request(method, path, json=json_payload)
        return response.status_code, (perf_counter() - start) * 1000


async def _wait_for_server(client: httpx.AsyncClient) -> None:
    deadline = perf_counter() + 60
    last_error: Exception | None = None
    while perf_counter() < deadline:
        try:
            response = await client.get("/health")
            if response.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(0.5)
    raise RuntimeError(f"external API did not become healthy: {last_error}")


if __name__ == "__main__":
    asyncio.run(main())
