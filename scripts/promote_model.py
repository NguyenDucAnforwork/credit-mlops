#!/usr/bin/env python3
"""
Promote a model version to an alias in the MLflow registry.
Logs the event to the model_deployment_events Postgres table.

Usage:
    python scripts/promote_model.py --version 8
    python scripts/promote_model.py --version 8 --alias champion --promoted-by alice
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))  # for sibling `_db` import
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import mlflow
import mlflow.tracking
from sqlalchemy import text

from _db import resolve_engine


MODEL_NAME = "credit_score_model"


def _log_event(engine, event_type, alias, from_version, to_version, triggered_by, reason=None):
    if engine is None:
        return
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO model_deployment_events
                (event_type, model_name, alias, from_version, to_version, triggered_by, reason)
            VALUES
                (:et, :mn, :alias, :fv, :tv, :by, :reason)
        """), {"et": event_type, "mn": MODEL_NAME, "alias": alias,
               "fv": from_version, "tv": to_version, "by": triggered_by, "reason": reason})
        conn.commit()


def promote(version: str, alias: str = "champion", promoted_by: str = "unknown") -> None:
    # Resolve the DB connection FIRST. If it is unreachable we surface a clear
    # warning *before* touching the registry, instead of mutating the alias and
    # then crashing on the audit write (the old silent partial-failure).
    engine = resolve_engine(required=False)

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    client = mlflow.MlflowClient()

    try:
        current = client.get_model_version_by_alias(MODEL_NAME, alias)
        from_version = current.version
    except Exception:
        from_version = None

    client.set_registered_model_alias(MODEL_NAME, alias, version)
    print(f"[promote] {alias}: v{from_version} → v{version}")

    if engine is None:
        print("[promote] WARNING: no database connection — deployment event NOT logged")
        return
    _log_event(engine, "promote", alias, from_version, str(version), promoted_by)
    print(f"[promote] deployment event logged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote a model version to an alias")
    parser.add_argument("--version",      required=True, help="Model version number to promote")
    parser.add_argument("--alias",        default="champion", help="Alias to set (default: champion)")
    parser.add_argument("--promoted-by",  default="unknown",  help="Identifier of who is promoting")
    args = parser.parse_args()
    promote(args.version, args.alias, args.promoted_by)
