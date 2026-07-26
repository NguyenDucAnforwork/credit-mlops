"""Property intelligence ingestion and ETL primitives."""

from property_intelligence.etl import (
    build_gold,
    build_silver,
    incremental_load,
    write_bronze_snapshot,
)
from property_intelligence.sources import (
    HuggingFaceDatasetMetadata,
    HuggingFaceShardMetadata,
    build_hf_shard_manifest,
    download_hf_shards,
    fetch_parquet_footer_summary,
    fetch_hf_dataset_metadata,
    hf_resolve_url,
    parse_hf_dataset_metadata,
    write_shard_manifest,
    write_source_metadata,
)

__all__ = [
    "build_gold",
    "build_silver",
    "incremental_load",
    "HuggingFaceDatasetMetadata",
    "HuggingFaceShardMetadata",
    "build_hf_shard_manifest",
    "download_hf_shards",
    "fetch_parquet_footer_summary",
    "fetch_hf_dataset_metadata",
    "hf_resolve_url",
    "parse_hf_dataset_metadata",
    "write_bronze_snapshot",
    "write_shard_manifest",
    "write_source_metadata",
]
