"""Append-only snapshot storage.

Layout under a data root::

    <root>/<source>/snapshots/YYYY/YYYY-MM-DDTHH-MM-SSZ.csv   canonical parsed rows
    <root>/<source>/raw/YYYY/YYYY-MM-DDTHH-MM-SSZ.<ext>.gz    response as received

Snapshots are never rewritten. A batch whose rows match the latest snapshot (ignoring
``collected_at``) is skipped, so unchanged sources produce no files and no commits.
"""

from __future__ import annotations

import csv
import gzip
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from myanmardata.records import Record, RecordError

_IGNORED_FOR_CHANGE = frozenset({"collected_at"})


@dataclass(frozen=True, slots=True)
class WriteResult:
    snapshot: Path | None
    raw: Path | None
    rows: int
    skipped_unchanged: bool


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


class SnapshotStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def snapshot_dir(self, source: str) -> Path:
        return self.root / source / "snapshots"

    def snapshots(self, source: str) -> list[Path]:
        return sorted(self.snapshot_dir(source).glob("*/*.csv"))

    def latest_rows(self, source: str) -> list[dict[str, str]] | None:
        existing = self.snapshots(source)
        if not existing:
            return None
        with existing[-1].open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def write(
        self,
        source: str,
        records: Sequence[Record],
        collected_at: datetime,
        raw: bytes | None = None,
        raw_ext: str = "json",
    ) -> WriteResult:
        if not records:
            raise RecordError(f"{source}: refusing to write an empty snapshot")
        kinds = {type(r) for r in records}
        if len(kinds) != 1:
            raise RecordError(f"{source}: a snapshot must hold one record type, got {kinds}")
        if any(r.source != source for r in records):
            raise RecordError(f"{source}: every record must carry source={source!r}")

        columns = type(records[0]).columns()
        rows = [r.as_row() for r in records]
        if self._unchanged(source, rows):
            return WriteResult(snapshot=None, raw=None, rows=len(rows), skipped_unchanged=True)

        stamp = _stamp(collected_at)
        year = stamp[:4]
        snapshot = self.snapshot_dir(source) / year / f"{stamp}.csv"
        if snapshot.exists():
            raise FileExistsError(f"snapshot already exists: {snapshot}")
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with snapshot.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

        raw_path = None
        if raw is not None:
            raw_path = self.root / source / "raw" / year / f"{stamp}.{raw_ext}.gz"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            # mtime=0 keeps the gzip bytes reproducible for identical payloads.
            raw_path.write_bytes(gzip.compress(raw, mtime=0))

        return WriteResult(snapshot=snapshot, raw=raw_path, rows=len(rows), skipped_unchanged=False)

    def _unchanged(self, source: str, rows: list[dict[str, str]]) -> bool:
        latest = self.latest_rows(source)
        if latest is None:
            return False

        def comparable(batch: list[dict[str, str]]) -> list[tuple[tuple[str, str], ...]]:
            return sorted(tuple(sorted((k, v) for k, v in r.items() if k not in _IGNORED_FOR_CHANGE)) for r in batch)

        return comparable(latest) == comparable(rows)
