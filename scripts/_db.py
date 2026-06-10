"""Shared DB helper for the deployment scripts.

Resolves a SQLAlchemy engine from DATABASE_URL with an automatic, connection-tested
fallback from the Docker-internal hostname ``postgres`` to ``localhost``.

Why this exists: ``.env`` ships ``DATABASE_URL=...@postgres:5432/...`` so the API
container can reach Postgres on the compose network. But when an operator runs
``scripts/promote_model.py`` from the *host* shell, ``postgres`` does not resolve,
and the bare ``create_engine`` call used to blow up *after* the MLflow alias had
already been mutated — a silent partial failure (registry changed, audit lost).
``resolve_engine`` probes the configured URL first and, only if that host is
unreachable, retries against ``localhost`` so the same command works from both
inside and outside the compose network.
"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _probe(url: str) -> Optional[Engine]:
    """Return a live engine if a trivial query succeeds, else None."""
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


def resolve_engine(required: bool = False) -> Optional[Engine]:
    """Resolve a working SQLAlchemy engine, or return None.

    1. Try DATABASE_URL exactly as configured.
    2. If that fails and the URL uses the Docker-internal ``@postgres`` host,
       retry against ``@localhost`` (host-shell execution).

    When ``required`` is True and no connection can be established, the process
    exits with a clear message instead of raising a multi-frame psycopg2 traceback.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        msg = "[db] DATABASE_URL not set"
        if required:
            raise SystemExit(f"{msg} — cannot continue")
        print(f"{msg} — deployment event will NOT be logged")
        return None

    engine = _probe(url)
    if engine is not None:
        return engine

    # Host-shell fallback: the compose-internal hostname is unreachable here.
    if "@postgres:" in url or "@postgres/" in url:
        alt = url.replace("@postgres:", "@localhost:").replace("@postgres/", "@localhost/")
        engine = _probe(alt)
        if engine is not None:
            print("[db] '@postgres' host unreachable from this shell — using localhost fallback")
            return engine

    msg = "[db] could not connect to the database (tried configured host and localhost fallback)"
    if required:
        raise SystemExit(f"{msg} — cannot continue")
    print(f"{msg} — deployment event will NOT be logged")
    return None
