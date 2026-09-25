"""Record schemas shared by every collector.

Every row carries the same provenance envelope (source, venue, method, observation and
collection times, source URL) followed by domain-specific fields. Values are kept as
published: prices are decimal strings, and nothing is converted or inferred.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from typing import ClassVar, Literal

# api/html: fetched from a website; chat: parsed from a channel post; ocr: read from an image;
# manual: typed in by a person.
Method = Literal["api", "html", "chat", "ocr", "manual"]
METHODS: frozenset[str] = frozenset({"api", "html", "chat", "ocr", "manual"})

_DECIMAL = re.compile(r"^(?:[0-9]+(?:\.[0-9]+)?)?$")
_CURRENCY = re.compile(r"^[A-Z]{3,5}$")


class RecordError(ValueError):
    """A record does not satisfy its schema."""


def utc_iso(moment: datetime) -> str:
    """Format an aware datetime as ``YYYY-MM-DDTHH:MM:SSZ``."""
    if moment.tzinfo is None:
        raise RecordError("timestamps must be timezone-aware")
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_timestamp(name: str, value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecordError(f"{name} is not an ISO 8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RecordError(f"{name} must include a UTC offset: {value!r}")


def _check_decimal(name: str, value: str) -> None:
    if not _DECIMAL.fullmatch(value):
        raise RecordError(f"{name} must be a non-negative decimal string or empty: {value!r}")


@dataclass(frozen=True, slots=True)
class FxQuote:
    """One published buy/sell quote for exchanging ``base_currency`` into ``quote_currency``.

    ``buy`` is what the venue pays for ``unit_amount`` of ``base_currency`` and ``sell`` is what it
    charges, both in ``quote_currency``. ``denomination`` is the note size for cash quotes and
    ``min_amount`` the smallest deal (in ``base_currency``) a tiered quote applies to; either may be
    empty. Rates for different denominations, tiers or channels are different series and must never
    be averaged together.
    """

    domain: ClassVar[str] = "fx"
    series_key: ClassVar[tuple[str, ...]] = (
        "source",
        "venue",
        "base_currency",
        "quote_currency",
        "unit_amount",
        "denomination",
        "min_amount",
        "channel",
    )

    source: str
    source_record_id: str
    venue: str
    base_currency: str
    quote_currency: str
    unit_amount: str
    denomination: str
    min_amount: str
    channel: str
    buy: str
    sell: str
    method: str
    observed_at: str
    collected_at: str
    source_url: str

    def __post_init__(self) -> None:
        for name in ("source", "venue", "unit_amount", "channel", "method", "source_url"):
            if not getattr(self, name):
                raise RecordError(f"{name} must not be empty")
        for name in ("base_currency", "quote_currency"):
            if not _CURRENCY.fullmatch(getattr(self, name)):
                raise RecordError(f"{name} must be an upper-case currency code: {getattr(self, name)!r}")
        if self.method not in METHODS:
            raise RecordError(f"method must be one of {sorted(METHODS)}: {self.method!r}")
        for name in ("unit_amount", "min_amount", "buy", "sell"):
            _check_decimal(name, getattr(self, name))
        if not self.buy and not self.sell:
            raise RecordError("a quote needs a buy or a sell price")
        _check_timestamp("observed_at", self.observed_at)
        _check_timestamp("collected_at", self.collected_at)

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    def as_row(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.columns()}


Record = FxQuote
