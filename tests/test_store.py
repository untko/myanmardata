"""Tests for record validation and the snapshot store."""

import csv
import gzip
from datetime import UTC, datetime

import pytest

from myanmardata.records import FxQuote, RecordError, utc_iso
from myanmardata.store import SnapshotStore

COLLECTED = datetime(2026, 9, 25, 3, 0, 5, tzinfo=UTC)


def quote(**overrides: str) -> FxQuote:
    values = {
        "source": "superrich_th",
        "source_record_id": "",
        "venue": "SuperRich Thailand",
        "base_currency": "USD",
        "quote_currency": "THB",
        "unit_amount": "1",
        "denomination": "100",
        "channel": "cash",
        "buy": "32.45",
        "sell": "32.55",
        "method": "html",
        "observed_at": "2026-09-25T02:58:00Z",
        "collected_at": utc_iso(COLLECTED),
        "source_url": "https://www.superrichthailand.com/exchange-rate",
    }
    values.update(overrides)
    return FxQuote(**values)


def test_utc_iso_requires_aware_datetime():
    assert utc_iso(COLLECTED) == "2026-09-25T03:00:05Z"
    with pytest.raises(RecordError):
        utc_iso(datetime(2026, 9, 25))


@pytest.mark.parametrize(
    "overrides",
    [
        {"base_currency": "usd"},
        {"buy": "32,45"},
        {"buy": "", "sell": ""},
        {"method": "guess"},
        {"observed_at": "2026-09-25 02:58"},
        {"venue": ""},
    ],
)
def test_invalid_quotes_are_rejected(overrides):
    with pytest.raises(RecordError):
        quote(**overrides)


def test_write_creates_snapshot_and_raw(tmp_path):
    store = SnapshotStore(tmp_path)
    result = store.write("superrich_th", [quote()], COLLECTED, raw=b'{"ok":1}', raw_ext="html")

    assert result.snapshot == tmp_path / "superrich_th/snapshots/2026/2026-09-25T03-00-05Z.csv"
    assert result.snapshot is not None and result.raw is not None
    assert gzip.decompress(result.raw.read_bytes()) == b'{"ok":1}'
    with result.snapshot.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [quote().as_row()]


def test_unchanged_batch_is_skipped_even_with_new_collection_time(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("superrich_th", [quote()], COLLECTED)

    later = datetime(2026, 9, 26, 3, 0, 0, tzinfo=UTC)
    again = store.write("superrich_th", [quote(collected_at=utc_iso(later))], later)
    assert again.skipped_unchanged and again.snapshot is None

    changed = store.write("superrich_th", [quote(collected_at=utc_iso(later), sell="32.60")], later)
    assert changed.snapshot is not None
    assert len(store.snapshots("superrich_th")) == 2


def test_rejects_empty_or_mislabelled_batches(tmp_path):
    store = SnapshotStore(tmp_path)
    with pytest.raises(RecordError):
        store.write("superrich_th", [], COLLECTED)
    with pytest.raises(RecordError):
        store.write("other", [quote()], COLLECTED)


def test_never_overwrites_a_snapshot(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("superrich_th", [quote()], COLLECTED)
    with pytest.raises(FileExistsError):
        store.write("superrich_th", [quote(sell="1")], COLLECTED)
