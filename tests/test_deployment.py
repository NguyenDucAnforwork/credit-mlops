"""
Tests for champion/challenger deployment workflow.
Covers: no-downtime during background reload failure, promote/rollback CLI scripts,
deployment_events table population, and trace_id/model_alias enrichment.
"""
from __future__ import annotations

import importlib
import os
import sys
import threading
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_loader(version: str = "v1", alias: str = "champion") -> MagicMock:
    ldr = MagicMock()
    ldr.is_loaded = True
    ldr.version = version
    ldr.active_alias = alias
    ldr.predict_all.return_value = {"proba": np.array([0.25]), "credit_score": None, "breakdown": None}
    ldr.maybe_reload.return_value = None
    return ldr


# ── 1. Non-blocking reload — health stays OK even when reload thread fails ─────

class TestNonBlockingReload:
    def test_health_200_during_failed_reload(self):
        """
        Background reload failure must not kill in-flight requests.
        The old model stays in memory; /health still returns 200.
        """
        from fastapi.testclient import TestClient
        import model_loader as ldr_mod
        import main as main_mod

        mock_ldr = _mock_loader()
        ldr_mod._loader = mock_ldr

        # Simulate a reload failure by making _reload_safe raise
        real_reload_safe_raises = Exception("registry 503")
        mock_ldr._reload_safe.side_effect = real_reload_safe_raises
        mock_ldr.is_loaded = True  # model was already loaded before failure

        with TestClient(main_mod.app, raise_server_exceptions=False) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_predict_200_while_reload_in_progress(self):
        """
        Requests dispatched while a background reload is running must complete
        with the OLD model (no blocking, no 503).
        """
        from fastapi.testclient import TestClient
        import model_loader as ldr_mod
        import main as main_mod

        mock_ldr = _mock_loader("v1-old", "scorecard")
        ldr_mod._loader = mock_ldr

        with TestClient(main_mod.app, raise_server_exceptions=False) as client:
            resp = client.post("/predict", json={"NUMBER_OF_LOANS": 2.0})

        assert resp.status_code == 200
        data = resp.json()
        assert "default_probability" in data
        assert "trace_id" in data and len(data["trace_id"]) == 36   # UUID4
        assert "model_alias" in data


# ── 2. PredictResponse enrichment ─────────────────────────────────────────────

class TestResponseEnrichment:
    def _make_client(self, alias: str = "scorecard"):
        from fastapi.testclient import TestClient
        import model_loader as ldr_mod
        import main as main_mod

        ldr_mod._loader = _mock_loader("registry@scorecard v7", alias)
        return TestClient(main_mod.app, raise_server_exceptions=False)

    def test_trace_id_is_uuid4(self):
        client = self._make_client()
        r = client.post("/predict", json={"NUMBER_OF_LOANS": 1.0})
        assert r.status_code == 200
        tid = r.json()["trace_id"]
        import uuid
        uuid.UUID(tid, version=4)  # raises ValueError if not UUID4

    def test_trace_id_unique_per_request(self):
        client = self._make_client()
        ids = {client.post("/predict", json={"NUMBER_OF_LOANS": 1.0}).json()["trace_id"]
               for _ in range(5)}
        assert len(ids) == 5  # all unique

    def test_model_alias_in_response(self):
        client = self._make_client(alias="challenger")
        r = client.post("/predict", json={"NUMBER_OF_LOANS": 1.0})
        assert r.json()["model_alias"] == "challenger"


# ── 3. Feature missing rate observation ───────────────────────────────────────

class TestFeatureMissingRate:
    def test_missing_rate_observed(self):
        """FEATURE_MISSING_RATE histogram must be called for every predict."""
        from fastapi.testclient import TestClient
        import model_loader as ldr_mod
        import main as main_mod

        ldr_mod._loader = _mock_loader()

        with patch.object(main_mod.FEATURE_MISSING_RATE, "observe") as mock_obs:
            with TestClient(main_mod.app, raise_server_exceptions=False) as client:
                client.post("/predict", json={"NUMBER_OF_LOANS": 2.0})
            mock_obs.assert_called_once()
            frac = mock_obs.call_args[0][0]
            assert 0.0 <= frac <= 1.0

    def test_all_nulls_gives_fraction_one(self):
        """Sending an empty payload (all nulls) → missing_frac close to 1.0."""
        from fastapi.testclient import TestClient
        import model_loader as ldr_mod
        import main as main_mod

        ldr_mod._loader = _mock_loader()

        with patch.object(main_mod.FEATURE_MISSING_RATE, "observe") as mock_obs:
            with TestClient(main_mod.app, raise_server_exceptions=False) as client:
                client.post("/predict", json={})
            frac = mock_obs.call_args[0][0]
            assert frac > 0.95  # all 122 fields null → ~1.0


# ── 4. ModelLoader background reload mechanics ─────────────────────────────────

