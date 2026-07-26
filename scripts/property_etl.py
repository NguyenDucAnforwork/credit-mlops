from __future__ import annotations

import os
from pathlib import Path

from google.cloud import bigquery, storage

from property_intelligence.hf_etl import run_hf_silver_gold_etl, write_hf_etl_summary
from property_intelligence.sources import (
    build_hf_shard_manifest,
    download_hf_shards,
    fetch_hf_dataset_metadata,
)


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    snapshot_id = metadata.revision
    raw_dir = Path("data/raw/vietnam-real-estates") / snapshot_id
    if not list(raw_dir.glob("*.parquet")):
        manifest = build_hf_shard_manifest(metadata)
        download_hf_shards(manifest, raw_dir)
    summary = run_hf_silver_gold_etl(raw_dir, Path("data"), snapshot_id)
    output_path = Path("reports/generated/hf_vietnam_real_estates_etl_summary_20260726.json")
    evidence_path = Path("docs/evidence/hf_etl_summary_20260726.json")
    write_hf_etl_summary(summary, output_path)
    write_hf_etl_summary(summary, evidence_path)
    _publish_outputs(summary, snapshot_id)
    print(evidence_path.read_text(encoding="utf-8"))


def _publish_outputs(summary, snapshot_id: str) -> None:
    bucket_name = os.environ.get("PROPERTY_DATA_BUCKET")
    dataset_id = os.environ.get("BIGQUERY_DATASET")
    if not bucket_name or not dataset_id:
        raise RuntimeError("PROPERTY_DATA_BUCKET and BIGQUERY_DATASET are required")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    for layer, path in (("silver", summary.silver_path), ("gold", summary.gold_path), ("quarantine", summary.quarantine_path)):
        blob = bucket.blob(f"property/{snapshot_id}/{layer}/listings.parquet")
        blob.upload_from_filename(path)
    bq_client = bigquery.Client()
    for table_name, path in (("property_silver", summary.silver_path), ("property_gold", summary.gold_path), ("property_quarantine", summary.quarantine_path)):
        job = bq_client.load_table_from_uri(
            f"gs://{bucket_name}/property/{snapshot_id}/{table_name.removeprefix('property_')}/listings.parquet",
            f"{bq_client.project}.{dataset_id}.{table_name}",
            job_config=bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.PARQUET, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE),
        )
        job.result()


if __name__ == "__main__":
    main()
