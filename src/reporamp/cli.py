"""Command-line interface for RepoRamp."""

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from reporamp.analyzer import _module_name, analyze_dependencies
from reporamp.config import load_config
from reporamp.parser import parse_python_file
from reporamp.quality import analyze_quality, parse_rule_selection, select_findings
from reporamp.report import write_reports
from reporamp.scanner import scan_repository

app = typer.Typer(
    name="reporamp",
    help="Understand Python codebases through structural analysis.",
    no_args_is_help=True,
)

class ReportFormat(str, Enum):
    """Report formats that the analyze command can write."""

    md = "md"
    json = "json"
    both = "both"


def print_banner() -> None:
    """Display the RepoRamp CLI banner."""
    banner = r"""
 ____                 ____                      
|  _ \ ___ _ __   ___|  _ \ __ _ _ __ ___  _ __
| |_) / _ \ '_ \ / _ \ |_) / _` | '_ ` _ \| '_ \
|  _ <  __/ |_) |  __/  _ < (_| | | | | | | |_) |
|_| \_\___| .__/ \___|_| \_\__,_|_| |_| |_| .__/
          |_|                              |_|
"""
    typer.secho(banner, fg=typer.colors.BRIGHT_CYAN, bold=True)
    typer.secho(
        "          PYTHON CODEBASE INTELLIGENCE",
        fg=typer.colors.BRIGHT_WHITE,
        bold=True,
    )
    typer.echo("  Scan • Understand • Improve")
    typer.echo()



@app.command()
def version() -> None:
    """Display the installed RepoRamp version."""
    from reporamp import __version__

    typer.echo(f"RepoRamp {__version__}")


@app.command("analyze")
def analyze(
    root: Annotated[
        Path,
        typer.Argument(
            help="Repository directory to analyze.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
    ] = Path("."),
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory where reports will be written.",
        ),
    ] = Path("reporamp-report"),
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Exit with code 1 if any Python file cannot be parsed.",
        ),
    ] = False,
    max_deps: Annotated[
        int | None,
        typer.Option(
            "--max-deps",
            min=0,
            help=(
                "QR002 threshold: flag modules with more internal dependencies. "
                "Default: 5."
            ),
            show_default=False,
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            help=(
                "Glob pattern for files or directories to skip, matched against "
                "names and root-relative paths. Repeatable."
            ),
        ),
    ] = None,
    report_format: Annotated[
        ReportFormat | None,
        typer.Option(
            "--format",
            help="Which reports to write. Default: both.",
            show_default=False,
        ),
    ] = None,
    fail_on: Annotated[
        str | None,
        typer.Option(
            "--fail-on",
            help=(
                "Comma-separated rule IDs (or 'cycles' for QR003). Exit with "
                "code 2 if any matching finding exists, e.g. --fail-on QR003,QR002."
            ),
        ),
    ] = None,
) -> None:
    """Analyze a repository and generate Markdown and JSON reports.

    Settings from [tool.reporamp] in the repository's pyproject.toml are used
    as defaults; command-line flags override them.
    """
    root = root.resolve()

    try:
        config = load_config(root)
    except ValueError as exc:
        typer.echo(f"Error: invalid pyproject.toml: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if max_deps is None:
        max_deps = config.get("max_deps", 5)
    if exclude is None:
        exclude = config.get("exclude", [])
    if fail_on is None:
        fail_on = config.get("fail_on")
    if report_format is None:
        report_format = ReportFormat(config.get("format", "both"))

    try:
        fail_rules = parse_rule_selection(fail_on)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--fail-on") from exc

    output = output.resolve()

    print_banner()
    typer.secho("  Repository Analysis", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  Scanning: {root}")
    typer.echo()

    try:
        source_files = scan_repository(root, exclude=exclude)
        modules = []
        parse_errors: list[tuple[str, str]] = []

        for relative_path in source_files:
            try:
                modules.append(parse_python_file(root / relative_path))
            except (SyntaxError, UnicodeError) as exc:
                parse_errors.append((relative_path.as_posix(), str(exc)))

        for relative_path, error in parse_errors:
            typer.echo(f"Could not parse {relative_path}: {error}", err=True)

        graph = analyze_dependencies(modules, root)
        
        module_paths = {
    _module_name(module.path, root): module.path
    for module in modules
}
        findings = analyze_quality(
            module_paths,
            graph,
            dependency_threshold=max_deps,
        )
        report_paths = write_reports(
            modules,
            graph,
            output,
            root=root,
            findings=findings,
            parse_errors=parse_errors,
            report_format=report_format.value,
        )

    except (OSError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Python files discovered: {len(source_files)}")
    typer.echo(f"Modules analyzed: {len(modules)}")
    typer.echo(f"Internal dependencies: {len(graph.edges)}")
    typer.echo(f"Unresolved imports: {len(graph.unresolved_imports)}")
    typer.echo(f"Files with parse errors: {len(parse_errors)}")
    typer.echo("\nReports generated:")
    for report_path in report_paths:
        typer.echo(f"  {report_path}")

    if parse_errors:
        typer.echo(f"\nAnalysis completed with {len(parse_errors)} parse error(s).")
        if strict:
            raise typer.Exit(code=1)
    else:
        typer.echo("\nAnalysis completed successfully.")

    failing = select_findings(findings, fail_rules)

    if failing:
        typer.echo(
            f"\n{len(failing)} finding(s) matched --fail-on "
            f"{','.join(sorted(fail_rules))}:",
            err=True,
        )
        for finding in failing:
            typer.echo(
                f"  [{finding.rule_id}] {finding.module}: {finding.message}",
                err=True,
            )
        raise typer.Exit(code=2)

if __name__ == "__main__":
    app()
