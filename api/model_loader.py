"""
Loads the champion model from MLflow Model Registry.
Falls back to a local artifact if MLflow is unreachable (disaster recovery).

Supported aliases: champion (XGBoost), challenger (LR), scorecard (WOE-LR).
The active alias is controlled by MLFLOW_MODEL_ALIAS env var (default: champion).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import joblib
import mlflow
import mlflow.pyfunc
import numpy as np

FALLBACK_MODEL_PATH = Path(__file__).parent.parent / "artifacts" / "fallback_model.joblib"
FALLBACK_PIPELINE_PATH = Path(__file__).parent.parent / "artifacts" / "feature_pipeline.joblib"
FALLBACK_SCORECARD_PATH = Path(__file__).parent.parent / "artifacts" / "scorecard_model.joblib"
MODEL_NAME = "credit_score_model"
RELOAD_INTERVAL_S = 60  # re-check alias every 60 s


class ModelLoader:
    def __init__(self) -> None:
        self._model = None
        self._pipeline = None
        self._version: str = "not_loaded"
        self._last_load: float = 0.0
        self._is_scorecard: bool = False  # True when serving the WOE scorecard

    def _active_alias(self) -> str:
        return os.getenv("MLFLOW_MODEL_ALIAS", "champion")

    def _load_from_registry(self) -> bool:
        try:
            mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
            alias = self._active_alias()
            model_uri = f"models:/{MODEL_NAME}@{alias}"
            client = mlflow.MlflowClient()
            mv = client.get_model_version_by_alias(MODEL_NAME, alias)

            # Scorecard is a joblib artifact — download and load directly
            if "scorecard" in (mv.tags or {}).get("model_type", "") or alias == "scorecard":
                import mlflow.artifacts
                sc_local = Path(mlflow.artifacts.download_artifacts(
                    artifact_uri=f"models:/{MODEL_NAME}@{alias}",
                    dst_path="/tmp/scorecard_download",
                ))
                # Try to find scorecard_model.joblib in downloaded artifacts
                sc_files = list(sc_local.rglob("scorecard_model.joblib"))
                if sc_files:
                    self._model = joblib.load(sc_files[0])
                    self._is_scorecard = True
                    self._version = f"{MODEL_NAME}@{alias} v{mv.version} (scorecard)"
                    return True

            # Generic pyfunc load (XGBoost / LR)
            self._model = mlflow.pyfunc.load_model(model_uri)
            self._is_scorecard = False
            self._version = f"{MODEL_NAME}@{alias} v{mv.version}"
            return True
        except Exception as exc:
            print(f"[model_loader] registry unavailable: {exc}")
            return False

    def _load_fallback(self) -> None:
        alias = self._active_alias()
        # Try scorecard fallback first if alias is scorecard
        if alias == "scorecard" and FALLBACK_SCORECARD_PATH.exists():
            self._model = joblib.load(FALLBACK_SCORECARD_PATH)
            self._is_scorecard = True
            self._version = "fallback_scorecard_local"
            print("[model_loader] using local fallback scorecard model")
            return
        if FALLBACK_MODEL_PATH.exists():
            self._model = joblib.load(FALLBACK_MODEL_PATH)
            self._is_scorecard = False
            self._version = "fallback_local"
            print("[model_loader] using local fallback model")
        else:
            # No fallback available — stay unloaded; health returns degraded
            # API still starts so health/metrics endpoints remain reachable
            print("[model_loader] WARNING: no fallback artifact — API degraded until registry available")

    def load(self) -> None:
        if not self._load_from_registry():
            self._load_fallback()
        if not self._is_scorecard:
            self._pipeline = self._load_pipeline()
        self._last_load = time.monotonic()
        print(f"[model_loader] loaded: {self._version}")

    def _load_pipeline(self):
        if FALLBACK_PIPELINE_PATH.exists():
            return joblib.load(FALLBACK_PIPELINE_PATH)
        return None

    def maybe_reload(self) -> None:
        if time.monotonic() - self._last_load > RELOAD_INTERVAL_S:
            self.load()

    def predict_proba(self, X_raw) -> np.ndarray:
        """Transform raw features then predict. Returns array of default probabilities."""
        import pandas as pd

        df = pd.DataFrame([X_raw]) if isinstance(X_raw, dict) else X_raw

        # Scorecard model handles its own full pipeline internally
        if self._is_scorecard and hasattr(self._model, "predict_proba"):
            return self._model.predict_proba(df)

        # Apply feature pipeline if available (XGBoost / LR path)
        if self._pipeline is not None:
            X_transformed = self._pipeline.transform(df)
        else:
            X_transformed = df.values

        if hasattr(self._model, "predict_proba"):
            return self._model.predict_proba(X_transformed)[:, 1]
        else:
            # MLflow pyfunc model
            import pandas as _pd
            preds = self._model.predict(_pd.DataFrame(X_transformed))
            if hasattr(preds, "values"):
                preds = preds.values.flatten()
            return np.array(preds, dtype=float)

    def predict_credit_score(self, X_raw) -> np.ndarray | None:
        """Return WOE-based credit scores for scorecard model, else None."""
        if self._is_scorecard and hasattr(self._model, "predict_credit_score"):
            import pandas as pd
            df = pd.DataFrame([X_raw]) if isinstance(X_raw, dict) else X_raw
            return self._model.predict_credit_score(df)
        return None

    @property
    def is_scorecard(self) -> bool:
        return self._is_scorecard

    @property
    def version(self) -> str:
        return self._version

    @property
    def is_loaded(self) -> bool:
        return self._model is not None


# Module-level singleton
_loader = ModelLoader()


def get_loader() -> ModelLoader:
    return _loader
