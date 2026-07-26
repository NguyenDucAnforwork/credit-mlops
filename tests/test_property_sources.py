from __future__ import annotations

import json
from io import BytesIO
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from property_intelligence import sources
from property_intelligence.sources import (
    build_hf_shard_manifest,
    fetch_parquet_footer_summary,
    hf_resolve_url,
    parse_hf_dataset_metadata,
    write_shard_manifest,
    write_source_metadata,
)


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


def test_hf_resolve_url_uses_revision():
    assert hf_resolve_url("shard_0000.parquet", "abc123").endswith(
        "/vduydong/vietnam-real-estates/resolve/abc123/shard_0000.parquet"
    )


def test_build_hf_shard_manifest_uses_head_metadata(monkeypatch):
    metadata = parse_hf_dataset_metadata(_payload())

    def fake_head(url):
        return {
            "content-length": "123",
            "etag": '"etag-1"',
            "x-xet-hash": "hash-1",
        }

    monkeypatch.setattr(sources, "_head_headers", fake_head)

    manifest = build_hf_shard_manifest(metadata)

    assert [shard.filename for shard in manifest] == ["shard_0000.parquet", "shard_0001.parquet"]
    assert manifest[0].size_bytes == 123
    assert manifest[0].etag == "etag-1"
    assert manifest[0].xet_hash == "hash-1"
    assert manifest[0].row_count is None


def test_fetch_parquet_footer_summary_reads_only_footer(monkeypatch):
    table = pa.table({"price": [1, 2, 3], "area": [10, 20, 30]})
    sink = BytesIO()
    pq.write_table(table, sink)
    payload = sink.getvalue()

    def fake_range(_url, start, end):
        return payload[start : end + 1]

    monkeypatch.setattr(sources, "_read_http_range", fake_range)

    rows, columns, row_groups, footer_size = fetch_parquet_footer_summary(
        "https://example.test/shard.parquet",
        len(payload),
    )

    assert rows == 3
    assert columns == 2
    assert row_groups == 1
    assert footer_size > 8


def test_write_shard_manifest_records_footer_metrics(tmp_path, monkeypatch):
    metadata = parse_hf_dataset_metadata(_payload())

    monkeypatch.setattr(
        sources,
        "_head_headers",
        lambda _url: {"content-length": "456", "etag": '"etag-2"'},
    )
    monkeypatch.setattr(
        sources,
        "fetch_parquet_footer_summary",
        lambda _url, _size: (200000, 19, 1, 10637),
    )

    manifest = build_hf_shard_manifest(metadata, measure_footers=True)
    output_path = write_shard_manifest(manifest, tmp_path / "manifest.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload[0]["row_count"] == 200000
    assert payload[0]["num_columns"] == 19
    assert payload[0]["footer_size_bytes"] == 10637
