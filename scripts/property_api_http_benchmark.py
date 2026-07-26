from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import httpx
import numpy as np

from property_intelligence.sources import fetch_hf_dataset_metadata


REQUESTS = 1000
CONCURRENCY = 10
HOST = "127.0.0.1"


async def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    repo_root = Path.cwd()
    gold_path = (repo_root / "data/gold" / metadata.revision / "listings_gold.parquet").resolve()
    port = _free_port()
    process = _start_server(repo_root, gold_path, port)
    try:
        base_url = f"http://{HOST}:{port}"
        await _wait_for_server(base_url)
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
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            warm_start = perf_counter()
            warm_response = await client.get("/v1/comparables", params=property_payload)
            warm_latency_ms = (perf_counter() - warm_start) * 1000
            report = {
                "snapshot_id": metadata.revision,
                "execution": "uvicorn_httpx_async",
                "requests_per_endpoint": REQUESTS,
                "concurrency": CONCURRENCY,
                "gold_path_exists": gold_path.exists(),
                "server": {
                    "host": HOST,
                    "port": port,
                    "startup_status": "ok",
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
                "criterion_scope": "vm_uvicorn_http_service_non_docker",
            }
    finally:
        _stop_server(process)

    reports_path = Path("reports/generated/property_api_http_benchmark_20260726.json")
    evidence_path = Path("docs/evidence/property_api_http_benchmark_20260726.json")
    for path in (reports_path, evidence_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(evidence_path.read_text(encoding="utf-8"))


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


async def _wait_for_server(base_url: str) -> None:
    deadline = perf_counter() + 30
    last_error: Exception | None = None
    async with httpx.AsyncClient(base_url=base_url, timeout=2.0) as client:
        while perf_counter() < deadline:
            try:
                response = await client.get("/health")
                if response.status_code == 200:
                    return
            except Exception as exc:
                last_error = exc
            await asyncio.sleep(0.25)
    raise RuntimeError(f"uvicorn did not become healthy: {last_error}")


def _start_server(repo_root: Path, gold_path: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["PROPERTY_GOLD_PATH"] = str(gold_path)
    env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "api"), str(repo_root / "src"), env.get("PYTHONPATH", "")])
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            HOST,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=repo_root / "api",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_server(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    asyncio.run(main())
