"""Console script for myanmardata."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from myanmardata.chat import Post, baht_kyat, text_posts, viber_desktop
from myanmardata.collectors import registry
from myanmardata.records import utc_iso
from myanmardata.store import SnapshotStore

app = typer.Typer(help="Collect Myanmar market data into append-only snapshots.", no_args_is_help=True)
viber = typer.Typer(help="Inspect a Viber Desktop database (viber.db).", no_args_is_help=True)
app.add_typer(viber, name="viber")
console = Console()

# Channel parsers: name -> (module with SOURCE and parse_posts, default Viber chat name)
CHANNELS = {"baht_kyat": (baht_kyat, "Baht-Kyat")}

ViberDb = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Path to viber.db (copy it first).")]


@app.command()
def sources() -> None:
    """List available collectors."""
    table = Table("name", "domain", "description")
    for collector in registry().values():
        table.add_row(collector.name, collector.domain, collector.description)
    console.print(table)


@app.command()
def collect(
    names: Annotated[list[str], typer.Argument(help="Collector names (see `myanmardata sources`).")],
    out: Annotated[Path, typer.Option(help="Data root; snapshots go to <out>/<source>/snapshots/.")] = Path("data"),
    dry_run: Annotated[bool, typer.Option(help="Fetch and parse, but write nothing.")] = False,
) -> None:
    """Run collectors and append a snapshot for each source whose data changed."""
    available = registry()
    unknown = [n for n in names if n not in available]
    if unknown:
        raise typer.BadParameter(f"unknown collector(s): {', '.join(unknown)}", param_hint="NAMES")

    store = SnapshotStore(out)
    failed = []
    for name in names:
        try:
            collection = available[name].collect()
        except Exception as exc:  # one broken source must not stop the others
            console.print(f"[red]✗ {name}: {exc}[/red]")
            failed.append(name)
            continue
        if dry_run:
            console.print(f"[cyan]• {name}: parsed {len(collection.records)} records (dry run)[/cyan]")
            continue
        result = store.write(
            collection.source, collection.records, collection.collected_at, collection.raw, collection.raw_ext
        )
        if result.skipped_unchanged:
            console.print(f"• {name}: unchanged ({result.rows} records), nothing written")
        else:
            console.print(f"[green]✓ {name}: {result.rows} records → {result.snapshot}[/green]")
    if failed:
        raise typer.Exit(code=1)


@viber.command("tables")
def viber_tables(db: ViberDb) -> None:
    """Show every table and its columns (to diagnose an unfamiliar Viber version)."""
    for name, columns in viber_desktop.tables(db).items():
        console.print(f"[bold]{name}[/bold]: {', '.join(columns)}")


@viber.command("chats")
def viber_chats(db: ViberDb) -> None:
    """List chats and channels with their number of text messages."""
    table = Table("chat", "messages")
    for name, count in viber_desktop.chats(db):
        table.add_row(name, str(count))
    console.print(table)


@app.command("import")
def import_chat(
    channel: Annotated[str, typer.Argument(help=f"Channel parser: {', '.join(CHANNELS)}.")],
    viber_db: Annotated[
        Path | None, typer.Option(dir_okay=False, exists=True, help="Read posts from viber.db.")
    ] = None,
    chat: Annotated[str | None, typer.Option(help="Chat name in viber.db (defaults to the channel's name).")] = None,
    text: Annotated[
        Path | None, typer.Option(dir_okay=False, exists=True, help="Read posts pasted into a file.")
    ] = None,
    last_year: Annotated[int | None, typer.Option(help="--text without timestamps: year of the last post.")] = None,
    utc_offset: Annotated[str, typer.Option(help="--text timestamps: their UTC offset.")] = "+06:30",
    out: Annotated[Path, typer.Option(help="Data root; snapshots go to <out>/<source>/snapshots/.")] = Path("data"),
    dry_run: Annotated[bool, typer.Option(help="Parse and report, but write nothing.")] = False,
    show_skipped: Annotated[bool, typer.Option(help="Print posts that held no rates.")] = False,
) -> None:
    """Import rate posts from a chat channel's history; only observations not yet stored are written."""
    if channel not in CHANNELS:
        raise typer.BadParameter(f"unknown channel {channel!r}", param_hint="CHANNEL")
    if (viber_db is None) == (text is None):
        raise typer.BadParameter("give exactly one of --viber-db or --text")
    parser, default_chat = CHANNELS[channel]

    posts: list[Post]
    if viber_db is not None:
        posts = list(viber_desktop.posts(viber_db, chat or default_chat))
    else:
        assert text is not None
        posts = text_posts.read(text.read_text(encoding="utf-8"), last_year, text_posts.parse_offset(utc_offset))

    collected_at = datetime.now(UTC).replace(microsecond=0)
    quotes, report = parser.parse_posts(posts, utc_iso(collected_at))
    console.print(f"{report.posts} posts, {report.rate_posts} with rates, {len(quotes)} quotes")
    if posts:
        console.print(f"from {utc_iso(posts[0].posted_at)} to {utc_iso(posts[-1].posted_at)}")
    for warning in report.warnings:
        console.print(f"[yellow]! {warning}[/yellow]")
    if show_skipped:
        for post in report.skipped:
            console.print(f"[dim]skipped {utc_iso(post.posted_at)}: {post.text[:120]!r}[/dim]")
    if dry_run or not quotes:
        return

    raw = json.dumps(
        [
            {"posted_at": utc_iso(p.posted_at), "date_only": p.date_only, "id": p.record_id, "text": p.text}
            for p in posts
        ],
        ensure_ascii=False,
        indent=1,
    ).encode()
    result = SnapshotStore(out).write(parser.SOURCE, quotes, collected_at, raw, "json", only_new=True)
    if result.skipped_unchanged:
        console.print("• nothing new; every observation is already stored")
    else:
        console.print(f"[green]✓ {result.rows} new quotes → {result.snapshot}[/green]")


if __name__ == "__main__":
    app()
