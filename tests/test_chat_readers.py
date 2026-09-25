"""Tests for reading posts from viber.db and from pasted text."""

import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from myanmardata.chat import text_posts, viber_desktop


def make_viber_db(path, messages):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE ChatInfo (ChatID INTEGER PRIMARY KEY, Name TEXT, Flags INTEGER);
        CREATE TABLE Events (EventID INTEGER PRIMARY KEY, ChatID INTEGER, TimeStamp INTEGER, Direction INTEGER);
        CREATE TABLE Messages (EventID INTEGER PRIMARY KEY, Body TEXT, Type INTEGER);
        INSERT INTO ChatInfo VALUES (1, 'Baht-Kyat', 0), (2, 'Family', 0);
        """
    )
    for event_id, (chat_id, stamp_ms, body) in enumerate(messages, start=100):
        db.execute("INSERT INTO Events VALUES (?, ?, ?, 0)", (event_id, chat_id, stamp_ms))
        db.execute("INSERT INTO Messages VALUES (?, ?, 1)", (event_id, body))
    db.commit()
    db.close()
    return path


def test_viber_reads_one_chat_oldest_first(tmp_path):
    sep25 = int(datetime(2026, 9, 25, 3, 41, tzinfo=UTC).timestamp() * 1000)
    db = make_viber_db(
        tmp_path / "viber.db",
        [(1, sep25 + 86_400_000, "newer"), (1, sep25, "older"), (2, sep25, "hi mum"), (1, sep25, None)],
    )
    posts = list(viber_desktop.posts(db, "Baht-Kyat"))
    assert [p.text for p in posts] == ["older", "newer"]
    assert posts[0].posted_at == datetime(2026, 9, 25, 3, 41, tzinfo=UTC)
    assert posts[0].record_id == "viber:101"
    assert viber_desktop.chats(db) == [("Baht-Kyat", 2), ("Family", 1)]
    assert "Messages" in viber_desktop.tables(db)


def test_viber_unknown_chat_and_schema(tmp_path):
    db = make_viber_db(tmp_path / "viber.db", [])
    with pytest.raises(LookupError):
        list(viber_desktop.posts(db, "Nope"))

    other = tmp_path / "other.db"
    sqlite3.connect(other).executescript("CREATE TABLE ChatInfo (ChatID INTEGER, Title TEXT);")
    with pytest.raises(viber_desktop.ViberSchemaError):
        viber_desktop.chats(other)


def test_text_with_timestamp_lines_uses_offset():
    text = "@ 2026-09-25 10:11\nUpdate - 25 Sep\nTHB > MMK - 130\n\n@ 2026-09-26 9:36\nUpdate - 26 Sep\n"
    posts = text_posts.read(text, offset=text_posts.parse_offset("+06:30"))
    assert [p.posted_at for p in posts] == [
        datetime(2026, 9, 25, 3, 41, tzinfo=UTC),
        datetime(2026, 9, 26, 3, 6, tzinfo=UTC),
    ]
    assert posts[0].text == "Update - 25 Sep\nTHB > MMK - 130"
    assert not posts[0].date_only


def test_text_headers_infer_years_backwards():
    text = "noise before\nUpdate - 30 Dec\na\nUpdate - 2 Jan\nb\nUpdate - 25 Sep\nc\n"
    posts = text_posts.read(text, last_year=2026)
    assert [p.posted_at.date().isoformat() for p in posts] == ["2025-12-30", "2026-01-02", "2026-09-25"]
    assert all(p.date_only for p in posts)
    assert posts[1].text == "Update - 2 Jan\nb"


def test_text_headers_need_a_year():
    with pytest.raises(ValueError):
        text_posts.read("Update - 25 Sep\n")


def test_parse_offset():
    assert text_posts.parse_offset("+0630") == timezone(timedelta(hours=6, minutes=30))
    assert text_posts.parse_offset("-05:00") == timezone(-timedelta(hours=5))
    with pytest.raises(ValueError):
        text_posts.parse_offset("Asia/Yangon")
