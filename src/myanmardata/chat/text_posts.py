"""Read channel posts pasted into a plain-text file.

Posts are separated by a timestamp line, which is the most reliable form::

    @ 2026-09-25 10:11
    Update - 25 Sep
    ...

Without timestamp lines, each ``Update - 25 Sep`` header starts a post, dated from the
header. Headers carry no year, so the year of the *last* post is given and earlier years are
inferred by walking backwards (a month later than the following post means the year before).
Date-only posts are recorded at 00:00 UTC of that date.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from myanmardata.chat import Post

_STAMP = re.compile(r"^\s*@\s*(\d{4}-\d{2}-\d{2})[ T](\d{1,2}:\d{2})\s*$")
_HEADER = re.compile(r"^\s*Update\s*[-–—:]?\s*(\d{1,2})\s+([A-Za-z]{3,9})\b", re.I)
_MONTHS = {
    m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)
}


def parse_offset(text: str) -> timezone:
    """``+06:30`` → a fixed UTC offset (Myanmar); avoids needing tz data on Windows."""
    match = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", text.strip())
    if not match:
        raise ValueError(f"UTC offset must look like +06:30, got {text!r}")
    sign = 1 if match.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3))))


def _month(name: str) -> int:
    try:
        return _MONTHS[name[:3].lower()]
    except KeyError:
        raise ValueError(f"unknown month {name!r}") from None


def read(text: str, last_year: int | None = None, offset: timezone = UTC) -> list[Post]:
    lines = text.splitlines()
    if any(_STAMP.match(line) for line in lines):
        return _read_stamped(lines, offset)
    if last_year is None:
        raise ValueError("posts without '@ YYYY-MM-DD HH:MM' lines need the year of the last post")
    return _read_headers(lines, last_year)


def _read_stamped(lines: list[str], offset: timezone) -> list[Post]:
    found: list[Post] = []
    stamp: datetime | None = None
    body: list[str] = []

    def flush() -> None:
        if stamp is not None and "".join(body).strip():
            found.append(Post(text="\n".join(body).strip(), posted_at=stamp.astimezone(UTC)))

    for line in lines:
        if match := _STAMP.match(line):
            flush()
            stamp = datetime.fromisoformat(f"{match.group(1)}T{match.group(2).zfill(5)}").replace(tzinfo=offset)
            body = []
        else:
            body.append(line)
    flush()
    return found


def _read_headers(lines: list[str], last_year: int) -> list[Post]:
    blocks: list[tuple[int, int, list[str]]] = []
    for line in lines:
        if match := _HEADER.match(line):
            blocks.append((int(match.group(1)), _month(match.group(2)), [line]))
        elif blocks:
            blocks[-1][2].append(line)

    found: list[Post] = []
    year, next_month = last_year, 13
    for day, month, body in reversed(blocks):
        if month > next_month:
            year -= 1
        next_month = month
        posted_at = datetime(year, month, day, tzinfo=UTC)
        found.append(Post(text="\n".join(body).strip(), posted_at=posted_at, date_only=True))
    found.reverse()
    return found
