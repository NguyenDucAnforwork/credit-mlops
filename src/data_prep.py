"""
Step 1 of training pipeline: load raw data, compute data_version hash,
split into train/test/reference, log summary stats to MLflow.
"""
import hashlib
import os
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

RAW_DATA_PATH = Path(__file__).parent.parent / "data" / "raw" / "01_dataset.csv"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def compute_data_version(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def load_and_split(
    data_path: Path = RAW_DATA_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    df = pd.read_csv(data_path, low_memory=False)

    # Drop non-feature columns
    df = df.drop(columns=["customer_id"], errors="ignore")

    X = df.drop(columns=["label"])
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )

    train_df = pd.concat([X_train, y_train], axis=1).reset_index(drop=True)
    test_df = pd.concat([X_test, y_test], axis=1).reset_index(drop=True)
    # Reference = training features only (for Evidently drift baseline)
    reference_df = X_train.reset_index(drop=True)

    data_version = compute_data_version(data_path)
    return train_df, test_df, reference_df, data_version


def save_splits(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    out_dir: Path = PROCESSED_DIR,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(out_dir / "train_data.csv", index=False)
    test_df.to_csv(out_dir / "test_data.csv", index=False)
    reference_df.to_csv(out_dir / "reference.csv", index=False)


def log_data_stats(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    data_version: str,
) -> None:
    y_train = train_df["label"]
    y_test = test_df["label"]
    mlflow.log_params({
        "data_version": f"01_dataset_{data_version}",
        "train_size": len(train_df),
        "test_size": len(test_df),
        "n_features_raw": train_df.shape[1] - 1,
    })
    mlflow.log_metrics({
        "train_default_rate": float(y_train.mean()),
        "test_default_rate": float(y_test.mean()),
        "train_missing_rate": float(train_df.isnull().mean().mean()),
    })


def run(log_to_mlflow: bool = True) -> tuple[str, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_df, test_df, reference_df, data_version = load_and_split()
    save_splits(train_df, test_df, reference_df)

    if log_to_mlflow:
        log_data_stats(train_df, test_df, data_version)

    print(f"[data_prep] version={data_version}  train={len(train_df)}  test={len(test_df)}")
    return data_version, train_df, test_df, reference_df


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    run(log_to_mlflow=False)
