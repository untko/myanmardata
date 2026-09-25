"""Tests for the Baht-Kyat channel parser."""

from datetime import UTC, datetime
from pathlib import Path

from myanmardata.chat import ParseReport, Post
from myanmardata.chat.baht_kyat import parse_post, parse_posts

POST = (Path(__file__).parent / "fixtures" / "baht_kyat_post.txt").read_text(encoding="utf-8")
POSTED = datetime(2026, 9, 25, 3, 41, tzinfo=UTC)  # 10:11 Yangon
COLLECTED = "2026-09-26T09:00:00Z"


def test_parses_both_tiers_as_thai_bank_account_quotes():
    report = ParseReport()
    quotes = parse_post(Post(POST, POSTED, "viber:42"), COLLECTED, report)

    assert report.warnings == []
    assert [(q.min_amount, q.buy, q.sell) for q in quotes] == [
        ("10000", "130.38", "133.51"),
        ("100000", "130.72", "133.16"),
    ]
    q = quotes[0]
    assert (q.base_currency, q.quote_currency, q.unit_amount) == ("THB", "MMK", "1")
    assert (q.channel, q.method, q.venue) == ("thai_bank_account", "chat", "Baht-Kyat")
    assert (q.observed_at, q.collected_at, q.source_record_id) == ("2026-09-25T03:41:00Z", COLLECTED, "viber:42")


def test_bracket_cross_check_flags_typos():
    report = ParseReport()
    text = "B 10,000 အထက်ဈေး\nMMK > THB - 133.51 (794)\nTHB > MMK - 130.38 (767)"
    quotes = parse_post(Post(text, POSTED), COLLECTED, report)
    assert len(quotes) == 1  # the quoted rate is kept
    assert "bracket 794" in report.warnings[0]


def test_other_currencies_and_missing_channel_note():
    report = ParseReport()
    text = "USD > MMK - 4,350\nMMK > USD - 4,420\nSGD > MMK - 3350"
    quotes = parse_post(Post(text, POSTED), COLLECTED, report)
    by_ccy = {q.base_currency: q for q in quotes}
    assert (by_ccy["USD"].buy, by_ccy["USD"].sell) == ("4350", "4420")
    assert (by_ccy["SGD"].buy, by_ccy["SGD"].sell) == ("3350", "")
    assert all(q.channel == "unspecified" and q.min_amount == "" for q in quotes)


def test_warns_when_buy_is_above_sell():
    report = ParseReport()
    parse_post(Post("MMK > THB - 120\nTHB > MMK - 130", POSTED), COLLECTED, report)
    assert "above sell" in report.warnings[0]


def test_announcements_are_skipped_not_errors():
    posts = [Post("ကျတော့ မှာ Facebook page မရှိပါ။", POSTED), Post(POST, POSTED)]
    quotes, report = parse_posts(posts, COLLECTED)
    assert (report.posts, report.rate_posts, len(report.skipped), len(quotes)) == (2, 1, 1, 2)
