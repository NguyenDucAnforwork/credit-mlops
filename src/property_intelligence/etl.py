from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


REQUIRED_COLUMNS = {
    "source_id",
    "title",
    "province",
    "district",
    "property_type",
    "price_vnd",
    "area_m2",
    "latitude",
    "longitude",
    "listed_at",
}


@dataclass(frozen=True)
class BronzeSnapshot:
    snapshot_id: str
    source_name: str
    parser_version: str
    raw_path: Path
    metadata_path: Path
    row_count: int
    sha256: str


@dataclass(frozen=True)
class LayerResult:
    snapshot_id: str
    row_count: int
    output_path: Path
    quarantine_path: Path | None = None
    quarantine_count: int = 0
    duplicate_count: int = 0


@dataclass(frozen=True)
class IncrementalResult:
    inserts: int
    duplicates: int
    output_path: Path


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFC", text).strip()
    return " ".join(text.split())


def normalize_property_type(value: object) -> str:
    text = normalize_text(value).casefold()
    mapping = {
        "apartment": "apartment",
        "can ho": "apartment",
        "căn hộ": "apartment",
        "house": "house",
        "nha": "house",
        "nhà": "house",
        "land": "land",
        "dat": "land",
        "đất": "land",
    }
    return mapping.get(text, text or "unknown")


