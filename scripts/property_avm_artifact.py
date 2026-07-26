from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import pandas as pd

from property_intelligence.avm import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TabularHgbQuantileArtifact,
    fit_tabular_hgb_quantile_artifact,
    write_avm_report,
)
from property_intelligence.sources import fetch_hf_dataset_metadata


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    columns = sorted(
        set(
            [
                "published_at",
                "price_vnd",
                "price_per_m2",
                *NUMERIC_FEATURES,
                *CATEGORICAL_FEATURES,
            ]
        )
    )
    gold = pd.read_parquet(Path("data/gold") / snapshot_id / "listings_gold.parquet", columns=columns)
    artifact_path = Path("artifacts/models/property_avm_hgb_quantile_20260726.joblib")

    train_start = perf_counter()
    artifact, report = fit_tabular_hgb_quantile_artifact(gold, snapshot_id=snapshot_id)
    train_eval_seconds = perf_counter() - train_start
    artifact.save(artifact_path)

    load_start = perf_counter()
    loaded = TabularHgbQuantileArtifact.load(artifact_path)
    load_latency_ms = (perf_counter() - load_start) * 1000

    sample = gold.loc[gold["published_at"].notna()].iloc[0][NUMERIC_FEATURES + CATEGORICAL_FEATURES].to_dict()
    predict_start = perf_counter()
    sample_prediction = loaded.predict_one(sample)
    predict_latency_ms = (perf_counter() - predict_start) * 1000

    second_artifact, second_report = fit_tabular_hgb_quantile_artifact(gold, snapshot_id=snapshot_id)
    del second_artifact
    mdape_diff_points = abs(
        report["point_metrics"]["mdape"] - second_report["point_metrics"]["mdape"]
    ) * 100

    size_bytes = artifact_path.stat().st_size
    report.update(
        {
            "artifact": {
                "path": str(artifact_path),
                "size_bytes": size_bytes,
                "size_mb": size_bytes / (1024 * 1024),
                "size_limit_mb": 150,
                "load_latency_ms": load_latency_ms,
                "single_prediction_latency_ms": predict_latency_ms,
                "same_seed_mdape_diff_points": mdape_diff_points,
                "same_seed_mdape_diff_limit_points": 0.3,
            },
            "runtime": {
                "train_eval_seconds": train_eval_seconds,
            },
            "sample_prediction": sample_prediction,
        }
    )

    reports_path = Path("reports/generated/avm_hgb_quantile_artifact_20260726.json")
    evidence_path = Path("docs/evidence/avm_hgb_quantile_artifact_20260726.json")
    write_avm_report(report, reports_path)
    write_avm_report(report, evidence_path)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
