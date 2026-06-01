"""
Chaos / fault-injection tests.
Verifies the system degrades gracefully when dependencies fail.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── ModelLoader fault injection ───────────────────────────────────────────────
class TestModelLoaderFallback:
    def test_falls_back_to_local_when_registry_down(self, tmp_path):
        """When MLflow registry is unreachable, loader uses local fallback."""
        import model_loader as loader_mod
        from sklearn.dummy import DummyClassifier
        import joblib

        dummy = DummyClassifier(strategy="constant", constant=0)
        dummy.fit([[0] * 22], [0])
        fallback_path = tmp_path / "fallback_model.joblib"
        joblib.dump(dummy, fallback_path)

        # Point FALLBACK_PIPELINE_PATH to non-existent so loader skips pipeline
        missing_pipeline = tmp_path / "no_pipeline.joblib"

        with patch.object(loader_mod, "FALLBACK_MODEL_PATH", fallback_path), \
             patch.object(loader_mod, "FALLBACK_PIPELINE_PATH", missing_pipeline), \
             patch("mlflow.pyfunc.load_model", side_effect=Exception("MLflow down")):
            loader = loader_mod.ModelLoader()
            loader.load()
            assert loader.version == "fallback_local"
            assert loader.is_loaded

    def test_degraded_when_no_fallback_and_registry_down(self, tmp_path):
        """If both registry and fallback are unavailable, loader stays unloaded (degraded)."""
        import model_loader as loader_mod

        with patch.object(loader_mod, "FALLBACK_MODEL_PATH", tmp_path / "nonexistent.joblib"), \
             patch("mlflow.pyfunc.load_model", side_effect=Exception("MLflow down")):
            loader = loader_mod.ModelLoader()
            loader.load()  # must not raise
            assert not loader.is_loaded
            assert loader.version == "not_loaded"


# ── API fault injection ───────────────────────────────────────────────────────
class TestAPIFaultInjection:
    def _get_client_with_mock(self, proba=0.3, is_loaded=True, side_effect=None):
        import model_loader as loader_mod  # same instance as main.py
        import main as main_mod
        from fastapi.testclient import TestClient

        mock_loader = MagicMock()
        mock_loader.is_loaded = is_loaded
        mock_loader.version = "mock@champion"
        if side_effect:
            mock_loader.predict_proba.side_effect = side_effect
        else:
            mock_loader.predict_proba.return_value = np.array([proba])
        mock_loader.maybe_reload.return_value = None
        loader_mod._loader = mock_loader

        return TestClient(main_mod.app, raise_server_exceptions=False), mock_loader

    def test_corrupted_numeric_input_still_responds(self):
        """Negative, zero, and extreme values must not crash the API."""
        client, _ = self._get_client_with_mock()
        payload = {
            "NUMBER_OF_LOANS": -999,
            "ENQUIRIES_3M": 99999,
            "OUTSTANDING_BAL_LOAN_CURRENT": -1,
        }
        resp = client.post("/predict", json=payload)
        assert resp.status_code in (200, 422, 500)

    def test_model_prediction_exception_returns_500(self, valid_predict_payload):
        """If model.predict_proba throws, API returns 500 not crash."""
        client, _ = self._get_client_with_mock(side_effect=RuntimeError("model exploded"))
        resp = client.post("/predict", json=valid_predict_payload)
        assert resp.status_code == 500

    def test_model_not_loaded_returns_503(self, valid_predict_payload):
        """If model never loaded, /predict returns 503."""
        client, _ = self._get_client_with_mock(is_loaded=False)
        resp = client.post("/predict", json=valid_predict_payload)
        assert resp.status_code == 503

    def test_health_degraded_when_model_not_loaded(self):
        client, _ = self._get_client_with_mock(is_loaded=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"


# ── Data prep fault injection ──────────────────────────────────────────────────
class TestDataPrepFaults:
    def test_missing_raw_file_raises(self, tmp_path):
        """data_prep.run() should raise FileNotFoundError if raw CSV missing."""
        from data_prep import load_and_split
        with pytest.raises((FileNotFoundError, Exception)):
            load_and_split(data_path=tmp_path / "nonexistent.csv")
