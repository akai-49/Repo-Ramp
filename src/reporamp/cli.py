"""Command-line interface for RepoRamp."""

from pathlib import Path
from typing import Annotated

import typer

from reporamp.analyzer import _module_name, analyze_dependencies
from reporamp.parser import parse_python_file
from reporamp.quality import analyze_quality
from reporamp.report import write_reports
from reporamp.scanner import scan_repository

app = typer.Typer(
    name="reporamp",
    help="Understand Python codebases through structural analysis.",
    no_args_is_help=True,
)

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
) -> None:
    """Analyze a repository and generate Markdown and JSON reports."""
    root = root.resolve()
    output = output.resolve()

    print_banner()
    typer.secho("  Repository Analysis", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  Scanning: {root}")
    typer.echo()

    try:
        source_files = scan_repository(root)
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
        findings = analyze_quality(module_paths, graph)
        markdown_path, json_path = write_reports(
            modules,
            graph,
            output,
            root=root,
            findings=findings,
            parse_errors=parse_errors,
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
    typer.echo(f"  {markdown_path}")
    typer.echo(f"  {json_path}")

    if parse_errors:
        typer.echo(f"\nAnalysis completed with {len(parse_errors)} parse error(s).")
        if strict:
            raise typer.Exit(code=1)
        return

    typer.echo("\nAnalysis completed successfully.")


if __name__ == "__main__":
    app()
