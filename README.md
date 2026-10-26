<p align="center">
  <img src="https://raw.githubusercontent.com/launchforgedev/Repo-Ramp/main/assets/reporamp-logo.png" alt="RepoRamp logo" width="420" />
</p>

<h1 align="center">RepoRamp</h1>

<p align="center">
  <strong>Python Codebase Intelligence</strong><br />
  Scan. Understand. Improve.
</p>

<p align="center">
  <a href="https://pypi.org/project/reporamp/"><img src="https://img.shields.io/pypi/v/reporamp?label=PyPI" alt="PyPI version" /></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python 3.10 or newer" />
  <a href="https://github.com/launchforgedev/Repo-Ramp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license" /></a>
</p>

<p align="center"><strong>Requires Python 3.10 or newer</strong></p>


RepoRamp is a command-line tool that helps developers understand the structure of a Python codebase. It scans Python modules, maps internal imports, detects dependency cycles, flags selected code-quality issues, and generates Markdown and JSON reports.

## Features

- **Python module discovery** — scans Python files while excluding common virtual environments, caches, and build directories.
- **Import and dependency analysis** — identifies relationships between modules in a project.
- **Circular dependency detection** — reports dependency cycles in the internal module graph.
- **Code-quality checks** — reports selected structural issues:
  - `QR001`: empty modules (empty `__init__.py` package markers are ignored)
  - `QR002`: modules with many internal dependencies
  - `QR003`: dependency cycles
- **Markdown and JSON reports** — keep a human-readable architecture overview and machine-readable analysis output.
- **Command-line interface** — run the analyzer from the project you want to inspect.

## Installation

Requires Python 3.10 or newer.

```bash
python -m pip install reporamp
```

## Quick start

Open a terminal in the Python project you want to analyze, then run:

```bash
cd path/to/your-project
reporamp analyze .
```

To choose an output location:

```bash
reporamp analyze . --output reporamp-report
```

Files that cannot be parsed (for example, syntax errors) are skipped, listed in the console, and recorded in a "Parse Errors" section of both reports. The run still exits with code 0; pass `--strict` to exit with code 1 when any file fails to parse:

```bash
reporamp analyze . --strict
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--output`, `-o` | `reporamp-report` | Directory where reports are written. |
| `--format md\|json\|both` | `both` | Which reports to write. |
| `--max-deps INT` | `5` | `QR002` threshold: flag modules with more internal dependencies than this. |
| `--exclude PATTERN` | — | Glob for files or directories to skip, matched against names and root-relative paths. Repeatable; added to the built-in exclusions (`.venv`, `build`, `__pycache__`, …). |
| `--strict` | off | Exit with code 1 if any file fails to parse. |

```bash
reporamp analyze . --exclude tests --exclude "migrations/*" --max-deps 8 --format md
```

See all supported options:

```bash
reporamp analyze --help
```

Check the installed version:

```bash
reporamp version
```

RepoRamp generates Markdown and JSON architecture reports. Use the Markdown report for a quick overview and the JSON report for tooling or further analysis.

## Example report

An analysis report can include:

- Number of Python modules analyzed
- Internal dependency count
- Standard-library and third-party imports
- Unresolved imports
- Dependency cycles
- Module imports, classes, and functions
- Code-quality findings and suggestions

## Quality rules

| Rule | What it checks |
| --- | --- |
| `QR001` | Empty Python modules (empty `__init__.py` files are ignored) |
| `QR002` | Modules with more outgoing internal dependencies than the configured threshold |
| `QR003` | Circular dependencies in the module graph |

These checks are structural signals to help guide code review; they do not replace tests, linting, or human judgment.

## Development

Clone the repository and install the project in editable mode with its development dependencies:

```bash
git clone https://github.com/launchforgedev/Repo-Ramp.git
cd Repo-Ramp
python -m pip install -e ".[dev]"
```

Run the tests:

```bash
pytest
```

## Continuous integration and releases

- `.github/workflows/ci.yml` runs `ruff check .` and `pytest` on Python 3.10–3.13 for every push to `main` and every pull request.
- `.github/workflows/release.yml` builds the package and publishes it to PyPI with [trusted publishing](https://docs.pypi.org/trusted-publishers/) when a `v*` tag is pushed (for example `v0.2.0`). It requires a `pypi` environment in the repository settings and a matching trusted publisher on PyPI.

## Current scope

RepoRamp currently focuses on static structural analysis of Python projects. AI-powered analysis is not part of the current release.

## Contributing

Issues, bug reports, and pull requests are welcome. Please include a clear description of the change and tests for new behavior where practical.

## License

RepoRamp is released under the MIT License. See [LICENSE](LICENSE).

## Links

- [PyPI package](https://pypi.org/project/reporamp/)
- [GitHub repository](https://github.com/launchforgedev/Repo-Ramp)
