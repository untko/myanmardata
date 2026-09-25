"""Rates published as chat-channel posts (Viber, Telegram, ...).

Readers turn an export into :class:`Post` objects; a per-channel parser turns each post into
records. Posts that are not rate updates (announcements, ads) are skipped, not errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Post:
    text: str
    posted_at: datetime
    record_id: str = ""
    # True when posted_at only carries a calendar date (e.g. taken from the post's own header).
    date_only: bool = False


@dataclass
class ParseReport:
    posts: int = 0
    rate_posts: int = 0
    skipped: list[Post] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
