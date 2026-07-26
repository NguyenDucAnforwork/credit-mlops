from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from property_intelligence.etl import normalize_property_type, normalize_text


HF_COLUMNS = [
    "name",
    "description",
    "property_type_name",
    "province_name",
    "district_name",
    "ward_name",
    "street_name",
    "project_name",
    "price",
    "area",
    "floor_count",
    "frontage_width",
    "house_depth",
    "road_width",
    "bedroom_count",
    "bathroom_count",
    "house_direction",
    "balcony_direction",
    "published_at",
]

MVP_CITIES = {"Hà Nội", "Hồ Chí Minh"}


@dataclass(frozen=True)
class HFEtlSummary:
    snapshot_id: str
    raw_rows: int
    silver_rows: int
    gold_rows: int
    quarantine_rows: int
    duplicate_rows: int
    missing_coordinate_columns: tuple[str, ...]
    silver_path: str
    gold_path: str
    quarantine_path: str


def run_hf_silver_gold_etl(
    raw_snapshot_dir: Path,
    output_root: Path,
    snapshot_id: str,
) -> HFEtlSummary:
    shard_paths = sorted(raw_snapshot_dir.glob("*.parquet"))
    if not shard_paths:
        raise FileNotFoundError(f"No Parquet shards found in {raw_snapshot_dir}")

    silver_frames: list[pd.DataFrame] = []
    quarantine_frames: list[pd.DataFrame] = []
    seen_ids: set[str] = set()
    raw_rows = 0
    duplicate_rows = 0

    for shard_path in shard_paths:
        raw = pd.read_parquet(shard_path, columns=HF_COLUMNS)
        raw_rows += len(raw)
        normalized = normalize_hf_frame(raw, shard_path.name, snapshot_id)
        invalid_mask = normalized["quarantine_reason"].notna()
        duplicate_mask = pd.Series(False, index=normalized.index)
        for idx, listing_id in normalized.loc[~invalid_mask, "listing_id"].items():
            if listing_id in seen_ids:
                duplicate_mask.loc[idx] = True
            else:
                seen_ids.add(listing_id)
        normalized.loc[duplicate_mask, "quarantine_reason"] = "duplicate_listing_id"
        duplicate_rows += int(duplicate_mask.sum())
        silver_frames.append(normalized.loc[normalized["quarantine_reason"].isna()].drop(columns=["quarantine_reason"]))
        quarantine_frames.append(normalized.loc[normalized["quarantine_reason"].notna()])

    silver = pd.concat(silver_frames, ignore_index=True) if silver_frames else pd.DataFrame()
    quarantine = pd.concat(quarantine_frames, ignore_index=True) if quarantine_frames else pd.DataFrame()
    gold = build_hf_gold(silver)

    silver_path = output_root / "silver" / snapshot_id / "listings.parquet"
    gold_path = output_root / "gold" / snapshot_id / "listings_gold.parquet"
    quarantine_path = output_root / "quarantine" / snapshot_id / "listings_quarantine.parquet"
    for path in (silver_path, gold_path, quarantine_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(silver_path, index=False)
    gold.to_parquet(gold_path, index=False)
    quarantine.to_parquet(quarantine_path, index=False)

    return HFEtlSummary(
        snapshot_id=snapshot_id,
        raw_rows=raw_rows,
        silver_rows=len(silver),
        gold_rows=len(gold),
        quarantine_rows=len(quarantine),
        duplicate_rows=duplicate_rows,
        missing_coordinate_columns=("latitude", "longitude"),
        silver_path=str(silver_path),
        gold_path=str(gold_path),
        quarantine_path=str(quarantine_path),
    )


def normalize_hf_frame(raw: pd.DataFrame, shard_name: str, snapshot_id: str) -> pd.DataFrame:
    df = pd.DataFrame()
    df["source_dataset"] = "vduydong/vietnam-real-estates"
    df["snapshot_id"] = snapshot_id
    df["source_shard"] = shard_name
    df["title"] = raw["name"].map(normalize_text)
    df["description"] = raw["description"].map(normalize_text)
    df["property_type"] = raw["property_type_name"].map(normalize_property_type)
    df["province"] = raw["province_name"].map(normalize_text)
    df["district"] = raw["district_name"].map(normalize_text)
    df["ward"] = raw["ward_name"].map(normalize_text)
    df["street"] = raw["street_name"].map(normalize_text)
    df["project"] = raw["project_name"].map(normalize_text)
    df["price_vnd"] = pd.to_numeric(raw["price"], errors="coerce")
    df["area_m2"] = pd.to_numeric(raw["area"], errors="coerce")
    df["floor_count"] = pd.to_numeric(raw["floor_count"], errors="coerce")
    df["frontage_width"] = pd.to_numeric(raw["frontage_width"], errors="coerce")
    df["house_depth"] = pd.to_numeric(raw["house_depth"], errors="coerce")
    df["road_width"] = pd.to_numeric(raw["road_width"], errors="coerce")
    df["bedroom_count"] = pd.to_numeric(raw["bedroom_count"], errors="coerce")
    df["bathroom_count"] = pd.to_numeric(raw["bathroom_count"], errors="coerce")
    df["house_direction"] = raw["house_direction"].map(normalize_text)
    df["balcony_direction"] = raw["balcony_direction"].map(normalize_text)
    df["published_at"] = pd.to_datetime(raw["published_at"], errors="coerce", utc=True)
    df["latitude"] = pd.NA
    df["longitude"] = pd.NA
    df["coordinate_status"] = "missing_source_columns"
    df["listing_id"] = pd.util.hash_pandas_object(
        df[
            [
                "title",
                "province",
                "district",
                "ward",
                "street",
                "property_type",
                "price_vnd",
                "area_m2",
                "published_at",
            ]
        ],
        index=False,
    ).astype(str)
    df["quarantine_reason"] = pd.NA
    df.loc[df["title"].eq(""), "quarantine_reason"] = "missing_title"
    df.loc[df["province"].eq(""), "quarantine_reason"] = "missing_province"
    df.loc[df["district"].eq(""), "quarantine_reason"] = "missing_district"
    df.loc[df["published_at"].isna(), "quarantine_reason"] = "invalid_published_at"
    df.loc[df["price_vnd"].isna() | (df["price_vnd"] <= 0), "quarantine_reason"] = "invalid_price"
    df.loc[df["area_m2"].isna() | (df["area_m2"] <= 0), "quarantine_reason"] = "invalid_area"
    return df


def build_hf_gold(silver: pd.DataFrame) -> pd.DataFrame:
    if silver.empty:
        return silver.copy()
    gold = silver.loc[silver["province"].isin(MVP_CITIES)].copy()
    gold["price_per_m2"] = gold["price_vnd"] / gold["area_m2"]
    gold["published_year"] = gold["published_at"].dt.year
    gold["published_month"] = gold["published_at"].dt.month
    gold["published_quarter"] = gold["published_at"].dt.quarter
    gold["city_key"] = gold["province"].str.casefold()
    gold["district_key"] = gold["district"].str.casefold()
    return gold


def write_hf_etl_summary(summary: HFEtlSummary, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "snapshot_id": summary.snapshot_id,
                "raw_rows": summary.raw_rows,
                "silver_rows": summary.silver_rows,
                "gold_rows": summary.gold_rows,
                "quarantine_rows": summary.quarantine_rows,
                "duplicate_rows": summary.duplicate_rows,
                "missing_coordinate_columns": list(summary.missing_coordinate_columns),
                "silver_path": summary.silver_path,
                "gold_path": summary.gold_path,
                "quarantine_path": summary.quarantine_path,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return output_path
