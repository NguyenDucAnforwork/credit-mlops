from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol


class ListingAdapter(Protocol):
    """Source adapter contract for permitted listing ingestion."""

    source_name: str
    parser_version: str
    rate_limit_per_minute: int

    def iter_records(self, checkpoint: str | None = None) -> Iterator[dict]:
        """Yield raw listing records from a checkpoint."""


@dataclass(frozen=True)
class CrawlBatch:
    source_name: str
    parser_version: str
    checkpoint: str | None
    records: list[dict]


class FixtureListingAdapter:
    """Deterministic adapter used by tests and smoke runs."""

    source_name = "fixture"
    parser_version = "fixture-v1"
    rate_limit_per_minute = 60

    def __init__(self, records: Iterable[dict]):
        self._records = list(records)

    def iter_records(self, checkpoint: str | None = None) -> Iterator[dict]:
        start = int(checkpoint or 0)
        for record in self._records[start:]:
            yield dict(record)

    def crawl(self, checkpoint: str | None = None) -> CrawlBatch:
        records = list(self.iter_records(checkpoint=checkpoint))
        next_checkpoint = str(len(self._records))
        return CrawlBatch(
            source_name=self.source_name,
            parser_version=self.parser_version,
            checkpoint=next_checkpoint,
            records=records,
        )
