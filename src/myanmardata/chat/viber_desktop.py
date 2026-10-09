"""Read channel posts from Viber Desktop's local database (``viber.db``).

Viber Desktop keeps every message it has loaded in a SQLite file:

* Windows: ``%APPDATA%\\ViberPC\\<phone number>\\viber.db``
* macOS:   ``~/Library/Application Support/ViberPC/<phone number>/viber.db``
* Linux:   ``~/.ViberPC/<phone number>/viber.db``

Only posts the app has downloaded are there, so scroll a channel back to the oldest post you
want before reading it. The database is copied (with its ``-wal`` journal, which holds the most
recent posts while Viber runs) to a temporary folder and read there, so the original is never
touched and Viber can stay open. Without a path, :func:`find_databases` looks in the usual places.

The schema is undocumented. This reader expects ``ChatInfo`` (chat names), ``Events`` (time and
chat of each message) and ``Messages`` (text), joined on ``ChatID`` and ``EventID``. Run
``myanmardata viber tables`` to see what your version actually has.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
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


def viber_roots() -> list[Path]:
    """Folders where Viber Desktop keeps one sub-folder per account."""
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "ViberPC"] if appdata else []
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "ViberPC"]
    return [home / ".ViberPC"]


def find_databases(roots: list[Path] | None = None) -> list[Path]:
    """Every ``viber.db`` under the Viber Desktop folders (one per signed-in account)."""
    return sorted(db for root in roots or viber_roots() for db in root.glob("*/viber.db"))


def locate(path: Path | str | None) -> Path:
    """``path`` if given, otherwise the only ``viber.db`` on this computer."""
    if path is not None:
        return Path(path)
    found = find_databases()
    if len(found) == 1:
        return found[0]
    if not found:
        searched = ", ".join(str(r) for r in viber_roots()) or "(no Viber folder for this system)"
        raise FileNotFoundError(f"no viber.db found in {searched}; pass its path with --viber-db")
    listing = "\n  ".join(str(f) for f in found)
    raise FileNotFoundError(f"several viber.db files found; pass one with --viber-db:\n  {listing}")


@contextmanager
def _open(path: Path | str) -> Iterator[sqlite3.Connection]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"no such file: {source}")
    with tempfile.TemporaryDirectory(prefix="myanmardata-viber-") as tmp:
        copy = Path(tmp) / "viber.db"
        shutil.copyfile(source, copy)
        for suffix in ("-wal", "-shm"):
            journal = source.with_name(source.name + suffix)
            if journal.is_file():
                shutil.copyfile(journal, copy.with_name(copy.name + suffix))
        with closing(sqlite3.connect(copy)) as db:
            yield db


def tables(path: Path | str) -> dict[str, list[str]]:
    """Every table and its columns, for inspecting an unfamiliar Viber version."""
    with _open(path) as db:
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
    with _open(path) as db:
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
    with _open(path) as db:
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
