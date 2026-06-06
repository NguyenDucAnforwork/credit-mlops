"""Benchmark the KNNImputer neighbor count used in the feature pipeline.

This script measures only the expensive imputation step on the processed
training features so we can compare n_neighbors=20 vs 10 vs 5.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from sklearn.impute import KNNImputer

ROOT = Path(__file__).resolve().parents[1]
TRAIN_CSV = ROOT / "data" / "processed" / "train_data.csv"
REPEATS = 3
NEIGHBORS = (20, 10, 5)


def benchmark() -> None:
    train_df = pd.read_csv(TRAIN_CSV)
    X = train_df.drop(columns=["label"]).values

    print(f"dataset_shape={X.shape}")
    print("n_neighbors,min_s,mean_s,max_s")

    for k in NEIGHBORS:
        timings: list[float] = []
        for _ in range(REPEATS):
            imputer = KNNImputer(n_neighbors=k)
            t0 = time.perf_counter()
            _ = imputer.fit_transform(X)
            timings.append(time.perf_counter() - t0)

        print(
            f"{k},{min(timings):.4f},{sum(timings) / len(timings):.4f},{max(timings):.4f}"
        )


if __name__ == "__main__":
    benchmark()
