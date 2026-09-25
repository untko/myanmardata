"""Tests for the SuperRich 1965 collector (offline, against a recorded response)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from myanmardata.collectors import superrich_1965
from myanmardata.collectors.superrich_1965 import ParseError, parse

PAYLOAD = (Path(__file__).parent / "fixtures" / "superrich_1965_head_office.json").read_bytes()
COLLECTED = datetime(2026, 9, 25, 18, 14, 47, tzinfo=UTC)
URL = "https://www.superrich.co.th/controllers/currency.php?method=3&value=33"


def test_parse_keeps_published_digits_and_update_times():
    quotes = parse(PAYLOAD, COLLECTED, URL)
    assert len(quotes) == 4
    usd = quotes[0]
    assert (usd.base_currency, usd.quote_currency, usd.denomination) == ("USD", "THB", "100-50")
    assert (usd.buy, usd.sell) == ("33.20000", "33.33000")
    assert usd.source_record_id == "7563709"
    assert usd.venue == "SuperRich 1965 Head Office"
    assert usd.method == "api"
    assert usd.observed_at == "2026-09-25T10:44:18Z"
    assert usd.collected_at == "2026-09-25T18:14:47Z"
    assert quotes[3].observed_at == "2026-09-25T01:46:42Z"


@pytest.mark.parametrize(
    "payload",
    [
        b"<html>maintenance</html>",
        b"[]",
        b'{"error": 1}',
        b'[{"currencyCode":"EUR","denom":"50","buy":1,"sell":2,"location":"HO","lastUpdate":"2026-09-25T01:46:42.000+0000"}]',
        b'[{"currencyCode":"USD","denom":"50","buy":1,"sell":2,"location":"HO","lastUpdate":"yesterday"}]',
    ],
)
def test_unexpected_responses_are_errors(payload):
    with pytest.raises(ParseError):
        parse(payload, COLLECTED, URL)


def test_collect_requests_head_office(monkeypatch):
    seen = {}

    def fake_fetch(url, headers=None):
        seen["url"] = url
        return PAYLOAD

    monkeypatch.setattr(superrich_1965, "fetch", fake_fetch)
    collection = superrich_1965.collect()
    assert seen["url"].endswith("method=3&value=33")
    assert collection.raw == PAYLOAD
    assert len(collection.records) == 4
