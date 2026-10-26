"""Run the full RepoRamp analysis for a repository."""

from dataclasses import dataclass
from pathlib import Path

from reporamp.analyzer import DependencyGraph, _module_name, analyze_dependencies
from reporamp.config import DEFAULTS, load_config, load_entry_points
from reporamp.parser import ModuleInfo, parse_python_file
from reporamp.quality import Finding, analyze_quality
from reporamp.scanner import scan_repository


@dataclass(frozen=True)
class Analysis:
    """Results of analyzing one repository."""

    source_files: list[Path]
    modules: list[ModuleInfo]
    parse_errors: list[tuple[str, str]]
    graph: DependencyGraph
    findings: list[Finding]


def run_analysis(
    root: Path,
    exclude: list[str] | tuple[str, ...] = (),
    max_deps: int = DEFAULTS["max_deps"],
    max_fan_in: int = DEFAULTS["max_fan_in"],
    max_module_lines: int = DEFAULTS["max_module_lines"],
    max_function_lines: int = DEFAULTS["max_function_lines"],
) -> Analysis:
    """Scan, parse and analyze ``root``; unparsable files are collected."""
    root = Path(root).resolve()
    source_files = scan_repository(root, exclude=exclude)
    modules = []
    parse_errors: list[tuple[str, str]] = []

    for relative_path in source_files:
        try:
            modules.append(parse_python_file(root / relative_path))
        except (SyntaxError, UnicodeError) as exc:
            parse_errors.append((relative_path.as_posix(), str(exc)))

    graph = analyze_dependencies(modules, root)
    module_paths = {_module_name(module.path, root): module.path for module in modules}
    findings = analyze_quality(
        module_paths,
        graph,
        dependency_threshold=max_deps,
        fan_in_threshold=max_fan_in,
        max_module_lines=max_module_lines,
        max_function_lines=max_function_lines,
        entry_points=load_entry_points(root),
    )

    return Analysis(source_files, modules, parse_errors, graph, findings)


def run_configured_analysis(root: Path) -> Analysis:
    """Run ``run_analysis`` with settings from the repository's pyproject.toml."""
    config = {**DEFAULTS, **load_config(root)}

    return run_analysis(
        root,
        exclude=config["exclude"],
        max_deps=config["max_deps"],
        max_fan_in=config["max_fan_in"],
        max_module_lines=config["max_module_lines"],
        max_function_lines=config["max_function_lines"],
    )
