"""Integration tests for the FastAPI endpoints."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_app_with_mock_model():
    """Create the FastAPI app with a mocked ModelLoader that doesn't need MLflow.

    main.py does `from model_loader import get_loader` (bare name via sys.path),
    so the test must patch the same module instance — `model_loader`, not `api.model_loader`.
    """
    import model_loader as loader_mod  # same instance that main.py sees
    import main as main_mod

    mock_loader = MagicMock()
    mock_loader.is_loaded = True
    mock_loader.version = "mock_model@champion v1"
    mock_loader.active_alias = "champion"  # PredictResponse.model_alias must be a str
    mock_loader.predict_proba.return_value = np.array([0.3])
    mock_loader.maybe_reload.return_value = None
    # The endpoint calls predict_all() (single-pass). Derive it from predict_proba
    # so tests that set predict_proba.return_value still control the probability.
    mock_loader.predict_all.side_effect = lambda df: {
        "proba": mock_loader.predict_proba.return_value,
        "credit_score": None,
        "breakdown": None,
    }

    loader_mod._loader = mock_loader
    return main_mod.app, mock_loader


@pytest.fixture
def client():
    app, _ = _make_app_with_mock_model()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_loader():
    app, mock_loader = _make_app_with_mock_model()
    return TestClient(app, raise_server_exceptions=False), mock_loader


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "model_version" in data
    assert "uptime_s" in data


def test_lifespan_tolerates_property_warmup_failure(monkeypatch):
    import main as main_mod
    import property_service

    monkeypatch.setattr(property_service, "warm_property_index", lambda: (_ for _ in ()).throw(FileNotFoundError("missing")))
    monkeypatch.setattr(main_mod, "warm_property_index", property_service.warm_property_index)

    with TestClient(main_mod.app, raise_server_exceptions=False) as lifespan_client:
        resp = lifespan_client.get("/health")

    assert resp.status_code == 200


def test_warm_property_index_reports_cached_rows(monkeypatch):
    import property_service

    class FakeIndex:
        listings = [1, 2, 3]

    monkeypatch.setattr(property_service, "_get_comparable_index", lambda: FakeIndex())
    monkeypatch.setattr(property_service, "_gold_path", lambda: Path("gold.parquet"))

    assert property_service.warm_property_index() == {
        "status": "ok",
        "gold_path": "gold.parquet",
        "listing_rows": 3,
    }


def test_predict_returns_200(client, valid_predict_payload):
    resp = client.post("/predict", json=valid_predict_payload)
    assert resp.status_code == 200


def test_predict_response_schema(client, valid_predict_payload):
    resp = client.post("/predict", json=valid_predict_payload)
    data = resp.json()
    assert 0.0 <= data["default_probability"] <= 1.0
    assert 300 <= data["credit_score"] <= 850
    assert data["risk_band"] in ["Very Poor", "Poor", "Fair", "Good", "Excellent"]
    assert data["decision"] in ["approve", "manual_review", "reject"]
    assert "model_version" in data
    assert data["latency_ms"] >= 0


def test_predict_empty_payload_still_works(client):
    resp = client.post("/predict", json={})
    assert resp.status_code in (200, 422, 500)


def test_predict_high_risk_decision(client_with_loader, valid_predict_payload):
    client, mock_loader = client_with_loader
    mock_loader.predict_proba.return_value = np.array([0.85])
    resp = client.post("/predict", json=valid_predict_payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "reject"


def test_predict_low_risk_decision(client_with_loader, valid_predict_payload):
    client, mock_loader = client_with_loader
    mock_loader.predict_proba.return_value = np.array([0.10])
    resp = client.post("/predict", json=valid_predict_payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "approve"


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "api_requests_total" in resp.text


def test_metrics_incremented_after_predict(client, valid_predict_payload):
    client.post("/predict", json=valid_predict_payload)
    resp = client.get("/metrics")
    assert "api_requests_total" in resp.text


def test_avm_predict_returns_required_property_fields(client, monkeypatch):
    import property_service

    class FakeIndex:
        def query(self, query):
            return _fake_comparable_result(query)

    monkeypatch.setattr(property_service, "_get_comparable_index", lambda: FakeIndex())
    resp = client.post(
        "/v1/avm/predict",
        json={
            "published_at": "2025-12-15T00:00:00Z",
            "province": "Hà Nội",
            "district": "Cầu Giấy",
            "property_type": "apartment",
            "area_m2": 50,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["estimated_value_vnd"] > 0
    assert data["lower_value_vnd"] <= data["estimated_value_vnd"] <= data["upper_value_vnd"]
    assert data["confidence"] in ["high", "medium", "low"]
    assert data["comparables"][0]["distance_status"] == "not_available_missing_coordinates"
    assert data["trace_id"]


def test_comparables_endpoint_returns_support_metadata(client, monkeypatch):
    import main as main_mod

    class FakeIndex:
        def query(self, query):
            return _fake_comparable_result(query)

    monkeypatch.setattr(main_mod, "_get_comparable_index", lambda: FakeIndex())
    resp = client.get(
        "/v1/comparables",
        params={
            "published_at": "2025-12-15T00:00:00Z",
            "province": "Hà Nội",
            "district": "Cầu Giấy",
            "property_type": "apartment",
            "area_m2": 50,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert data["support_level"] == "medium"
    assert data["distance_status"] == "not_available_missing_coordinates"


@pytest.mark.parametrize(
    "loan_amount,expected",
    [
        (75.0, "approve"),
        (75.01, "manual_review"),
        (85.0, "manual_review"),
        (85.01, "reject"),
    ],
)
def test_lending_decision_ltv_boundaries(client, loan_amount, expected):
    resp = client.post(
        "/v1/lending/decision",
        json={
            "credit_decision": "approve",
            "loan_amount_vnd": loan_amount,
            "lower_value_vnd": 100.0,
            "confidence": "high",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["decision"] == expected


def _fake_comparable_result(query):
    comparables = [
        {
            "listing_id": f"cmp-{idx}",
            "province": query.province,
            "district": query.district,
            "ward": "Dịch Vọng",
            "property_type": query.property_type,
            "price_vnd": price_per_m2 * query.area_m2,
            "area_m2": query.area_m2,
            "price_per_m2": price_per_m2,
            "published_at": "2025-11-01T00:00:00+00:00",
            "match_tier": "province+district+property_type",
            "area_ratio": 1.0,
            "recency_days": 30.0,
            "distance_m": None,
            "distance_status": "not_available_missing_coordinates",
        }
        for idx, price_per_m2 in enumerate([40_000_000, 42_000_000, 44_000_000], start=1)
    ]
    return {
        "query": query.__dict__,
        "count": len(comparables),
        "max_results": 10,
        "area_tolerance": 0.25,
        "support_level": "medium",
        "match_tier_counts": {"province+district+property_type": 3},
        "distance_status": "not_available_missing_coordinates",
        "warnings": ["source dataset lacks latitude/longitude; comparable distance and radius fallback unavailable"],
        "comparables": comparables,
    }
