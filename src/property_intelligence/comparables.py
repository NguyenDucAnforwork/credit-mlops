from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable

import numpy as np
import pandas as pd


COMPARABLE_COLUMNS = [
    "listing_id",
    "published_at",
    "province",
    "district",
    "ward",
    "street",
    "project",
    "property_type",
    "price_vnd",
    "area_m2",
    "price_per_m2",
]


@dataclass(frozen=True)
class ComparableQuery:
    listing_id: str | None
    published_at: str
    province: str
    district: str
    property_type: str
    area_m2: float


@dataclass(frozen=True)
class ComparableResult:
    listing_id: str
    province: str
    district: str
    ward: str
    property_type: str
    price_vnd: float
    area_m2: float
    price_per_m2: float
    published_at: str
    match_tier: str
    area_ratio: float
    recency_days: float
    distance_m: None
    distance_status: str


class NonGisComparableIndex:
    def __init__(self, listings: pd.DataFrame) -> None:
        self.listings = _clean_listings(listings)
        self.groups = {
            ("province", "district", "property_type"): _build_groups(
                self.listings,
                ["province", "district", "property_type"],
            ),
            ("province", "district"): _build_groups(self.listings, ["province", "district"]),
            ("province", "property_type"): _build_groups(self.listings, ["province", "property_type"]),
            ("province",): _build_groups(self.listings, ["province"]),
        }

    def query(
        self,
        query: ComparableQuery,
        max_results: int = 10,
        area_tolerance: float = 0.25,
    ) -> dict:
        as_of = _utc_timestamp(query.published_at)
        candidates: list[pd.DataFrame] = []
        tier_counts: dict[str, int] = {}
        for columns, group_map in self.groups.items():
            key = tuple(getattr(query, column) for column in columns)
            group = group_map.get(key)
            tier_name = "+".join(columns)
            if group is None:
                tier_counts[tier_name] = 0
                continue
            filtered = _filter_candidates(
                group,
                query=query,
                as_of=as_of,
                area_tolerance=area_tolerance,
            )
            tier_counts[tier_name] = len(filtered)
            if not filtered.empty:
                candidates.append(filtered.assign(match_tier=tier_name))
            if sum(len(candidate) for candidate in candidates) >= max_results:
                break

        combined = pd.concat(candidates, ignore_index=True) if candidates else pd.DataFrame()
        if not combined.empty:
            combined = combined.drop_duplicates("listing_id")
            combined["area_delta"] = (combined["area_m2"] - query.area_m2).abs()
            combined["recency_days"] = (as_of - combined["published_at"]).dt.total_seconds() / 86400
            combined = combined.sort_values(["area_delta", "recency_days", "price_per_m2"]).head(max_results)
        comparables = [_row_to_result(row, query.area_m2).__dict__ for _, row in combined.iterrows()]
        return {
            "query": query.__dict__,
            "count": len(comparables),
            "max_results": max_results,
            "area_tolerance": area_tolerance,
            "support_level": _support_level(len(comparables)),
            "match_tier_counts": tier_counts,
            "distance_status": "not_available_missing_coordinates",
            "warnings": ["source dataset lacks latitude/longitude; comparable distance and radius fallback unavailable"],
            "comparables": comparables,
        }


