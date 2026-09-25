"""Tests for the command-line interface."""

import csv
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from myanmardata.cli import app
from myanmardata.collectors import superrich_th
from tests.test_chat_readers import make_viber_db

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = (FIXTURES / "superrich_th_exchange_rate.html").read_bytes()
POST = (FIXTURES / "baht_kyat_post.txt").read_text(encoding="utf-8")
runner = CliRunner()


class _Clock(datetime):
    """Advances one minute per call, so every run gets a distinct collection time."""

    calls = 0

    @classmethod
    def now(cls, tz=None):
        cls.calls += 1
        return datetime(2026, 9, 25, 3, cls.calls, tzinfo=UTC)


def rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_sources_lists_collectors():
    result = runner.invoke(app, ["sources"])
    assert result.exit_code == 0
    assert "superrich_th" in result.output


def test_source_without_update_times_keeps_every_run(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: PAGE)
    monkeypatch.setattr(superrich_th, "datetime", _Clock)

    for _ in range(2):
        result = runner.invoke(app, ["collect", "superrich_th", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
    assert len(list(tmp_path.glob("superrich_th/snapshots/*/*.csv"))) == 2
    assert len(list(tmp_path.glob("superrich_th/raw/*/*.json.gz"))) == 2


def test_failed_source_exits_non_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: b"<html></html>")
    result = runner.invoke(app, ["collect", "superrich_th", "--out", str(tmp_path)])
    assert result.exit_code == 1
    assert not list(tmp_path.rglob("*.csv"))


def test_unknown_collector_is_rejected(tmp_path):
    result = runner.invoke(app, ["collect", "nope", "--out", str(tmp_path)])
    assert result.exit_code != 0


def test_import_from_viber_db_only_writes_new_observations(tmp_path, monkeypatch):
    monkeypatch.setattr("myanmardata.cli.datetime", _Clock)
    sep25 = int(datetime(2026, 9, 25, 3, 41, tzinfo=UTC).timestamp() * 1000)
    db = make_viber_db(tmp_path / "viber.db", [(1, sep25, POST), (1, sep25 + 60_000, "Facebook page မရှိပါ")])
    out = tmp_path / "data"
    args = ["import", "baht_kyat", "--viber-db", str(db), "--out", str(out)]

    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "2 posts, 1 with rates, 2 quotes" in first.output
    [snapshot] = out.glob("baht_kyat_viber/snapshots/*/*.csv")
    assert [(r["min_amount"], r["buy"], r["sell"]) for r in rows(snapshot)] == [
        ("10000", "130.38", "133.51"),
        ("100000", "130.72", "133.16"),
    ]
    [raw] = out.glob("baht_kyat_viber/raw/*/*.json.gz")
    assert json.loads(gzip.decompress(raw.read_bytes()))[0]["id"] == "viber:100"

    # A later export contains the old post plus a new one: only the new one is written.
    newer = POST.replace("133.51", "134.00").replace("(749)", "(746)")
    db2 = make_viber_db(tmp_path / "viber2.db", [(1, sep25, POST), (1, sep25 + 86_400_000, newer)])
    second = runner.invoke(app, ["import", "baht_kyat", "--viber-db", str(db2), "--out", str(out)])
    assert second.exit_code == 0, second.output
    assert "2 new quotes" in second.output

    third = runner.invoke(app, ["import", "baht_kyat", "--viber-db", str(db2), "--out", str(out)])
    assert "nothing new" in third.output
    assert len(list(out.glob("baht_kyat_viber/snapshots/*/*.csv"))) == 2


def test_import_from_text_dry_run(tmp_path):
    pasted = tmp_path / "posts.txt"
    pasted.write_text(POST, encoding="utf-8")
    result = runner.invoke(
        app, ["import", "baht_kyat", "--text", str(pasted), "--last-year", "2026", "--out", str(tmp_path), "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "1 posts, 1 with rates, 2 quotes" in result.output
    assert "2026-09-25T00:00:00Z" in result.output
    assert not list(tmp_path.rglob("*.csv"))


def test_import_needs_exactly_one_input(tmp_path):
    result = runner.invoke(app, ["import", "baht_kyat", "--out", str(tmp_path)])
    assert result.exit_code != 0


def test_viber_commands(tmp_path):
    db = make_viber_db(tmp_path / "viber.db", [(1, 1_790_000_000_000, POST)])
    chats = runner.invoke(app, ["viber", "chats", str(db)])
    assert chats.exit_code == 0 and "Baht-Kyat" in chats.output
    tables = runner.invoke(app, ["viber", "tables", str(db)])
    assert tables.exit_code == 0 and "EventID" in tables.output
