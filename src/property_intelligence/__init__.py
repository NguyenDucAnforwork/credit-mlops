"""Property intelligence ingestion and ETL primitives."""

from property_intelligence.etl import (
    build_gold,
    build_silver,
    incremental_load,
    write_bronze_snapshot,
)
from property_intelligence.sources import (
    HuggingFaceDatasetMetadata,
    fetch_hf_dataset_metadata,
    parse_hf_dataset_metadata,
    write_source_metadata,
)

__all__ = [
    "build_gold",
    "build_silver",
    "incremental_load",
    "HuggingFaceDatasetMetadata",
    "fetch_hf_dataset_metadata",
    "parse_hf_dataset_metadata",
    "write_bronze_snapshot",
    "write_source_metadata",
]
