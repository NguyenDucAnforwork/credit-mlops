from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import pyarrow.parquet as pq


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


@dataclass(frozen=True)
class HuggingFaceShardMetadata:
    filename: str
    url: str
    size_bytes: int | None
    etag: str | None
    xet_hash: str | None
    row_count: int | None = None
    num_columns: int | None = None
    num_row_groups: int | None = None
    footer_size_bytes: int | None = None


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


def hf_resolve_url(
    filename: str,
    revision: str,
    dataset_id: str = HF_DATASET_ID,
) -> str:
    return f"https://huggingface.co/datasets/{dataset_id}/resolve/{revision}/{filename}"


def build_hf_shard_manifest(
    metadata: HuggingFaceDatasetMetadata,
    measure_footers: bool = False,
) -> list[HuggingFaceShardMetadata]:
    shards: list[HuggingFaceShardMetadata] = []
    for filename in metadata.parquet_files:
        url = hf_resolve_url(filename, metadata.revision, metadata.dataset_id)
        headers = _head_headers(url)
        size = _int_header(headers, "content-length") or _int_header(headers, "x-linked-size")
        etag = _strip_quotes(headers.get("etag") or headers.get("x-linked-etag"))
        xet_hash = headers.get("x-xet-hash")
        row_count = num_columns = num_row_groups = footer_size_bytes = None
        if measure_footers:
            if size is None:
                raise ValueError(f"Cannot measure Parquet footer without size for {filename}")
            row_count, num_columns, num_row_groups, footer_size_bytes = fetch_parquet_footer_summary(url, size)
        shards.append(
            HuggingFaceShardMetadata(
                filename=filename,
                url=url,
                size_bytes=size,
                etag=etag,
                xet_hash=xet_hash,
                row_count=row_count,
                num_columns=num_columns,
                num_row_groups=num_row_groups,
                footer_size_bytes=footer_size_bytes,
            )
        )
    return shards


def fetch_parquet_footer_summary(url: str, size_bytes: int) -> tuple[int, int, int, int]:
    tail = _read_http_range(url, size_bytes - 8, size_bytes - 1)
    if len(tail) != 8 or tail[-4:] != b"PAR1":
        raise ValueError("Remote object does not have a valid Parquet footer")
    footer_len = int.from_bytes(tail[:4], "little")
    footer_start = size_bytes - 8 - footer_len
    footer = _read_http_range(url, footer_start, size_bytes - 1)
    metadata = pq.read_metadata(BytesIO(footer))
    return metadata.num_rows, metadata.num_columns, metadata.num_row_groups, len(footer)


def write_shard_manifest(shards: Iterable[HuggingFaceShardMetadata], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            [
                {
                    "filename": shard.filename,
                    "url": shard.url,
                    "size_bytes": shard.size_bytes,
                    "etag": shard.etag,
                    "xet_hash": shard.xet_hash,
                    "row_count": shard.row_count,
                    "num_columns": shard.num_columns,
                    "num_row_groups": shard.num_row_groups,
                    "footer_size_bytes": shard.footer_size_bytes,
                }
                for shard in shards
            ],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return output_path


def _head_headers(url: str) -> dict[str, str]:
    with urlopen(Request(url, method="HEAD"), timeout=30) as response:  # nosec B310
        return {key.casefold(): value for key, value in response.headers.items()}


def _read_http_range(url: str, start: int, end: int) -> bytes:
    request = Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urlopen(request, timeout=60) as response:  # nosec B310
        return response.read()


def _int_header(headers: dict[str, str], name: str) -> int | None:
    value = headers.get(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _strip_quotes(value: str | None) -> str | None:
    return value.strip('"') if value else None
