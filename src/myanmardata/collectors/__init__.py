"""Source collectors.

Each collector fetches one source and returns validated records plus the raw payload it
parsed, so a snapshot can always be re-parsed later. Collectors never write files.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from myanmardata.records import Record


@dataclass(frozen=True, slots=True)
class Collection:
    source: str
    records: list[Record]
    collected_at: datetime
    raw: bytes
    raw_ext: str


@dataclass(frozen=True, slots=True)
class Collector:
    name: str
    domain: str
    description: str
    collect: Callable[[], Collection]


def registry() -> dict[str, Collector]:
    from myanmardata.collectors import superrich_1965, superrich_th

    collectors = [superrich_th.COLLECTOR, superrich_1965.COLLECTOR]
    return {c.name: c for c in collectors}
