"""Command-line interface for RepoRamp."""

from pathlib import Path
from typing import Annotated

import typer

from reporamp.analyzer import analyze_dependencies
from reporamp.parser import parse_python_file
from reporamp.report import write_reports
from reporamp.scanner import scan_repository

app = typer.Typer(
    name="reporamp",
    help="Understand Python codebases through structural analysis.",
    no_args_is_help=True,
)


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
) -> None:
    """Analyze a repository and generate Markdown and JSON reports."""
    root = root.resolve()
    output = output.resolve()

    typer.echo("RepoRamp — Python Codebase Analyzer")
    typer.echo(f"Scanning: {root}")

    try:
        source_files = scan_repository(root)
        modules = []
        parse_errors: list[tuple[Path, str]] = []

        for relative_path in source_files:
            try:
                modules.append(parse_python_file(root / relative_path))
            except (SyntaxError, UnicodeError) as exc:
                parse_errors.append((relative_path, str(exc)))

        if parse_errors:
            for relative_path, error in parse_errors:
                typer.echo(
                    f"Could not parse {relative_path}: {error}",
                    err=True,
                )
            raise typer.Exit(code=1)

        graph = analyze_dependencies(modules, root)
        markdown_path, json_path = write_reports(
            modules,
            graph,
            output,
        )

    except (OSError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Python files discovered: {len(source_files)}")
    typer.echo(f"Modules analyzed: {len(modules)}")
    typer.echo(f"Internal dependencies: {len(graph.edges)}")
    typer.echo(f"Unresolved imports: {len(graph.unresolved_imports)}")
    typer.echo("\nReports generated:")
    typer.echo(f"  {markdown_path}")
    typer.echo(f"  {json_path}")
    typer.echo("\nAnalysis completed successfully.")


if __name__ == "__main__":
    app()
