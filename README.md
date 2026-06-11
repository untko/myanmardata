# myanmardata

![PyPI version](https://img.shields.io/pypi/v/myanmardata.svg)

project about myanmar data collection and analysis

* [GitHub](https://github.com/untko/myanmardata/) | [PyPI](https://pypi.org/project/myanmardata/) | [Documentation](https://untko.github.io/myanmardata/)
* Created by [untko](https://audrey.feldroy.com/) | GitHub [@untko](https://github.com/untko) | PyPI [@untko](https://pypi.org/user/untko/)
* MIT License

## Features

* TODO

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
# Clone your fork
git clone git@github.com:your_username/myanmardata.git
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
