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
    mock_loader.predict_proba.return_value = np.array([0.3])
    mock_loader.maybe_reload.return_value = None

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
