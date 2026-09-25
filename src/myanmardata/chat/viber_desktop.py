"""Read channel posts from Viber Desktop's local database (``viber.db``).

Viber Desktop keeps every message it has loaded in a SQLite file:

* Windows: ``%APPDATA%\\ViberPC\\<phone number>\\viber.db``
* macOS:   ``~/Library/Application Support/ViberPC/<phone number>/viber.db``
* Linux:   ``~/.ViberPC/<phone number>/viber.db``

Only posts the app has downloaded are there, so scroll a channel back to the oldest post you
want before reading it. The file is opened read-only; copy it first if Viber is running.

The schema is undocumented. This reader expects ``ChatInfo`` (chat names), ``Events`` (time and
chat of each message) and ``Messages`` (text), joined on ``ChatID`` and ``EventID``. Run
``myanmardata viber tables`` to see what your version actually has.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from myanmardata.chat import Post

REQUIRED = {
    "ChatInfo": {"ChatID", "Name"},
    "Events": {"EventID", "ChatID", "TimeStamp"},
    "Messages": {"EventID", "Body"},
}


class ViberSchemaError(RuntimeError):
    """The database does not have the tables and columns this reader expects."""


def _connect(path: Path | str) -> sqlite3.Connection:
    uri = Path(path).resolve().as_uri() + "?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def tables(path: Path | str) -> dict[str, list[str]]:
    """Every table and its columns, for inspecting an unfamiliar Viber version."""
    with closing(_connect(path)) as db:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return {name: [c[1] for c in db.execute(f'PRAGMA table_info("{name}")')] for name in names}


def _check_schema(db: sqlite3.Connection) -> None:
    for table, needed in REQUIRED.items():
        have = {c[1] for c in db.execute(f'PRAGMA table_info("{table}")')}
        if missing := needed - have:
            raise ViberSchemaError(
                f"table {table} lacks {sorted(missing)}; run `myanmardata viber tables` and share the output"
            )


def chats(path: Path | str) -> list[tuple[str, int]]:
    """(chat name, number of text messages), most messages first."""
    with closing(_connect(path)) as db:
        _check_schema(db)
        rows = db.execute(
            """
            SELECT c.Name, COUNT(m.EventID)
            FROM ChatInfo c
            JOIN Events e ON e.ChatID = c.ChatID
            JOIN Messages m ON m.EventID = e.EventID
            WHERE m.Body IS NOT NULL AND m.Body != ''
            GROUP BY c.ChatID
            ORDER BY COUNT(m.EventID) DESC
            """
        )
        return [(name or "", count) for name, count in rows]


def _timestamp(value: int | float) -> datetime:
    # Viber stores milliseconds since the epoch; accept seconds too.
    seconds = value / 1000 if value > 1e11 else value
    return datetime.fromtimestamp(seconds, UTC).replace(microsecond=0)


def posts(path: Path | str, chat: str) -> Iterator[Post]:
    """Text posts of the chat named ``chat``, oldest first."""
    with closing(_connect(path)) as db:
        _check_schema(db)
        matches = db.execute("SELECT COUNT(*) FROM ChatInfo WHERE Name = ?", (chat,)).fetchone()[0]
        if not matches:
            raise LookupError(f"no chat named {chat!r}; run `myanmardata viber chats` to list them")
        rows = db.execute(
            """
            SELECT e.EventID, e.TimeStamp, m.Body
            FROM ChatInfo c
            JOIN Events e ON e.ChatID = c.ChatID
            JOIN Messages m ON m.EventID = e.EventID
            WHERE c.Name = ? AND m.Body IS NOT NULL AND m.Body != ''
            ORDER BY e.TimeStamp, e.EventID
            """,
            (chat,),
        )
        for event_id, stamp, body in rows:
            yield Post(text=str(body), posted_at=_timestamp(stamp), record_id=f"viber:{event_id}")
