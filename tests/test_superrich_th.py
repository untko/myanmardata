"""Tests for the SuperRich Thailand collector (offline, against a recorded page structure)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from myanmardata.collectors import superrich_th
from myanmardata.collectors.superrich_th import ParseError, extract_exchange_list, parse

PAGE = (Path(__file__).parent / "fixtures" / "superrich_th_exchange_rate.html").read_text(encoding="utf-8")
COLLECTED = datetime(2026, 9, 25, 18, 12, 27, tzinfo=UTC)


def test_extracts_exchange_list_split_across_flight_chunks():
    exchange = extract_exchange_list(PAGE)
    assert list(exchange)[:2] == ["USD", "GBP"]
    assert exchange["MMK"][0]["buyText"] == "0.00500"


def test_parse_keeps_published_values_and_denominations():
    quotes = parse(extract_exchange_list(PAGE), COLLECTED)
    by_key = {(q.base_currency, q.denomination): q for q in quotes}

    usd100 = by_key["USD", "100"]
    assert (usd100.buy, usd100.sell, usd100.quote_currency) == ("33.27", "33.33", "THB")
    assert usd100.venue == "SuperRich Thailand H01"
    assert usd100.source_record_id == "H01:0010"
    assert usd100.observed_at == usd100.collected_at == "2026-09-25T18:12:27Z"

    assert by_key["USD", "20 - 10"].buy == "33.21"
    assert ("GBP", "20- 5") in by_key  # spacing preserved as published
    mmk = by_key["MMK", "10000 - 500"]
    assert (mmk.buy, mmk.sell) == ("0.00500", "0.00900")
    assert ("SCOT", "100 - 5") in by_key
    assert len(quotes) == 8


def test_missing_exchange_list_is_an_error():
    with pytest.raises(ParseError):
        extract_exchange_list('<html><script>self.__next_f.push([1,"nothing here"])</script></html>')


def test_layout_change_without_usd_is_an_error():
    with pytest.raises(ParseError):
        parse({"EUR": [{"denomRem": "50", "buyText": "37.8", "sellText": "38", "branchCode": "H01"}]}, COLLECTED)


def test_bad_rate_is_an_error():
    with pytest.raises(ParseError):
        parse({"USD": [{"denomRem": "100", "buyText": "n/a", "sellText": "33", "branchCode": "H01"}]}, COLLECTED)


def test_collect_uses_fetched_page(monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: PAGE.encode())
    collection = superrich_th.collect()
    assert collection.source == "superrich_th"
    assert len(collection.records) == 8
    assert b'"MMK"' in collection.raw
