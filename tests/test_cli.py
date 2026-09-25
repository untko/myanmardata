"""Tests for the command-line interface."""

from pathlib import Path

from typer.testing import CliRunner

from myanmardata.cli import app
from myanmardata.collectors import superrich_th

PAGE = (Path(__file__).parent / "fixtures" / "superrich_th_exchange_rate.html").read_bytes()
runner = CliRunner()


def test_sources_lists_superrich():
    result = runner.invoke(app, ["sources"])
    assert result.exit_code == 0
    assert "superrich_th" in result.output


def test_collect_writes_then_skips_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: PAGE)

    first = runner.invoke(app, ["collect", "superrich_th", "--out", str(tmp_path)])
    assert first.exit_code == 0, first.output
    assert len(list(tmp_path.glob("superrich_th/snapshots/*/*.csv"))) == 1
    assert len(list(tmp_path.glob("superrich_th/raw/*/*.json.gz"))) == 1

    second = runner.invoke(app, ["collect", "superrich_th", "--out", str(tmp_path)])
    assert second.exit_code == 0, second.output
    assert "unchanged" in second.output
    assert len(list(tmp_path.glob("superrich_th/snapshots/*/*.csv"))) == 1


def test_failed_source_exits_non_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(superrich_th, "fetch", lambda url: b"<html></html>")
    result = runner.invoke(app, ["collect", "superrich_th", "--out", str(tmp_path)])
    assert result.exit_code == 1
    assert not list(tmp_path.rglob("*.csv"))


def test_unknown_collector_is_rejected(tmp_path):
    result = runner.invoke(app, ["collect", "nope", "--out", str(tmp_path)])
    assert result.exit_code != 0
