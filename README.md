
# RepoRamp

Understand Python codebases through automated structural analysis
and optional local AI explanations.

## Status

Early development. Features are being built incrementally.

## Goals

- Discover Python source files safely.
- Extract modules, classes, functions, and imports.
- Analyze relationships between modules.
- Generate Markdown and JSON architecture reports.
- Offer optional, source-grounded local AI explanations.

## Development setup

Python 3.10 or later is required.

Create and activate a virtual environment, then install the
development dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Run tests:

```powershell
python -m pytest
```

Check code quality:

```powershell
ruff check .
ruff format --check .
```

## Project status

RepoRamp is not yet published on PyPI. Installation instructions
will be updated when a public release is available.
