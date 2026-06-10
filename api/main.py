"""
FastAPI inference service for credit scoring.
Endpoints: GET /health  POST /predict  GET /metrics
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager

import pandas as pd
from dotenv import load_dotenv
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import create_engine, text

load_dotenv()

from decision import make_decision
from model_loader import get_loader
from schemas import HealthResponse, PredictRequest, PredictResponse

# ── Prometheus metrics ────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "api_requests_total", "Total requests", ["endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "api_latency_seconds", "Request latency",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)
PREDICTION_SCORE = Histogram(
    "prediction_default_prob", "Distribution of default probability scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
DECISION_COUNT = Counter(
    "prediction_decision_total", "Decision counts", ["decision"]
)
ERROR_COUNT = Counter("api_errors_total", "API errors", ["error_type"])
FEATURE_MISSING_RATE = Histogram(
    "feature_missing_rate", "Fraction of null features per request (0–1)",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0],
)

_start_time = time.monotonic()

# ── DB engine (audit log) ─────────────────────────────────────────────────────
_db_engine = None


def _get_engine():
    global _db_engine
    if _db_engine is None:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            _db_engine = create_engine(db_url, pool_pre_ping=True)
            with _db_engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS predictions (
                        id SERIAL PRIMARY KEY,
                        ts TIMESTAMPTZ DEFAULT now(),
                        trace_id TEXT,
                        features JSONB,
                        default_probability FLOAT,
                        credit_score INT,
                        risk_band TEXT,
                        decision TEXT,
                        model_version TEXT,
                        latency_ms FLOAT
                    )
                """))
                # Migration for tables created before trace_id existed.
                conn.execute(text(
                    "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS trace_id TEXT"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_predictions_trace_id "
                    "ON predictions (trace_id)"
                ))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS model_deployment_events (
                        id            SERIAL PRIMARY KEY,
                        ts            TIMESTAMPTZ DEFAULT now(),
                        event_type    TEXT NOT NULL,
                        model_name    TEXT NOT NULL,
                        alias         TEXT NOT NULL,
                        from_version  TEXT,
                        to_version    TEXT,
                        triggered_by  TEXT DEFAULT 'api',
                        reason        TEXT
                    )
                """))
                conn.commit()
    return _db_engine


def _log_deployment_event(event_type: str, alias: str, from_version: str | None,
                           to_version: str, triggered_by: str = "api", reason: str | None = None) -> None:
    try:
        engine = _get_engine()
        if engine is None:
            return
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO model_deployment_events
                    (event_type, model_name, alias, from_version, to_version, triggered_by, reason)
                VALUES
                    (:event_type, 'credit_score_model', :alias, :from_version,
                     :to_version, :triggered_by, :reason)
            """), {"event_type": event_type, "alias": alias, "from_version": from_version,
                   "to_version": to_version, "triggered_by": triggered_by, "reason": reason})
            conn.commit()
    except Exception as exc:
        print(f"[deployment_events] write failed: {exc}")


def _audit_log(features: dict, result: dict) -> None:
    try:
        engine = _get_engine()
        if engine is None:
            return
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO predictions
                    (trace_id, features, default_probability, credit_score, risk_band,
                     decision, model_version, latency_ms)
                VALUES
                    (:trace_id, :features, :default_probability, :credit_score, :risk_band,
                     :decision, :model_version, :latency_ms)
            """), {
                "trace_id": result.get("trace_id"),
                "features": json.dumps(features),
                "default_probability": result["default_probability"],
                "credit_score": result["credit_score"],
                "risk_band": result["risk_band"],
                "decision": result["decision"],
                "model_version": result["model_version"],
                "latency_ms": result["latency_ms"],
            })
            conn.commit()
    except Exception as exc:
        ERROR_COUNT.labels(error_type="db_write").inc()
        print(f"[audit] DB write failed: {exc}")


# ── Redis rate limiter ────────────────────────────────────────────────────────
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            import redis
            _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def _check_rate_limit(client_ip: str, limit: int = 100, window: int = 60) -> bool:
    """Returns True if request is allowed."""
    r = _get_redis()
    if r is None:
        return True
    key = f"rate:{client_ip}"
    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, window)
        return count <= limit
    except Exception:
        return True  # fail open if Redis is down


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    loader = get_loader()
    try:
        loader.load()
    except Exception as exc:
        print(f"[startup] model load failed (degraded mode): {exc}")
    try:
        _get_engine()
    except Exception as exc:
        print(f"[startup] DB init failed (non-fatal): {exc}")
    yield


app = FastAPI(
    title="Credit Scoring API",
    description="MLOps-grade credit default prediction service",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health():
    loader = get_loader()
    return HealthResponse(
        status="ok" if loader.is_loaded else "degraded",
        model_version=loader.version,
        uptime_s=round(time.monotonic() - _start_time, 1),
    )


@app.post("/predict", response_model=PredictResponse)
def predict(
    request: Request,
    payload: PredictRequest,
    model: Optional[str] = Query(None, description="Model alias: champion, challenger, scorecard"),
    source: str = Query("auto", description="Source: auto | local | dagshub"),
):
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        REQUEST_COUNT.labels(endpoint="/predict", status="429").inc()
        raise HTTPException(status_code=429, detail="Rate limit exceeded (100 req/min)")

    try:
        loader = get_loader(alias=model, source=source)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    loader.maybe_reload()

    if not loader.is_loaded:
        ERROR_COUNT.labels(error_type="model_not_loaded").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    t0 = time.monotonic()
    try:
        trace_id = str(uuid.uuid4())
        features = payload.model_dump(exclude_none=False)
        # Observe feature completeness
        missing_frac = sum(1 for v in features.values() if v is None) / max(len(features), 1)
        FEATURE_MISSING_RATE.observe(missing_frac)
        df = pd.DataFrame([features])

        # Single pass: KNN runs once regardless of model type
        all_results = loader.predict_all(df)
        default_prob    = float(all_results["proba"][0])
        scorecard_score = float(all_results["credit_score"][0]) if all_results["credit_score"] is not None else None
        sc_breakdown    = all_results["breakdown"]

        result = make_decision(default_prob)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)

        response = PredictResponse(
            **result,
            model_version=loader.version,
            latency_ms=latency_ms,
            scorecard_score=scorecard_score,
            scorecard_breakdown=sc_breakdown,
            model_alias=loader.active_alias,
            trace_id=trace_id,
        )

        # Observability
        REQUEST_LATENCY.observe(time.monotonic() - t0)
        REQUEST_COUNT.labels(endpoint="/predict", status="200").inc()
        PREDICTION_SCORE.observe(default_prob)
        DECISION_COUNT.labels(decision=result["decision"]).inc()

        _audit_log(features, {**result, "model_version": loader.version, "latency_ms": latency_ms,
                               "scorecard_score": scorecard_score, "trace_id": trace_id})
        return response

    except HTTPException:
        raise
    except Exception as exc:
        ERROR_COUNT.labels(error_type="prediction_error").inc()
        REQUEST_COUNT.labels(endpoint="/predict", status="500").inc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/metrics")
def metrics():
    REQUEST_COUNT.labels(endpoint="/metrics", status="200").inc()
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
