#!/usr/bin/env python3
"""
Roll back an alias to the previous version recorded in model_deployment_events.

Usage:
    python scripts/rollback_model.py
    python scripts/rollback_model.py --alias scorecard --reason "P95 latency spike" --triggered-by alice
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
from sqlalchemy import text

from _db import resolve_engine


MODEL_NAME = "credit_score_model"


def rollback(alias: str = "champion", reason: str = "manual rollback",
             triggered_by: str = "unknown") -> None:
    # Rollback needs the DB to find the previous version, so it is required.
    # resolve_engine handles the '@postgres' -> 'localhost' host-shell fallback
    # and exits with a clear message (not a psycopg2 traceback) if unreachable.
    engine = resolve_engine(required=True)

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT from_version, to_version
            FROM   model_deployment_events
            WHERE  alias      = :alias
              AND  event_type = 'promote'
            ORDER  BY ts DESC
            LIMIT  1
        """), {"alias": alias}).fetchone()

    if row is None or row.from_version is None:
        print(f"[rollback] No previous version found for alias '{alias}' in deployment_events")
        sys.exit(1)

    current_version  = row.to_version
    rollback_version = row.from_version

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    client = mlflow.MlflowClient()
    client.set_registered_model_alias(MODEL_NAME, alias, rollback_version)
    print(f"[rollback] {alias}: v{current_version} → v{rollback_version}  reason={reason!r}")

    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO model_deployment_events
                (event_type, model_name, alias, from_version, to_version, triggered_by, reason)
            VALUES
                ('rollback', :mn, :alias, :fv, :tv, :by, :reason)
        """), {"mn": MODEL_NAME, "alias": alias, "fv": current_version,
               "tv": rollback_version, "by": triggered_by, "reason": reason})
        conn.commit()
    print("[rollback] deployment event logged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roll back alias to previous version")
    parser.add_argument("--alias",        default="champion")
    parser.add_argument("--reason",       default="manual rollback")
    parser.add_argument("--triggered-by", default="unknown")
    args = parser.parse_args()
    rollback(args.alias, args.reason, args.triggered_by)