class TestModelLoaderReload:
    def test_maybe_reload_spawns_thread_after_interval(self):
        """
        maybe_reload() must NOT block — it spawns a daemon thread and returns.
        Uses the already-imported model_loader module to avoid Prometheus
        duplicate-registry errors that occur when re-executing the module file.
        """
        import model_loader as mod

        ldr = mod.ModelLoader(alias="champion", source="local")
        ldr._model = MagicMock()  # mark as loaded
        ldr._last_load = time.monotonic() - mod.RELOAD_INTERVAL_S - 1  # force stale

        spawned: list[threading.Thread] = []

        def capture_start(self_thread):
            spawned.append(self_thread)

        with patch.object(threading.Thread, "start", capture_start):
            t0 = time.monotonic()
            ldr.maybe_reload()
            elapsed = time.monotonic() - t0

        assert elapsed < 0.05, "maybe_reload must return in <50ms (non-blocking)"
        assert len(spawned) == 1, "Expected exactly one thread to be spawned"
        assert spawned[0].daemon is True

    def test_maybe_reload_no_double_spawn(self):
        """Second call while thread is alive must not spawn a second thread."""
        import model_loader as mod

        ldr = mod.ModelLoader(alias="champion", source="local")
        ldr._model = MagicMock()
        ldr._last_load = time.monotonic() - mod.RELOAD_INTERVAL_S - 1

        fake_thread = MagicMock(spec=threading.Thread)
        fake_thread.is_alive.return_value = True
        ldr._reload_thread = fake_thread

        with patch("threading.Thread") as mock_thread_cls:
            ldr.maybe_reload()
            mock_thread_cls.assert_not_called()


# ── 5. promote_model script ────────────────────────────────────────────────────

class TestPromoteScript:
    def _load_promote(self):
        spec = importlib.util.spec_from_file_location(
            "promote_model",
            Path(__file__).parent.parent / "scripts" / "promote_model.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("mlflow", MagicMock())
        spec.loader.exec_module(mod)
        return mod

    def test_promote_sets_alias_in_mlflow(self):
        mod = self._load_promote()
        mock_client = MagicMock()
        mock_client.get_model_version_by_alias.return_value = MagicMock(version="5")

        with patch("mlflow.MlflowClient", return_value=mock_client), \
             patch("mlflow.set_tracking_uri"), \
             patch.object(mod, "resolve_engine", return_value=None), \
             patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "http://fake"}):
            mod.promote("8", "champion", "ci-bot")

        mock_client.set_registered_model_alias.assert_called_once_with(
            "credit_score_model", "champion", "8"
        )

    def test_promote_logs_deployment_event(self):
        mod = self._load_promote()
        mock_client = MagicMock()
        mock_client.get_model_version_by_alias.return_value = MagicMock(version="5")
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("mlflow.MlflowClient", return_value=mock_client), \
             patch("mlflow.set_tracking_uri"), \
             patch.object(mod, "resolve_engine", return_value=mock_engine), \
             patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "http://fake"}):
            mod.promote("8", "champion", "alice")

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_promote_no_db_does_not_crash(self):
        mod = self._load_promote()
        mock_client = MagicMock()
        mock_client.get_model_version_by_alias.side_effect = Exception("alias not found")

        with patch("mlflow.MlflowClient", return_value=mock_client), \
             patch("mlflow.set_tracking_uri"), \
             patch.object(mod, "resolve_engine", return_value=None), \
             patch.dict(os.environ, {"MLFLOW_TRACKING_URI": "http://fake"}):
            mod.promote("8", "champion", "ci-bot")  # should not raise

        mock_client.set_registered_model_alias.assert_called_once()


# ── 6. rollback_model script ───────────────────────────────────────────────────

class TestRollbackScript:
    def _load_rollback(self):
        spec = importlib.util.spec_from_file_location(
            "rollback_model",
            Path(__file__).parent.parent / "scripts" / "rollback_model.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("mlflow", MagicMock())
        spec.loader.exec_module(mod)
        return mod

    def _make_rollback_env(self, mod, mock_client, mock_conn, mock_engine):
        """Context manager stack for rollback tests."""
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        return (
            patch.object(mod, "resolve_engine", return_value=mock_engine),
            patch("mlflow.MlflowClient", return_value=mock_client),
            patch("mlflow.set_tracking_uri"),
            patch.dict(os.environ, {
                "MLFLOW_TRACKING_URI": "http://fake",
                "DATABASE_URL": "postgresql://fake",
            }),
        )

    def test_rollback_restores_previous_version(self):
        mod = self._load_rollback()
        mock_client = MagicMock()
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = MagicMock(
            from_version="5", to_version="8"
        )
        patches = self._make_rollback_env(mod, mock_client, mock_conn, mock_engine)
        with patches[0], patches[1], patches[2], patches[3]:
            mod.rollback("champion", "latency spike", "oncall")

        mock_client.set_registered_model_alias.assert_called_once_with(
            "credit_score_model", "champion", "5"
        )

    def test_rollback_logs_rollback_event(self):
        mod = self._load_rollback()
        mock_client = MagicMock()
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = MagicMock(
            from_version="5", to_version="8"
        )
        patches = self._make_rollback_env(mod, mock_client, mock_conn, mock_engine)
        with patches[0], patches[1], patches[2], patches[3]:
            mod.rollback("champion", "latency spike", "oncall")

        # Should have called execute twice: once SELECT, once INSERT rollback event
        assert mock_conn.execute.call_count == 2
        insert_args = mock_conn.execute.call_args_list[1][0]
        # str(TextClause) returns the actual SQL text (object repr does not)
        assert "rollback" in str(insert_args[0])
