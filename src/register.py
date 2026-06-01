"""
Step 4 of training pipeline: register runs to MLflow Model Registry,
promote best model to Production, set alias 'champion'.

Lifecycle: Developing → Staging → Production → Archived
"""
from __future__ import annotations

import os

import mlflow
from mlflow import MlflowClient

MODEL_NAME = "credit_score_model"
EXPERIMENT_NAME = "credit_scoring"


def _client() -> MlflowClient:
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    return MlflowClient()


def register_run(run_id: str, model_name: str = MODEL_NAME) -> str:
    """Register a run's model artifact, returns the new version number."""
    result = mlflow.register_model(
        model_uri=f"runs:/{run_id}/model",
        name=model_name,
    )
    return result.version


def promote_to_champion(version: str, model_name: str = MODEL_NAME) -> None:
    """Set alias 'champion' on the given version and archive others."""
    client = _client()

    # Archive any existing champion
    try:
        current = client.get_model_version_by_alias(model_name, "champion")
        if current.version != version:
            client.delete_registered_model_alias(model_name, "champion")
    except Exception:
        pass

    client.set_registered_model_alias(model_name, "champion", version)
    print(f"[register] champion → {model_name} v{version}")


def promote_to_challenger(version: str, model_name: str = MODEL_NAME) -> None:
    client = _client()
    try:
        client.delete_registered_model_alias(model_name, "challenger")
    except Exception:
        pass
    client.set_registered_model_alias(model_name, "challenger", version)
    print(f"[register] challenger → {model_name} v{version}")


def get_champion_version(model_name: str = MODEL_NAME) -> str | None:
    client = _client()
    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
        return mv.version
    except Exception:
        return None


def get_latest_versions(model_name: str = MODEL_NAME) -> list:
    """Return all registered versions sorted by creation time (newest first)."""
    client = _client()
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
        return sorted(versions, key=lambda v: int(v.version), reverse=True)
    except Exception:
        return []


def promote_to_scorecard(version: str, model_name: str = MODEL_NAME) -> None:
    client = _client()
    try:
        client.delete_registered_model_alias(model_name, "scorecard")
    except Exception:
        pass
    client.set_registered_model_alias(model_name, "scorecard", version)
    print(f"[register] scorecard → {model_name} v{version}")


def run(lr_run_id: str, xgb_run_id: str, sc_run_id: str | None = None) -> None:
    """
    Models are registered inline in train.py (MLflow 3.x).
    This step looks up new versions by run_id and sets aliases:
      LR  → challenger
      XGB → champion
      SC  → scorecard
    """
    client = _client()
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])

    def find_version_for_run(run_id: str) -> str | None:
        versions = client.search_model_versions(f"name='{MODEL_NAME}'")
        for v in versions:
            if v.run_id == run_id:
                return v.version
        return None

    lr_version = find_version_for_run(lr_run_id)
    xgb_version = find_version_for_run(xgb_run_id)

    if lr_version:
        promote_to_challenger(lr_version)
        print(f"[register] LR  → v{lr_version} (challenger)")
    else:
        print(f"[register] WARNING: LR version not found for run {lr_run_id}")

    if xgb_version:
        promote_to_champion(xgb_version)
        print(f"[register] XGB → v{xgb_version} (champion)")
    else:
        print(f"[register] WARNING: XGB version not found for run {xgb_run_id}")

    if sc_run_id:
        sc_version = find_version_for_run(sc_run_id)
        if sc_version:
            promote_to_scorecard(sc_version)
            print(f"[register] SC  → v{sc_version} (scorecard)")
        else:
            print(f"[register] WARNING: Scorecard version not found for run {sc_run_id}")
