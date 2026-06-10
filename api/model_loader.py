"""
Loads the champion model from MLflow Model Registry.
Falls back to a local artifact if MLflow is unreachable (disaster recovery).

Supported aliases: champion (XGBoost), challenger (LR), scorecard (WOE-LR).
The active alias is controlled by MLFLOW_MODEL_ALIAS env var (default: champion).

Per-request overrides: pass alias/source to get_loader(alias, source).
  source="auto"    – try DagsHub registry first, fall back to local (default)
  source="local"   – skip registry entirely, use local joblib artifacts
  source="dagshub" – require registry; raise RuntimeError if unavailable
"""
from __future__ import annotations

import os
import time
import threading
import uuid
from pathlib import Path
from typing import Optional

import joblib
import mlflow
import mlflow.artifacts
import mlflow.pyfunc
import mlflow.sklearn
import numpy as np
from prometheus_client import Counter, Gauge

FALLBACK_MODEL_PATH = Path(__file__).parent.parent / "artifacts" / "fallback_model.joblib"
FALLBACK_PIPELINE_PATH = Path(__file__).parent.parent / "artifacts" / "feature_pipeline.joblib"
FALLBACK_SCORECARD_PATH = Path(__file__).parent.parent / "artifacts" / "scorecard_model.joblib"
MODEL_NAME = "credit_score_model"

MODEL_RELOAD_SUCCESS = Counter(
    "model_reload_success_total", "Successful background model reloads",
    ["alias", "source"],
)
MODEL_RELOAD_FAILURE = Counter(
    "model_reload_failure_total", "Failed background model reloads",
    ["alias", "error_type"],
)
MODEL_INFO = Gauge(
    "model_version_info", "Currently loaded model (1=active)",
    ["alias", "version", "source"],
)
_global_reload_lock = threading.Lock()

# Local fallback reload: instant (disk read).
# Registry reload: 5-10s (DagsHub artifact download).
# 60s interval caused every-minute 5-10s blocking spikes on requests that
# happened to trigger the reload. 3600s (1h) is appropriate — aliases
# don't change more often than that in practice.
RELOAD_INTERVAL_S = 3600


