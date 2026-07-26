from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from property_intelligence.sources import parse_hf_dataset_metadata, write_source_metadata


def _payload():
    return {
        "id": "vduydong/vietnam-real-estates",
        "sha": "abc123",
        "lastModified": "2026-04-08T06:51:21.000Z",
        "downloads": 15,
        "likes": 0,
        "siblings": [
            {"rfilename": "README.md"},
            {"rfilename": "shard_0001.parquet"},
            {"rfilename": "shard_0000.parquet"},
        ],
    }


def test_parse_hf_dataset_metadata_keeps_revision_and_parquet_files():
    metadata = parse_hf_dataset_metadata(
        _payload(),
        captured_at=datetime(2026, 7, 26, 7, 0, tzinfo=UTC),
    )

    assert metadata.dataset_id == "vduydong/vietnam-real-estates"
    assert metadata.revision == "abc123"
    assert metadata.parquet_files == ("shard_0000.parquet", "shard_0001.parquet")
    assert metadata.downloads == 15
    assert metadata.captured_at == "2026-07-26T07:00:00+00:00"


def test_parse_hf_dataset_metadata_requires_revision():
    payload = _payload()
    payload.pop("sha")

    with pytest.raises(ValueError, match="revision sha"):
        parse_hf_dataset_metadata(payload)


def test_write_source_metadata_records_file_count(tmp_path):
    metadata = parse_hf_dataset_metadata(_payload())
    output_path = write_source_metadata(metadata, tmp_path / "source.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["dataset_id"] == "vduydong/vietnam-real-estates"
    assert payload["revision"] == "abc123"
    assert payload["parquet_file_count"] == 2
