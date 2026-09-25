"""Console script for myanmardata."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from myanmardata.collectors import registry
from myanmardata.store import SnapshotStore

app = typer.Typer(help="Collect Myanmar market data into append-only snapshots.", no_args_is_help=True)
console = Console()


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


if __name__ == "__main__":
    app()