def benchmark_comparable_queries(
    listings: pd.DataFrame,
    queries: Iterable[ComparableQuery],
    max_results: int = 10,
) -> dict:
    index = NonGisComparableIndex(listings)
    latencies_ms: list[float] = []
    counts: list[int] = []
    support: list[str] = []
    errors = 0
    for query in queries:
        start = perf_counter()
        try:
            result = index.query(query, max_results=max_results)
        except Exception:
            errors += 1
            continue
        latencies_ms.append((perf_counter() - start) * 1000)
        counts.append(result["count"])
        support.append(result["support_level"])
    latency_array = np.array(latencies_ms, dtype=float)
    count_array = np.array(counts, dtype=float)
    return {
        "method": "non_gis_pandas_comparable_fallback",
        "query_count": len(latencies_ms),
        "error_count": errors,
        "valid_request_error_rate": float(errors / max(len(latencies_ms) + errors, 1)),
        "latency_ms": {
            "median": float(np.median(latency_array)) if len(latency_array) else None,
            "p95": float(np.quantile(latency_array, 0.95)) if len(latency_array) else None,
            "max": float(np.max(latency_array)) if len(latency_array) else None,
        },
        "comparable_count": {
            "median": float(np.median(count_array)) if len(count_array) else None,
            "mean": float(np.mean(count_array)) if len(count_array) else None,
            "min": int(np.min(count_array)) if len(count_array) else None,
            "max": int(np.max(count_array)) if len(count_array) else None,
        },
        "support_share": {level: float(np.mean(np.array(support) == level)) for level in ("high", "medium", "low")},
        "distance_status": "not_available_missing_coordinates",
        "postgis_criterion_status": "blocked_missing_coordinates_and_postgis",
    }


def comparable_queries_from_frame(frame: pd.DataFrame) -> list[ComparableQuery]:
    clean = _clean_listings(frame)
    return [
        ComparableQuery(
            listing_id=str(row.listing_id),
            published_at=row.published_at.isoformat(),
            province=row.province,
            district=row.district,
            property_type=row.property_type,
            area_m2=float(row.area_m2),
        )
        for row in clean.itertuples(index=False)
    ]


def _clean_listings(listings: pd.DataFrame) -> pd.DataFrame:
    clean = listings.copy()
    for column in COMPARABLE_COLUMNS:
        if column not in clean.columns:
            clean[column] = ""
    clean = clean.loc[
        clean["published_at"].notna()
        & clean["price_vnd"].notna()
        & clean["area_m2"].notna()
        & clean["price_per_m2"].notna()
        & (clean["price_vnd"] > 0)
        & (clean["area_m2"] > 0)
    ].copy()
    clean["published_at"] = pd.to_datetime(clean["published_at"], utc=True)
    for column in ("listing_id", "province", "district", "ward", "street", "project", "property_type"):
        clean[column] = clean[column].fillna("").astype(str)
    return clean


def _build_groups(listings: pd.DataFrame, columns: list[str]) -> dict[tuple[str, ...], pd.DataFrame]:
    groups: dict[tuple[str, ...], pd.DataFrame] = {}
    for key, group in listings.groupby(columns, dropna=False):
        normalized_key = key if isinstance(key, tuple) else (key,)
        groups[normalized_key] = group.sort_values("published_at")
    return groups


def _filter_candidates(
    group: pd.DataFrame,
    query: ComparableQuery,
    as_of: pd.Timestamp,
    area_tolerance: float,
) -> pd.DataFrame:
    lower_area = query.area_m2 * (1 - area_tolerance)
    upper_area = query.area_m2 * (1 + area_tolerance)
    mask = (
        (group["published_at"] < as_of)
        & (group["area_m2"] >= lower_area)
        & (group["area_m2"] <= upper_area)
    )
    if query.listing_id:
        mask &= group["listing_id"] != query.listing_id
    return group.loc[mask]


def _utc_timestamp(value: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _row_to_result(row: pd.Series, subject_area_m2: float) -> ComparableResult:
    return ComparableResult(
        listing_id=str(row["listing_id"]),
        province=str(row["province"]),
        district=str(row["district"]),
        ward=str(row["ward"]),
        property_type=str(row["property_type"]),
        price_vnd=float(row["price_vnd"]),
        area_m2=float(row["area_m2"]),
        price_per_m2=float(row["price_per_m2"]),
        published_at=row["published_at"].isoformat(),
        match_tier=str(row["match_tier"]),
        area_ratio=float(row["area_m2"] / subject_area_m2),
        recency_days=float(row["recency_days"]),
        distance_m=None,
        distance_status="not_available_missing_coordinates",
    )


def _support_level(count: int) -> str:
    if count >= 5:
        return "high"
    if count >= 3:
        return "medium"
    return "low"
