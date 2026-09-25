"""Parser for the "Baht-Kyat" Viber channel (THB/USD/SGD against MMK).

A typical post::

    Update - 25 Sep

    B 10,000 အထက်ဈေး              <- tier: deals above 10,000 baht
    MMK > THB - 133.51 (749)       <- customer pays 133.51 kyat per baht (749 baht per 100,000 kyat)
    THB > MMK - 130.38 (767)       <- customer receives 130.38 kyat per baht (767 baht per 100,000 kyat)

    B 100,000 အထက်ဈေး
    MMK > THB - 133.16 (751)
    THB > MMK - 130.72 (765)

    🔺🔺🔺 ထိုင်းဘဏ်အကောင့် ဈေးပါ။          <- these are Thai bank account rates
    ငွေသား (အရွက်) နဲ့ နိုင်ငံခြားဘဏ်အကောင့်ဈေးမတူပါဗျ။  <- cash and foreign accounts are priced differently

Rates are kyat per one unit of the foreign currency. ``MMK > X`` is the channel selling X
(``sell``); ``X > MMK`` is the channel buying X (``buy``). The bracketed figure, units of X per
100,000 kyat, is used only as a cross-check.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

from myanmardata.chat import ParseReport, Post
from myanmardata.records import FxQuote, RecordError, utc_iso

SOURCE = "baht_kyat_viber"
VENUE = "Baht-Kyat"
SOURCE_URL = "viber-channel:Baht-Kyat"

_NUMBER = r"[0-9][0-9,]*(?:\.[0-9]+)?"
_TIER = re.compile(rf"^\s*(B|฿|THB|\$|USD|SGD|S\$)\s*({_NUMBER})\s*(?:အထက်|above|\+)", re.I)
_RATE = re.compile(
    rf"^\s*([A-Z]{{3}})\s*(?:>|→|->|to)\s*([A-Z]{{3}})\s*[-–—:=]?\s*({_NUMBER})\s*(?:\(\s*({_NUMBER})\s*\))?",
    re.I,
)
_TIER_CURRENCY = {"B": "THB", "฿": "THB", "THB": "THB", "$": "USD", "USD": "USD", "SGD": "SGD", "S$": "SGD"}
_THAI_BANK = "ထိုင်းဘဏ်"
_LAKH = Decimal(100_000)


def _number(text: str) -> str:
    return text.replace(",", "")


def parse_post(post: Post, collected_at: str, report: ParseReport) -> list[FxQuote]:
    """Return the quotes in one post (empty if it is not a rate update)."""
    channel = "thai_bank_account" if _THAI_BANK in post.text else "unspecified"
    observed_at = utc_iso(post.posted_at)

    # (base currency, tier) -> {"buy": ..., "sell": ...}
    sides: dict[tuple[str, str], dict[str, str]] = {}
    tier_currency, tier_amount = "", ""
    for line in post.text.splitlines():
        if tier := _TIER.match(line):
            tier_currency = _TIER_CURRENCY[tier.group(1).upper()]
            tier_amount = _number(tier.group(2))
            continue
        rate = _RATE.match(line)
        if not rate:
            continue
        source_ccy, target_ccy = rate.group(1).upper(), rate.group(2).upper()
        if (source_ccy == "MMK") == (target_ccy == "MMK"):
            report.warnings.append(f"{observed_at}: not a kyat pair: {line.strip()!r}")
            continue
        foreign = target_ccy if source_ccy == "MMK" else source_ccy
        side = "sell" if source_ccy == "MMK" else "buy"
        value = _number(rate.group(3))
        if check := rate.group(4):
            implied = _LAKH / Decimal(value)
            if abs(implied - Decimal(_number(check))) > 1:
                report.warnings.append(
                    f"{observed_at}: {line.strip()!r}: bracket {check} ≠ 100,000 / {value} ≈ {implied:.0f}"
                )
        min_amount = tier_amount if tier_currency in ("", foreign) else ""
        if tier_currency and tier_currency != foreign:
            report.warnings.append(f"{observed_at}: tier in {tier_currency} applied to {foreign}; tier dropped")
        sides.setdefault((foreign, min_amount), {})[side] = value

    quotes = []
    for (foreign, min_amount), prices in sides.items():
        try:
            quotes.append(
                FxQuote(
                    source=SOURCE,
                    source_record_id=post.record_id,
                    venue=VENUE,
                    base_currency=foreign,
                    quote_currency="MMK",
                    unit_amount="1",
                    denomination="",
                    min_amount=min_amount,
                    channel=channel,
                    buy=prices.get("buy", ""),
                    sell=prices.get("sell", ""),
                    method="chat",
                    observed_at=observed_at,
                    collected_at=collected_at,
                    source_url=SOURCE_URL,
                )
            )
        except RecordError as exc:
            report.warnings.append(f"{observed_at}: {exc}")
            continue
        buy, sell = prices.get("buy"), prices.get("sell")
        if buy and sell and Decimal(buy) > Decimal(sell):
            report.warnings.append(f"{observed_at}: {foreign} buy {buy} is above sell {sell}")
    return quotes


def parse_posts(posts: Iterable[Post], collected_at: str) -> tuple[list[FxQuote], ParseReport]:
    report = ParseReport()
    quotes: list[FxQuote] = []
    for post in posts:
        report.posts += 1
        found = parse_post(post, collected_at, report)
        if found:
            report.rate_posts += 1
            quotes.extend(found)
        else:
            report.skipped.append(post)
    return quotes, report
