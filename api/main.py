"""
FastAPI inference service for credit scoring.
Endpoints: GET /health  POST /predict  GET /metrics
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
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
                        features JSONB,
                        default_probability FLOAT,
                        credit_score INT,
                        risk_band TEXT,
                        decision TEXT,
                        model_version TEXT,
                        latency_ms FLOAT
                    )
                """))
                conn.commit()
    return _db_engine


def _audit_log(features: dict, result: dict) -> None:
    try:
        engine = _get_engine()
        if engine is None:
            return
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO predictions
                    (features, default_probability, credit_score, risk_band,
                     decision, model_version, latency_ms)
                VALUES
                    (:features, :default_probability, :credit_score, :risk_band,
                     :decision, :model_version, :latency_ms)
            """), {
                "features": str(features),
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
def predict(request: Request, payload: PredictRequest):
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        REQUEST_COUNT.labels(endpoint="/predict", status="429").inc()
        raise HTTPException(status_code=429, detail="Rate limit exceeded (100 req/min)")

    loader = get_loader()
    loader.maybe_reload()

    if not loader.is_loaded:
        ERROR_COUNT.labels(error_type="model_not_loaded").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    t0 = time.monotonic()
    try:
        features = payload.model_dump(exclude_none=False)
        df = pd.DataFrame([features])

        proba = loader.predict_proba(df)
        default_prob = float(proba[0])

        # WOE-based score + per-feature breakdown (scorecard model only)
        sc_scores = loader.predict_credit_score(df)
        scorecard_score = float(sc_scores[0]) if sc_scores is not None else None
        sc_breakdown = loader.explain(df) if loader.is_scorecard else None

        result = make_decision(default_prob)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)

        response = PredictResponse(
            **result,
            model_version=loader.version,
            latency_ms=latency_ms,
            scorecard_score=scorecard_score,
            scorecard_breakdown=sc_breakdown,
        )

        # Observability
        REQUEST_LATENCY.observe(time.monotonic() - t0)
        REQUEST_COUNT.labels(endpoint="/predict", status="200").inc()
        PREDICTION_SCORE.observe(default_prob)
        DECISION_COUNT.labels(decision=result["decision"]).inc()

        _audit_log(features, {**result, "model_version": loader.version, "latency_ms": latency_ms,
                               "scorecard_score": scorecard_score})
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
