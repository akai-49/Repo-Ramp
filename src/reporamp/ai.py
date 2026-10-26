
"""Optional AI-powered insights for RepoRamp."""

from reporamp.analyzer import DependencyGraph, find_dependency_cycles
from reporamp.parser import ModuleInfo


def build_analysis_context(
    modules: list[ModuleInfo],
    graph: DependencyGraph,
) -> dict[str, object]:
    """Build a structured summary from repository analysis results."""
    cycles = find_dependency_cycles(graph)

    return {
        "module_count": len(modules),
        "module_names": sorted(
            module.path.as_posix() for module in modules
        ),
        "dependency_count": len(graph.edges),
        "dependencies": [
            {"source": edge.source, "target": edge.target}
            for edge in graph.edges
        ],
        "unresolved_import_count": len(graph.unresolved_imports),
        "cycle_count": len(cycles),
        "cycles": [list(cycle) for cycle in cycles],
    }


def generate_architecture_summary(
    context: dict[str, object],
) -> str:
    """Generate a basic architecture summary without an AI provider."""
    module_count = context["module_count"]
    dependency_count = context["dependency_count"]
    unresolved_count = context["unresolved_import_count"]
    cycle_count = context["cycle_count"]

    lines = [
        f"The repository contains {module_count} Python modules "
        f"and {dependency_count} internal dependencies.",
        f"It has {unresolved_count} unresolved imports and "
        f"{cycle_count} dependency cycles.",
    ]

    dependencies = context["dependencies"]

    if dependencies:
        lines.append("Module relationships:")

        for dependency in dependencies:
            lines.append(
                f"- {dependency['source']} depends on "
                f"{dependency['target']}."
            )
    else:
        lines.append("No internal module dependencies were detected.")

    return "\n".join(lines)