class ModelLoader:
    def __init__(self, alias: Optional[str] = None, source: str = "auto") -> None:
        self._alias_override = alias   # None → use MLFLOW_MODEL_ALIAS env var
        self._source = source          # "auto" | "local" | "dagshub"
        self._model = None
        self._pipeline = None
        self._version: str = "not_loaded"
        self._last_load: float = 0.0
        self._is_scorecard: bool = False  # True when serving the WOE scorecard
        self._reload_thread: threading.Thread | None = None

    def _active_alias(self) -> str:
        if self._alias_override:
            return self._alias_override
        return os.getenv("MLFLOW_MODEL_ALIAS", "champion")

    def _load_from_registry(self) -> bool:
        try:
            mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
            alias = self._active_alias()
            model_uri = f"models:/{MODEL_NAME}@{alias}"
            client = mlflow.MlflowClient()
            mv = client.get_model_version_by_alias(MODEL_NAME, alias)

            # Scorecard: registered with sklearn flavor (no python_function flavor).
            # mlflow.sklearn.load_model uses cloudpickle and returns the fitted
            # ScorecardModel instance directly. mlflow.pyfunc.load_model would fail
            # with "Model does not have the python_function flavor".
            if "scorecard" in (mv.tags or {}).get("model_type", "") or alias == "scorecard":
                self._model = mlflow.sklearn.load_model(model_uri)
                self._is_scorecard = True
                self._version = f"{MODEL_NAME}@{alias} v{mv.version} (scorecard/dagshub)"
                return True

            # Generic pyfunc load (XGBoost / LR)
            self._model = mlflow.pyfunc.load_model(model_uri)
            self._is_scorecard = False
            self._version = f"{MODEL_NAME}@{alias} v{mv.version}"
            return True
        except Exception as exc:
            print(f"[model_loader] registry unavailable: {exc}")
            return False

    def _load_fallback(self, strict: bool = False) -> None:
        alias = self._active_alias()
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
            msg = f"No local fallback artifact for alias '{alias}'"
            if strict:
                raise RuntimeError(msg)
            # Non-strict (auto mode): stay unloaded; health returns degraded
            print(f"[model_loader] WARNING: {msg} — API degraded until registry available")

    def load(self) -> None:
        if self._source == "local":
            self._load_fallback(strict=True)
        elif self._source == "dagshub":
            if not self._load_from_registry():
                raise RuntimeError(
                    f"DagsHub registry unavailable for alias '{self._active_alias()}'"
                )
        else:  # "auto"
            if not self._load_from_registry():
                self._load_fallback()
        if not self._is_scorecard:
            self._pipeline = self._load_pipeline()
        self._last_load = time.monotonic()
        print(f"[model_loader] loaded: {self._version}")
        MODEL_INFO.labels(alias=self._active_alias(), version=self._version, source=self._source).set(1)

    def _load_pipeline(self):
        if FALLBACK_PIPELINE_PATH.exists():
            # Route through FeaturePipeline.load so the artifact unpickles
            # regardless of cwd / sys.path (module-alias shim).
            from features import FeaturePipeline
            return FeaturePipeline.load(FALLBACK_PIPELINE_PATH)
        return None

    def maybe_reload(self) -> None:
        """Spawn a background reload thread — never blocks the request path."""
        if time.monotonic() - self._last_load > RELOAD_INTERVAL_S:
            if self._reload_thread is None or not self._reload_thread.is_alive():
                self._reload_thread = threading.Thread(
                    target=self._reload_safe, daemon=True,
                    name=f"model-reload-{self._active_alias()}",
                )
                self._reload_thread.start()

    def _reload_safe(self) -> None:
        """Load new model in background; atomically swap attributes when ready."""
        alias = self._active_alias()
        if not _global_reload_lock.acquire(blocking=False):
            return  # another reload already in progress
        try:
            tmp = ModelLoader(alias=self._alias_override, source=self._source)
            tmp.load()
            # Atomic swap — in-flight requests complete with old model
            self._model      = tmp._model
            self._pipeline   = tmp._pipeline
            self._version    = tmp._version
            self._is_scorecard = tmp._is_scorecard
            if hasattr(tmp, "_train_medians"):
                self._train_medians = tmp._train_medians
            self._last_load = time.monotonic()
            MODEL_RELOAD_SUCCESS.labels(alias=alias, source=self._source).inc()
            MODEL_INFO.labels(alias=alias, version=self._version, source=self._source).set(1)
            print(f"[model_loader] background reload OK: {self._version}")
        except Exception as exc:
            self._last_load = time.monotonic()  # reset timer — avoid tight retry loop
            MODEL_RELOAD_FAILURE.labels(alias=alias, error_type=type(exc).__name__).inc()
            print(f"[model_loader] background reload FAILED: {exc}")
        finally:
            _global_reload_lock.release()

    def _fill_nulls_with_medians(self, df):
        """
        Pre-fill NaN with column medians from training data before running the
        feature pipeline.

        Why: KNNImputer finds neighbors using only non-null columns. For API
        requests with 14/122 features, those neighbors are biased toward
        whatever segment the 14 provided count-features select — typically
        high-risk customers — inflating P(default) to ~0.93 on average.
        Median imputation is neutral (population-level average) and removes
        that bias. KNNImputer then has no NaN to process and returns instantly.
        """
        import pandas as pd
        if self._pipeline is None or not hasattr(self._pipeline, "pipeline_"):
            return df
        knn = self._pipeline.pipeline_.named_steps.get("imputer")
        if knn is None or not hasattr(knn, "_fit_X"):
            return df
        if not hasattr(self, "_train_medians"):
            self._train_medians = np.nanmedian(knn._fit_X, axis=0)
        arr = df.values.astype(float)
        for j, med in enumerate(self._train_medians):
            null_mask = np.isnan(arr[:, j])
            if null_mask.any():
                arr[null_mask, j] = med
        return pd.DataFrame(arr, columns=df.columns, index=df.index)

    def predict_proba(self, X_raw) -> np.ndarray:
        """Transform raw features then predict. Returns array of default probabilities."""
        import pandas as pd

        df = pd.DataFrame([X_raw]) if isinstance(X_raw, dict) else X_raw

        # Scorecard model handles its own full pipeline internally
        if self._is_scorecard and hasattr(self._model, "predict_proba"):
            return self._model.predict_proba(df)

        # Pre-fill nulls with training medians so KNNImputer is a no-op.
        # Avoids segment bias from KNN neighbor selection on partial inputs.
        df = self._fill_nulls_with_medians(df)

        # Apply feature pipeline if available (XGBoost / LR path)
        if self._pipeline is not None:
            X_transformed = self._pipeline.transform(df)
        else:
            X_transformed = df.values

        if hasattr(self._model, "predict_proba"):
            return self._model.predict_proba(X_transformed)[:, 1]
        else:
            # MLflow pyfunc — detect and handle 2-column probability DataFrame.
            # MLflow 3.x sklearn/xgboost pyfunc can return DataFrame shaped (n, 2)
            # with columns [P(class=0), P(class=1)].  Taking index [0] would give
            # P(no_default) instead of P(default).  Always take the last column.
            import pandas as _pd
            preds = self._model.predict(_pd.DataFrame(X_transformed))
            if hasattr(preds, "values"):
                arr = preds.values
                if arr.ndim == 2 and arr.shape[1] >= 2:
                    return arr[:, -1].astype(float)   # P(class=last) = P(default)
                preds = arr.flatten()
            return np.array(preds, dtype=float)

    def predict_credit_score(self, X_raw) -> np.ndarray | None:
        """Return WOE-based credit scores for scorecard model, else None."""
        if self._is_scorecard and hasattr(self._model, "predict_credit_score"):
            import pandas as pd
            df = pd.DataFrame([X_raw]) if isinstance(X_raw, dict) else X_raw
            return self._model.predict_credit_score(df)
        return None

    def explain(self, X_raw) -> list | None:
        """Return per-feature score breakdown for scorecard model, else None."""
        if self._is_scorecard and hasattr(self._model, "explain"):
            import pandas as pd
            df = pd.DataFrame([X_raw]) if isinstance(X_raw, dict) else X_raw
            return self._model.explain(df)
        return None

    def predict_all(self, X_raw) -> dict:
        """
        Single-pass predict for scorecard model (KNN runs once instead of 3×).
        Returns {"proba": ..., "credit_score": ..., "breakdown": ...}.
        Falls back to separate calls for non-scorecard models.
        """
        import pandas as pd
        df = pd.DataFrame([X_raw]) if isinstance(X_raw, dict) else X_raw
        if self._is_scorecard and hasattr(self._model, "predict_all"):
            return self._model.predict_all(df)
        proba = self.predict_proba(df)
        return {"proba": proba, "credit_score": None, "breakdown": None}

    @property
    def active_alias(self) -> str:
        return self._active_alias()

    @property
    def is_scorecard(self) -> bool:
        return self._is_scorecard

    @property
    def version(self) -> str:
        return self._version

    @property
    def is_loaded(self) -> bool:
        return self._model is not None


# Default singleton — serves requests with no explicit model/source override
_loader = ModelLoader()

# Cache for per-request model overrides keyed by (alias, source)
_loader_cache: dict[tuple[str, str], ModelLoader] = {}


def get_loader(alias: Optional[str] = None, source: str = "auto") -> ModelLoader:
    """Return a ModelLoader for the given alias+source combination.

    Called with no args → returns the default singleton (uses MLFLOW_MODEL_ALIAS env var).
    Called with alias/source → creates and caches a dedicated loader on first call.
    Raises RuntimeError for source="dagshub" when the registry is unavailable.
    """
    if alias is None and source == "auto":
        return _loader
    resolved_alias = alias or os.getenv("MLFLOW_MODEL_ALIAS", "champion")
    key = (resolved_alias, source)
    if key not in _loader_cache:
        ldr = ModelLoader(alias=resolved_alias, source=source)
        ldr.load()  # may raise RuntimeError for source="dagshub"
        _loader_cache[key] = ldr
    return _loader_cache[key]
