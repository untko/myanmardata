"""Append-only snapshot storage.

Layout under a data root::

    <root>/<source>/snapshots/YYYY/YYYY-MM-DDTHH-MM-SSZ.csv   canonical parsed rows
    <root>/<source>/raw/YYYY/YYYY-MM-DDTHH-MM-SSZ.<ext>.gz    response as received

Imports of overlapping history (``only_new=True``) keep only observations not already stored,
identified by the record's series key plus ``observed_at``.

Snapshots are never rewritten. A batch whose rows match the latest snapshot (ignoring
``collected_at``) is skipped, so a source that publishes update times produces no files
and no commits until it changes. Sources without update times use the collection time
as ``observed_at``, so every run is kept as evidence that the rate was still on offer.
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

    def _read(self, path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def observation_keys(self, source: str, key: tuple[str, ...]) -> set[tuple[str, ...]]:
        """Every stored (series key + ``observed_at``) for ``source``."""
        fields = (*key, "observed_at")
        return {tuple(row.get(f, "") for f in fields) for path in self.snapshots(source) for row in self._read(path)}

    def latest_rows(self, source: str) -> list[dict[str, str]] | None:
        existing = self.snapshots(source)
        return self._read(existing[-1]) if existing else None

    def write(
        self,
        source: str,
        records: Sequence[Record],
        collected_at: datetime,
        raw: bytes | None = None,
        raw_ext: str = "json",
        only_new: bool = False,
    ) -> WriteResult:
        if not records:
            raise RecordError(f"{source}: refusing to write an empty snapshot")
        kinds = {type(r) for r in records}
        if len(kinds) != 1:
            raise RecordError(f"{source}: a snapshot must hold one record type, got {kinds}")
        if any(r.source != source for r in records):
            raise RecordError(f"{source}: every record must carry source={source!r}")

        record_type = type(records[0])
        columns = record_type.columns()
        rows = [r.as_row() for r in records]
        if only_new:
            fields = (*record_type.series_key, "observed_at")
            known = self.observation_keys(source, record_type.series_key)
            rows = [r for r in rows if tuple(r[f] for f in fields) not in known]
            if not rows:
                return WriteResult(snapshot=None, raw=None, rows=0, skipped_unchanged=True)
        elif self._unchanged(source, rows):
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
