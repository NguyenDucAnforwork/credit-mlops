from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen


HF_DATASET_ID = "vduydong/vietnam-real-estates"
HF_API_URL = f"https://huggingface.co/api/datasets/{HF_DATASET_ID}"


@dataclass(frozen=True)
class HuggingFaceDatasetMetadata:
    dataset_id: str
    revision: str
    last_modified: str | None
    parquet_files: tuple[str, ...]
    downloads: int | None
    likes: int | None
    captured_at: str


def parse_hf_dataset_metadata(payload: dict, captured_at: datetime | None = None) -> HuggingFaceDatasetMetadata:
    captured_at = captured_at or datetime.now(tz=UTC)
    siblings = payload.get("siblings") or []
    parquet_files = tuple(
        sorted(
            item["rfilename"]
            for item in siblings
            if isinstance(item, dict) and str(item.get("rfilename", "")).endswith(".parquet")
        )
    )
    revision = payload.get("sha")
    dataset_id = payload.get("id") or HF_DATASET_ID
    if not revision:
        raise ValueError("Hugging Face dataset metadata did not include a revision sha")
    return HuggingFaceDatasetMetadata(
        dataset_id=dataset_id,
        revision=revision,
        last_modified=payload.get("lastModified"),
        parquet_files=parquet_files,
        downloads=payload.get("downloads"),
        likes=payload.get("likes"),
        captured_at=captured_at.isoformat(),
    )


def fetch_hf_dataset_metadata(api_url: str = HF_API_URL) -> HuggingFaceDatasetMetadata:
    with urlopen(api_url, timeout=30) as response:  # nosec B310 - fixed public HF API URL by default
        payload = json.loads(response.read().decode("utf-8"))
    return parse_hf_dataset_metadata(payload)


def write_source_metadata(metadata: HuggingFaceDatasetMetadata, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "dataset_id": metadata.dataset_id,
                "revision": metadata.revision,
                "last_modified": metadata.last_modified,
                "parquet_files": list(metadata.parquet_files),
                "parquet_file_count": len(metadata.parquet_files),
                "downloads": metadata.downloads,
                "likes": metadata.likes,
                "captured_at": metadata.captured_at,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return output_path