def deterministic_listing_id(record: dict) -> str:
    parts = [
        normalize_text(record.get("source_id")),
        normalize_text(record.get("province")).casefold(),
        normalize_text(record.get("district")).casefold(),
        normalize_property_type(record.get("property_type")),
        _stable_number(record.get("price_vnd")),
        _stable_number(record.get("area_m2")),
        _stable_number(record.get("latitude"), digits=6),
        _stable_number(record.get("longitude"), digits=6),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def write_bronze_snapshot(
    records: Iterable[dict],
    root_dir: Path,
    source_name: str,
    parser_version: str,
    captured_at: datetime | None = None,
) -> BronzeSnapshot:
    rows = [dict(record) for record in records]
    captured_at = captured_at or datetime.now(tz=UTC)
    payload = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    if payload:
        payload = f"{payload}\n"
    sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    snapshot_id = f"{source_name}_{captured_at.strftime('%Y%m%dT%H%M%SZ')}_{sha256[:12]}"
    snapshot_dir = root_dir / "bronze" / source_name / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    raw_path = snapshot_dir / "records.jsonl"
    metadata_path = snapshot_dir / "metadata.json"
    raw_path.write_text(payload, encoding="utf-8")
    metadata = {
        "snapshot_id": snapshot_id,
        "source_name": source_name,
        "parser_version": parser_version,
        "captured_at": captured_at.isoformat(),
        "row_count": len(rows),
        "sha256": sha256,
        "raw_path": str(raw_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return BronzeSnapshot(
        snapshot_id=snapshot_id,
        source_name=source_name,
        parser_version=parser_version,
        raw_path=raw_path,
        metadata_path=metadata_path,
        row_count=len(rows),
        sha256=sha256,
    )


def build_silver(bronze: BronzeSnapshot, root_dir: Path) -> LayerResult:
    rows = [json.loads(line) for line in bronze.raw_path.read_text(encoding="utf-8").splitlines() if line]
    valid_rows: list[dict] = []
    quarantine_rows: list[dict] = []
    seen_ids: set[str] = set()
    duplicate_count = 0

    for raw in rows:
        normalized, reason = _normalize_record(raw)
        if reason:
            quarantine_rows.append({**raw, "quarantine_reason": reason})
            continue
        listing_id = deterministic_listing_id(normalized)
        normalized["listing_id"] = listing_id
        normalized["snapshot_id"] = bronze.snapshot_id
        if listing_id in seen_ids:
            duplicate_count += 1
            quarantine_rows.append({**normalized, "quarantine_reason": "duplicate_in_snapshot"})
            continue
        seen_ids.add(listing_id)
        valid_rows.append(normalized)

    silver_dir = root_dir / "silver" / bronze.snapshot_id
    quarantine_dir = root_dir / "quarantine" / bronze.snapshot_id
    silver_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    output_path = silver_dir / "listings.parquet"
    quarantine_path = quarantine_dir / "listings_quarantine.parquet"
    pd.DataFrame(valid_rows).to_parquet(output_path, index=False)
    pd.DataFrame(quarantine_rows).to_parquet(quarantine_path, index=False)
    return LayerResult(
        snapshot_id=bronze.snapshot_id,
        row_count=len(valid_rows),
        output_path=output_path,
        quarantine_path=quarantine_path,
        quarantine_count=len(quarantine_rows),
        duplicate_count=duplicate_count,
    )


def build_gold(silver: LayerResult, root_dir: Path) -> LayerResult:
    df = pd.read_parquet(silver.output_path)
    if df.empty:
        gold = df.copy()
    else:
        gold = df.copy()
        gold["price_per_m2"] = gold["price_vnd"] / gold["area_m2"]
        listed = pd.to_datetime(gold["listed_at"], utc=True, errors="coerce")
        gold["listed_year"] = listed.dt.year
        gold["listed_month"] = listed.dt.month
        gold["city_key"] = gold["province"].str.casefold()
        gold["district_key"] = gold["district"].str.casefold()
        gold["h3_r7"] = gold.apply(lambda row: _pseudo_h3(row["latitude"], row["longitude"], 7), axis=1)
        gold["h3_r8"] = gold.apply(lambda row: _pseudo_h3(row["latitude"], row["longitude"], 8), axis=1)
        gold["h3_r9"] = gold.apply(lambda row: _pseudo_h3(row["latitude"], row["longitude"], 9), axis=1)
    gold_dir = root_dir / "gold" / silver.snapshot_id
    gold_dir.mkdir(parents=True, exist_ok=True)
    output_path = gold_dir / "listings_gold.parquet"
    gold.to_parquet(output_path, index=False)
    return LayerResult(snapshot_id=silver.snapshot_id, row_count=len(gold), output_path=output_path)


def incremental_load(
    new_records: Iterable[dict],
    existing_ids: set[str],
    output_path: Path,
) -> IncrementalResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inserted: list[dict] = []
    duplicates = 0
    known = set(existing_ids)
    for record in new_records:
        normalized, reason = _normalize_record(record)
        if reason:
            duplicates += 1
            continue
        listing_id = deterministic_listing_id(normalized)
        if listing_id in known:
            duplicates += 1
            continue
        known.add(listing_id)
        inserted.append({**normalized, "listing_id": listing_id})
    pd.DataFrame(inserted).to_parquet(output_path, index=False)
    return IncrementalResult(inserts=len(inserted), duplicates=duplicates, output_path=output_path)


def _normalize_record(record: dict) -> tuple[dict, str | None]:
    missing = sorted(column for column in REQUIRED_COLUMNS if record.get(column) in (None, ""))
    if missing:
        return {}, f"missing:{','.join(missing)}"
    try:
        price = float(record["price_vnd"])
        area = float(record["area_m2"])
        lat = float(record["latitude"])
        lon = float(record["longitude"])
    except (TypeError, ValueError):
        return {}, "invalid_numeric"
    if not math.isfinite(price) or price <= 0:
        return {}, "invalid_price"
    if not math.isfinite(area) or area <= 0:
        return {}, "invalid_area"
    if not (8.0 <= lat <= 24.5 and 102.0 <= lon <= 110.5):
        return {}, "invalid_coordinates"

    return {
        "source_id": normalize_text(record["source_id"]),
        "title": normalize_text(record["title"]),
        "province": normalize_text(record["province"]),
        "district": normalize_text(record["district"]),
        "property_type": normalize_property_type(record["property_type"]),
        "price_vnd": price,
        "area_m2": area,
        "latitude": lat,
        "longitude": lon,
        "listed_at": normalize_text(record["listed_at"]),
    }, None


def _stable_number(value: object, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:.{digits}f}"


def _pseudo_h3(latitude: float, longitude: float, resolution: int) -> str:
    # Temporary deterministic cell key until the PostGIS/H3 phase installs real H3.
    scale = 10 ** max(resolution - 5, 0)
    lat_key = int(round(float(latitude) * scale))
    lon_key = int(round(float(longitude) * scale))
    return f"r{resolution}_{lat_key}_{lon_key}"
