"""Command-line interface for RepoRamp."""

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from reporamp.ai import (
    AISummaryUnavailable,
    build_analysis_context,
    generate_ai_summary,
    generate_architecture_summary,
)
from reporamp.analyzer import _module_name, analyze_dependencies
from reporamp.config import load_config, load_entry_points
from reporamp.diff import diff_reports, has_new_problems, load_report, render_diff
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
    max_fan_in: Annotated[
        int | None,
        typer.Option(
            "--max-fan-in",
            min=0,
            help="QR004 threshold: flag modules imported by more modules. Default: 10.",
            show_default=False,
        ),
    ] = None,
    max_module_lines: Annotated[
        int | None,
        typer.Option(
            "--max-module-lines",
            min=0,
            help="QR006 threshold: flag modules with more lines. Default: 1000.",
            show_default=False,
        ),
    ] = None,
    max_function_lines: Annotated[
        int | None,
        typer.Option(
            "--max-function-lines",
            min=0,
            help="QR006 threshold: flag functions with more lines. Default: 100.",
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
    ai: Annotated[
        bool,
        typer.Option(
            "--ai",
            help=(
                "Add an architecture summary written by Claude (needs "
                'ANTHROPIC_API_KEY and pip install "reporamp[ai]"). Only '
                "module names and dependency data are sent, never source code."
            ),
        ),
    ] = False,
) -> None:
    """Analyze a repository and generate Markdown and JSON reports.

    Settings from [tool.reporamp] in the repository's pyproject.toml are used
    as defaults; command-line flags override them.
    """
    root = root.resolve()

    try:
        config = load_config(root)
        entry_points = load_entry_points(root)
    except ValueError as exc:
        typer.echo(f"Error: invalid pyproject.toml: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if max_deps is None:
        max_deps = config.get("max_deps", 5)
    if max_fan_in is None:
        max_fan_in = config.get("max_fan_in", 10)
    if max_module_lines is None:
        max_module_lines = config.get("max_module_lines", 1000)
    if max_function_lines is None:
        max_function_lines = config.get("max_function_lines", 100)
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
            fan_in_threshold=max_fan_in,
            max_module_lines=max_module_lines,
            max_function_lines=max_function_lines,
            entry_points=entry_points,
        )
        summary = None
        if ai:
            context = build_analysis_context(modules, graph, root)
            try:
                summary = generate_ai_summary(context)
                typer.echo("AI architecture summary generated.")
            except AISummaryUnavailable as exc:
                typer.echo(
                    f"AI summary unavailable ({exc}); using the local summary.",
                    err=True,
                )
                summary = generate_architecture_summary(context)

        report_paths = write_reports(
            modules,
            graph,
            output,
            root=root,
            findings=findings,
            parse_errors=parse_errors,
            report_format=report_format.value,
            summary=summary,
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


@app.command("diff")
def diff(
    base: Annotated[
        Path,
        typer.Argument(help="Baseline report.json.", exists=True, dir_okay=False),
    ],
    head: Annotated[
        Path,
        typer.Argument(help="New report.json to compare.", exists=True, dir_okay=False),
    ],
    fail_on_new: Annotated[
        bool,
        typer.Option(
            "--fail-on-new",
            help="Exit with code 2 if HEAD has new cycles or findings.",
        ),
    ] = False,
) -> None:
    """Compare two JSON reports: modules, dependencies, cycles and findings."""
    try:
        changes = diff_reports(load_report(base), load_report(head))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(render_diff(changes))

    if fail_on_new and has_new_problems(changes):
        raise typer.Exit(code=2)

if __name__ == "__main__":
    app()
