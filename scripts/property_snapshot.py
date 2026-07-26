from __future__ import annotations

import json
from pathlib import Path

from property_intelligence.sources import (
    build_hf_shard_manifest,
    download_hf_shards,
    fetch_hf_dataset_metadata,
    write_shard_manifest,
    write_source_metadata,
)


def main() -> None:
    metadata = fetch_hf_dataset_metadata()
    root = Path("data/raw/vietnam-real-estates") / metadata.revision
    reports_dir = Path("reports/generated")
    evidence_dir = Path("docs/evidence")
    reports_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    write_source_metadata(metadata, reports_dir / "hf_vietnam_real_estates_metadata_20260726.json")
    manifest = build_hf_shard_manifest(metadata, measure_footers=True)
    downloaded = download_hf_shards(manifest, root)
    manifest_path = write_shard_manifest(
        downloaded,
        reports_dir / "hf_vietnam_real_estates_snapshot_manifest_20260726.json",
    )
    summary = {
        "dataset_id": metadata.dataset_id,
        "revision": metadata.revision,
        "raw_snapshot_dir": str(root),
        "parquet_file_count": len(downloaded),
        "total_rows": sum(shard.row_count or 0 for shard in downloaded),
        "total_size_bytes": sum(shard.size_bytes or 0 for shard in downloaded),
        "manifest_path": str(manifest_path),
        "shards": [
            {
                "filename": shard.filename,
                "size_bytes": shard.size_bytes,
                "row_count": shard.row_count,
                "sha256": shard.sha256,
                "etag": shard.etag,
            }
            for shard in downloaded
        ],
    }
    evidence_path = evidence_dir / "hf_snapshot_download_summary_20260726.json"
    evidence_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
