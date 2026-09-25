"""Tests for the command-line interface."""

from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from myanmardata.cli import app
from myanmardata.collectors import superrich_1965, superrich_th

FIXTURES = Path(__file__).parent / "fixtures"
PAGE = (FIXTURES / "superrich_th_exchange_rate.html").read_bytes()
PAYLOAD = (FIXTURES / "superrich_1965_head_office.json").read_bytes()
runner = CliRunner()


class _Clock(datetime):
    """Advances one minute per call, so every run gets a distinct collection time."""

    calls = 0

    @classmethod
    def now(cls, tz=None):
        cls.calls += 1
        return datetime(2026, 9, 25, 3, cls.calls, tzinfo=UTC)


def test_sources_lists_collectors():
    result = runner.invoke(app, ["sources"])
    assert result.exit_code == 0
    assert "superrich_th" in result.output
    assert "superrich_1965" in result.output


def test_source_without_update_times_keeps_every_run(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: PAGE)
    monkeypatch.setattr(superrich_th, "datetime", _Clock)

    for _ in range(2):
        result = runner.invoke(app, ["collect", "superrich_th", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
    assert len(list(tmp_path.glob("superrich_th/snapshots/*/*.csv"))) == 2
    assert len(list(tmp_path.glob("superrich_th/raw/*/*.json.gz"))) == 2


def test_source_with_update_times_skips_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_1965, "fetch", lambda url, headers=None: PAYLOAD)
    monkeypatch.setattr(superrich_1965, "datetime", _Clock)

    first = runner.invoke(app, ["collect", "superrich_1965", "--out", str(tmp_path)])
    assert first.exit_code == 0, first.output
    second = runner.invoke(app, ["collect", "superrich_1965", "--out", str(tmp_path)])
    assert second.exit_code == 0, second.output
    assert "unchanged" in second.output
    assert len(list(tmp_path.glob("superrich_1965/snapshots/*/*.csv"))) == 1


def test_one_failing_source_does_not_block_others(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: b"<html></html>")
    monkeypatch.setattr(superrich_1965, "fetch", lambda url, headers=None: PAYLOAD)

    result = runner.invoke(app, ["collect", "superrich_th", "superrich_1965", "--out", str(tmp_path)])
    assert result.exit_code == 1
    assert len(list(tmp_path.glob("superrich_1965/snapshots/*/*.csv"))) == 1
    assert not list(tmp_path.glob("superrich_th/**/*.csv"))


def test_failed_source_exits_non_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: b"<html></html>")
    result = runner.invoke(app, ["collect", "superrich_th", "--out", str(tmp_path)])
    assert result.exit_code == 1
    assert not list(tmp_path.rglob("*.csv"))


def test_unknown_collector_is_rejected(tmp_path):
    result = runner.invoke(app, ["collect", "nope", "--out", str(tmp_path)])
    assert result.exit_code != 0
