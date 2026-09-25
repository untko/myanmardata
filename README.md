# myanmardata

![PyPI version](https://img.shields.io/pypi/v/myanmardata.svg)

Collectors for hard-to-get Myanmar market data: informal and cash exchange rates, local gold,
fuel and agricultural prices that are not published through an API.

* [GitHub](https://github.com/untko/myanmardata/) | [PyPI](https://pypi.org/project/myanmardata/) | [Documentation](https://untko.github.io/myanmardata/)
* Created by [untko](https://github.com/untko)
* MIT License

## How it fits together

This repository holds **code, not data**. Each dataset lives in its own repository (public or
private) whose scheduled workflow installs `myanmardata`, runs the collectors it wants, and commits
the resulting snapshots:

```
myanmardata (this repo)            collectors · record schemas · snapshot store · CLI
   │  uvx --from git+…/myanmardata myanmardata collect <sources> --out data
   ▼
myanmar-fx-data   myanmar-gold-data   myanmar-agro-market-data   (private-…)
```

A copy-ready workflow for a data repository is in
[`templates/data-repo/.github/workflows/collect.yml`](templates/data-repo/.github/workflows/collect.yml).

## Collectors

| name | domain | what |
|---|---|---|
| `superrich_th` | fx | SuperRich Thailand (green), cash buy/sell in THB per denomination, incl. USD, CNY, MMK |

```sh
myanmardata sources
myanmardata collect superrich_th --out data
```

## Chat channels (Viber)

Local kyat rates are mostly posted in Viber channels, which have no public web view. Import a
channel's history from Viber Desktop's local database:

1. In Viber Desktop, open the channel and scroll up to the oldest post you want; only loaded
   posts are in the database.
2. Quit Viber (or copy the file) and locate `viber.db`:
   Windows `%APPDATA%\ViberPC\<phone>\viber.db`, macOS `~/Library/Application Support/ViberPC/<phone>/viber.db`.
3. Run:

```sh
myanmardata viber chats viber.db                                   # find the channel's name
myanmardata import baht_kyat --viber-db viber.db --dry-run         # check what parses
myanmardata import baht_kyat --viber-db viber.db --out data        # write new observations
```

Re-running on a newer copy only adds posts not already stored. If `viber chats` fails, run
`myanmardata viber tables viber.db`: Viber's schema is undocumented and may differ by version.

Without database access, paste posts into a text file and use `--text posts.txt`, either with an
`@ 2026-09-25 10:11` line (Myanmar time by default) before each post, or relying on each post's
`Update - 25 Sep` header with `--last-year 2026`.

| channel | parser | what |
|---|---|---|
| Baht-Kyat (Viber) | `baht_kyat` | THB→MMK buy/sell by deal size (≥ ฿10,000 / ≥ ฿100,000), Thai bank account transfers |

## Data layout and rules

```
data/<source>/snapshots/YYYY/YYYY-MM-DDTHH-MM-SSZ.csv   parsed rows, never rewritten
data/<source>/raw/YYYY/YYYY-MM-DDTHH-MM-SSZ.json.gz     the payload those rows came from
```

* Every row carries its `source`, `venue`, `method` (`api`, `html`, `chat`, `ocr`, `manual`),
  `observed_at` (when the price applies), `collected_at` (when it was fetched) and `source_url`.
* Values stay as published: prices are decimal strings, and denominations keep the source's spelling.
* FX series are identified by source, venue, currency pair, unit amount, denomination, minimum
  deal size and channel (cash, Thai bank account, ...).
  Different note sizes get different rates; never average across them.
* A batch identical to the latest snapshot is skipped. Sources without their own update time use
  the collection time as `observed_at`, so each run is kept.
* One failing source never blocks the others; the command exits non-zero after saving the rest.

## Documentation

Documentation is built with [Zensical](https://zensical.org/) and deployed to GitHub Pages.

* **Live site:** https://untko.github.io/myanmardata/
* **Preview locally:** `just docs-serve` (serves at http://localhost:8000)
* **Build:** `just docs-build`

API documentation is auto-generated from docstrings using [mkdocstrings](https://mkdocstrings.github.io/).

Docs deploy automatically on push to `main` via GitHub Actions. To enable this, go to your repo's Settings > Pages and set the source to **GitHub Actions**.

## Development

To set up for local development:

```bash
git clone git@github.com:untko/myanmardata.git
cd myanmardata

# Install in editable mode with live updates
uv tool install --editable .
```

This installs the CLI globally but with live updates - any changes you make to the source code are immediately available when you run `myanmardata`.

Run tests:

```bash
uv run pytest
```

Run quality checks (format, lint, type check, test):

```bash
just qa
```

## Author

myanmardata was created in 2026 by untko.

Built with [Cookiecutter](https://github.com/cookiecutter/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.
