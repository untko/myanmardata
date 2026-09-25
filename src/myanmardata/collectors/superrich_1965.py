"""SuperRich 1965 ("orange") cash exchange rates, quoted in THB.

The rate page loads JSON from ``controllers/currency.php?method=3&value=<locationId>``::

    [{"uid": 7563709, "currencyCode": "USD", "denom": "100-50", "buy": 33.20000,
      "sell": 33.33000, "location": "Head Office", "locationCode": "MC125610005",
      "lastUpdate": "2026-09-25T10:44:18.000+0000", ...}, ...]

Each rate carries its own ``lastUpdate`` (UTC), used as ``observed_at``. Numbers are kept
exactly as written in the JSON, so ``33.20000`` stays ``33.20000``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from myanmardata.collectors import Collection, Collector
from myanmardata.http import fetch
from myanmardata.records import FxQuote, RecordError, utc_iso

SOURCE = "superrich_1965"
HEAD_OFFICE = 33
PAGE_URL = "https://www.superrich.co.th/currency_rate.php"
API_URL = "https://www.superrich.co.th/controllers/currency.php?method=3&value={location}"


class ParseError(ValueError):
    """The response no longer has the expected structure."""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _parse_update(value: str) -> str:
    try:
        return utc_iso(datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z"))
    except ValueError as exc:
        raise ParseError(f"unexpected lastUpdate format {value!r}") from exc


def parse(payload: bytes, collected_at: datetime, url: str) -> list[FxQuote]:
    try:
        # parse_float=str keeps the published digits instead of rounding through float.
        rows: Any = json.loads(payload, parse_float=str, parse_int=str)
    except json.JSONDecodeError as exc:
        raise ParseError(f"response is not JSON: {exc}") from exc
    if not isinstance(rows, list) or not rows:
        raise ParseError("expected a non-empty list of rates")

    collected = utc_iso(collected_at)
    quotes = []
    for row in rows:
        try:
            quotes.append(
                FxQuote(
                    source=SOURCE,
                    source_record_id=_text(row.get("uid")),
                    venue=f"SuperRich 1965 {_text(row.get('location')) or _text(row.get('locationCode'))}",
                    base_currency=_text(row.get("currencyCode")).upper(),
                    quote_currency="THB",
                    unit_amount="1",
                    denomination=" ".join(_text(row.get("denom")).split()),
                    channel="cash",
                    buy=_text(row.get("buy")),
                    sell=_text(row.get("sell")),
                    method="api",
                    observed_at=_parse_update(_text(row.get("lastUpdate"))),
                    collected_at=collected,
                    source_url=url,
                )
            )
        except (RecordError, AttributeError) as exc:
            raise ParseError(f"{row!r}: {exc}") from exc
    if not any(q.base_currency == "USD" for q in quotes):
        raise ParseError("no USD quotes found; the API has probably changed")
    return quotes


def collect(location: int = HEAD_OFFICE) -> Collection:
    collected_at = datetime.now(UTC).replace(microsecond=0)
    url = API_URL.format(location=location)
    payload = fetch(url, headers={"Referer": PAGE_URL, "X-Requested-With": "XMLHttpRequest"})
    return Collection(
        source=SOURCE,
        records=list(parse(payload, collected_at, url)),
        collected_at=collected_at,
        raw=payload,
        raw_ext="json",
    )


COLLECTOR = Collector(
    name=SOURCE,
    domain="fx",
    description="SuperRich 1965 (orange) cash buy/sell rates in THB, head office, per-rate update times",
    collect=collect,
)
