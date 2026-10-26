"""Generate Markdown and JSON reports from repository analysis."""

import json
from pathlib import Path

from reporamp.analyzer import (
    DependencyGraph,
    classify_import,
    find_dependency_cycles,
)
from reporamp.parser import ModuleInfo
from reporamp.quality import Finding


def _classify_unresolved_imports(
    graph: DependencyGraph,
) -> dict[str, list[tuple[str, str]]]:
    """Group non-internal imports by their detected category."""
    categories: dict[str, list[tuple[str, str]]] = {
        "standard_library": [],
        "third_party": [],
        "unresolved": [],
    }

    for source, imported in graph.unresolved_imports:
        category = classify_import(imported)
        categories[category].append((source, imported))

    return categories

def _display_path(path: Path, root: Path | None = None) -> str:
    """Return a repository-relative path when the root is provided."""
    if root is not None:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass

    return path.as_posix()

def render_markdown(
    modules: list[ModuleInfo],
    graph: DependencyGraph,
    root: Path | None = None,
    findings: list[Finding] | None = None,
) -> str:
    """Render repository analysis as a Markdown document."""
    categories = _classify_unresolved_imports(graph)

    lines = [
        "# RepoRamp Architecture Report",
        "",
        "## Summary",
        "",
        f"- Python modules analyzed: {len(modules)}",
        f"- Internal dependencies: {len(graph.edges)}",
        f"- Standard-library imports: {len(categories['standard_library'])}",
        f"- Third-party imports: {len(categories['third_party'])}",
        f"- Unresolved imports: {len(categories['unresolved'])}",
        f"- Dependency cycles: {len(find_dependency_cycles(graph))}",
        "",
        "## Modules",
        "",
    ]

    for module in sorted(modules, key=lambda item: item.path.as_posix()):
        lines.extend(
            [
                f"### `{_display_path(module.path, root)}`",
                "",
                "#### Imports",
                "",
            ]
        )

        if module.imports:
            for item in module.imports:
                if item.level:
                    prefix = "." * item.level
                    imported_module = f"{prefix}{item.module or ''}"
                else:
                    imported_module = item.module or ""

                if item.name:
                    imported_module = f"{imported_module}:{item.name}"

                if item.alias:
                    imported_module = f"{imported_module} as {item.alias}"

                lines.append(f"- Line {item.line_number}: `{imported_module}`")
        else:
            lines.append("- None")

        lines.extend(["", "#### Classes", ""])

        if module.classes:
            for item in module.classes:
                bases = f" ({', '.join(item.bases)})" if item.bases else ""
                lines.append(f"- `{item.name}`{bases} — line {item.line_number}")
        else:
            lines.append("- None")

        lines.extend(["", "#### Functions and methods", ""])

        if module.functions:
            for item in module.functions:
                kind = "method" if item.parent_class else "function"
                async_prefix = "async " if item.is_async else ""
                parent = f" in `{item.parent_class}`" if item.parent_class else ""
                lines.append(
                    f"- {async_prefix}`{item.name}` ({kind}){parent}"
                    f" — line {item.line_number}"
                )
        else:
            lines.append("- None")

        lines.append("")

    lines.extend(["## Internal Dependencies", ""])

    if graph.edges:
        for edge in graph.edges:
            lines.append(f"- `{edge.source}` → `{edge.target}`")
    else:
        lines.append("- None detected")

    for category, title in (
        ("standard_library", "Standard Library Imports"),
        ("third_party", "Third-Party Imports"),
        ("unresolved", "Unresolved Imports"),
    ):
        lines.extend(["", f"## {title}", ""])

        imports = categories[category]

        if imports:
            for source, imported in imports:
                lines.append(f"- `{source}` imports `{imported}`")
        else:
            lines.append("- None")

    lines.extend(["", "## Dependency Cycles", ""])

    cycles = find_dependency_cycles(graph)

    if cycles:
        for cycle in cycles:
            cycle_path = " → ".join((*cycle, cycle[0]))
            lines.append(f"- {cycle_path}")
    else:
        lines.append("- None detected")

    lines.append("")
    lines.extend(["## Code Quality Findings", ""])
    if findings:
        for finding in findings:
            lines.extend(
                [
                    f"### [{finding.rule_id}] {finding.severity.upper()}",
                    "",
                    f"- **Module:** `{finding.module}`",
                    f"- **Issue:** {finding.message}",
                    f"- **Suggestion:** {finding.suggestion}",
                    "",
                ]
            )
    else:
        lines.extend(["No code quality findings.", ""])
    return "\n".join(lines)


def render_json(
    modules: list[ModuleInfo],
    graph: DependencyGraph,
    root: Path | None = None,
    findings: list[Finding] | None = None,
) -> str:
    """Render repository analysis as deterministic JSON."""
    categories = _classify_unresolved_imports(graph)

    payload = {
        "schema_version": 1,
        "summary": {
            "modules": len(modules),
            "internal_dependencies": len(graph.edges),
            "standard_library_imports": len(categories["standard_library"]),
            "third_party_imports": len(categories["third_party"]),
            "unresolved_imports": len(categories["unresolved"]),
            "dependency_cycles": len(find_dependency_cycles(graph)),
            
        },
        "quality_findings": [
                    {
                        "rule_id": finding.rule_id,
                        "severity": finding.severity,
                        "message": finding.message,
                        "module": finding.module,
                        "suggestion": finding.suggestion,
                    }
                    for finding in (findings or [])
                ],
        "modules": [
            {
                "path":  _display_path(module.path, root),
                "imports": [
                    {
                        "module": item.module,
                        "name": item.name,
                        "alias": item.alias,
                        "level": item.level,
                        "line": item.line_number,
                    }
                    for item in module.imports
                ],
                "classes": [
                    {
                        "name": item.name,
                        "line": item.line_number,
                        "end_line": item.end_line_number,
                        "bases": list(item.bases),
                    }
                    for item in module.classes
                ],
                "functions": [
                    {
                        "name": item.name,
                        "line": item.line_number,
                        "end_line": item.end_line_number,
                        "is_async": item.is_async,
                        "parent_class": item.parent_class,
                    }
                    for item in module.functions
                ],
            }
            for module in sorted(modules, key=lambda item: item.path.as_posix())
        ],
        "dependencies": [
            {"source": edge.source, "target": edge.target}
            for edge in graph.edges
        ],
        "standard_library_imports": [
            {"source": source, "module": imported}
            for source, imported in categories["standard_library"]
        ],
        "third_party_imports": [
            {"source": source, "module": imported}
            for source, imported in categories["third_party"]
        ],
        "unresolved_imports": [
            {"source": source, "module": imported}
            for source, imported in categories["unresolved"]
        ],
        "dependency_cycles": [
            list(cycle) for cycle in find_dependency_cycles(graph)
        ],
    }

    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

def write_reports(
    modules: list[ModuleInfo],
    graph: DependencyGraph,
    output_dir: Path,
    root: Path | None = None,
    findings: list[Finding] | None = None,
) -> tuple[Path, Path]:
    """Write Markdown and JSON reports to an output directory."""
    output_dir = Path(output_dir)

    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(f"Report output path is not a directory: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = output_dir / "report.md"
    json_path = output_dir / "report.json"

    markdown_path.write_text(
    render_markdown(modules, graph, root, findings),
    encoding="utf-8",
)
    json_path.write_text(
    render_json(modules, graph, root, findings),
    encoding="utf-8",
)

    return markdown_path, json_path
