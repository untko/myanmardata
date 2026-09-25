"""SuperRich Thailand ("green") cash exchange rates, quoted in THB.

The exchange-rate page is a Next.js app whose server-rendered flight data
(``self.__next_f.push([1, "..."])`` chunks) contains an ``exchangeList`` object::

    {"USD": [{"denomRem": "100", "buyText": "33.27", "sellText": "33.33",
              "branchCode": "H01", "denomCode": "0010", "unit": "USD", ...}, ...], ...}

Rates are live counter rates with no publication timestamp, so ``observed_at`` is the
collection time. The page shows the headquarters branch (Rajdamri 1, ``H01``).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from myanmardata.collectors import Collection, Collector
from myanmardata.http import fetch
from myanmardata.records import FxQuote, RecordError, utc_iso

SOURCE = "superrich_th"
URL = "https://www.superrichthailand.com/exchange-rate"

_FLIGHT_CHUNK = re.compile(r"self\.__next_f\.push\((\[.*?\])\)</script>", re.S)
_EXCHANGE_LIST = '"exchangeList":'


class ParseError(ValueError):
    """The page no longer has the expected structure."""


def extract_exchange_list(page: str) -> dict[str, list[dict[str, Any]]]:
    """Return the ``exchangeList`` object embedded in the page's flight data."""
    payload = []
    for chunk in _FLIGHT_CHUNK.findall(page):
        try:
            item = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if len(item) > 1 and isinstance(item[1], str):
            payload.append(item[1])
    flight = "".join(payload)

    start = flight.find(_EXCHANGE_LIST)
    if start < 0:
        raise ParseError("exchangeList not found in page flight data")
    try:
        value, _ = json.JSONDecoder().raw_decode(flight, start + len(_EXCHANGE_LIST))
    except json.JSONDecodeError as exc:
        raise ParseError(f"exchangeList is not valid JSON: {exc}") from exc
    if not isinstance(value, dict) or not value:
        raise ParseError("exchangeList is empty or not an object")
    return value


def _decimal_text(value: object) -> str:
    """Normalise a published rate to a plain decimal string, keeping its precision."""
    text = str(value).strip().replace(",", "")
    if not text:
        return ""
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ParseError(f"unparseable rate {value!r}") from exc
    if number < 0:
        raise ParseError(f"negative rate {value!r}")
    return text


def parse(exchange_list: dict[str, list[dict[str, Any]]], collected_at: datetime) -> list[FxQuote]:
    stamp = utc_iso(collected_at)
    quotes = []
    for currency, rows in exchange_list.items():
        for row in rows:
            base = str(row.get("unit") or currency).strip().upper()
            branch = str(row.get("branchCode") or "").strip()
            try:
                quotes.append(
                    FxQuote(
                        source=SOURCE,
                        source_record_id=f"{branch}:{row.get('denomCode', '')}".strip(":"),
                        venue=f"SuperRich Thailand {branch}".strip(),
                        base_currency=base,
                        quote_currency="THB",
                        unit_amount="1",
                        denomination=" ".join(str(row.get("denomRem") or "").split()),
                        min_amount="",
                        channel="cash",
                        buy=_decimal_text(row.get("buyText", "")),
                        sell=_decimal_text(row.get("sellText", "")),
                        method="html",
                        observed_at=stamp,
                        collected_at=stamp,
                        source_url=URL,
                    )
                )
            except RecordError as exc:
                raise ParseError(f"{currency} {row!r}: {exc}") from exc
    if not any(q.base_currency == "USD" for q in quotes):
        raise ParseError("no USD quotes found; the page layout has probably changed")
    return quotes


def collect() -> Collection:
    collected_at = datetime.now(UTC).replace(microsecond=0)
    page = fetch(URL).decode("utf-8", errors="replace")
    exchange_list = extract_exchange_list(page)
    raw = json.dumps(exchange_list, ensure_ascii=False, indent=1, sort_keys=True).encode()
    return Collection(
        source=SOURCE,
        records=list(parse(exchange_list, collected_at)),
        collected_at=collected_at,
        raw=raw,
        raw_ext="json",
    )


COLLECTOR = Collector(
    name=SOURCE,
    domain="fx",
    description="SuperRich Thailand (green) cash buy/sell rates in THB, headquarters branch",
    collect=collect,
)
