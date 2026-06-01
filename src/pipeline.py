"""
Training pipeline DAG orchestrator.
Steps: data_prep → features → train → register
Each step logs inputs/outputs to MLflow for full traceability.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src/ to path so steps can import siblings
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv(Path(__file__).parent.parent / ".env")

import mlflow

import data_prep
import features as feat
import register
import train


def run_pipeline(skip_data_prep: bool = False, skip_feature_fit: bool = False) -> None:
    """
    Full training pipeline. Set skip_* flags to resume from a later step
    when data/features haven't changed (cache behaviour).
    """
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("credit_scoring")

    # ── Step 1: Data prep ────────────────────────────────────────────────────
    if skip_data_prep:
        import hashlib
        raw = Path(__file__).parent.parent / "data" / "raw" / "01_dataset.csv"
        h = hashlib.sha256()
        with open(raw, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        data_version = h.hexdigest()[:8]
        print(f"[pipeline] skip data_prep, using cached data_version={data_version}")
    else:
        data_version, _, _, _ = data_prep.run(log_to_mlflow=False)

    # ── Step 2: Feature pipeline ──────────────────────────────────────────────
    if skip_feature_fit:
        fp = feat.FeaturePipeline.load()
        print(f"[pipeline] skip feature fit, loaded from artifacts")
    else:
        import pandas as pd
        processed = Path(__file__).parent.parent / "data" / "processed"
        train_df = pd.read_csv(processed / "train_data.csv")
        X_train = train_df.drop(columns=["label"])
        y_train = train_df["label"]

        fp = feat.FeaturePipeline()
        fp.fit_transform(X_train, y_train)
        fp.save()
        print(f"[pipeline] feature pipeline fitted: {fp.n_features_out()} features out")

    # ── Step 3: Train ─────────────────────────────────────────────────────────
    lr_run_id, xgb_run_id, sc_run_id = train.run(data_version)

    # ── Step 4: Register ──────────────────────────────────────────────────────
    register.run(lr_run_id, xgb_run_id, sc_run_id)

    print("\n[pipeline] DONE — champion model registered on DagsHub MLflow")
    print(f"  LR  run: {lr_run_id}")
    print(f"  XGB run: {xgb_run_id}")
    print(f"  SC  run: {sc_run_id}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-data-prep", action="store_true")
    parser.add_argument("--skip-feature-fit", action="store_true")
    args = parser.parse_args()
    run_pipeline(
        skip_data_prep=args.skip_data_prep,
        skip_feature_fit=args.skip_feature_fit,
    )
