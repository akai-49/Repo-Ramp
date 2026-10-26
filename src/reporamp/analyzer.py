"""Analyze internal module dependencies in a Python repository."""

from dataclasses import dataclass
from pathlib import Path

from reporamp.parser import ModuleInfo


@dataclass(frozen=True)
class DependencyEdge:
    """Represent an import dependency between two repository modules."""

    source: str
    target: str


@dataclass(frozen=True)
class DependencyGraph:
    """Represent modules and their internal import dependencies."""

    modules: tuple[str, ...]
    edges: tuple[DependencyEdge, ...]
    unresolved_imports: tuple[tuple[str, str], ...]



def _module_name(path: Path, root: Path) -> str:
    """Convert a source path into a repository-relative module name."""
    relative_path = path.relative_to(root)
    parts = list(relative_path.with_suffix("").parts)

    # Support the common src-layout package structure:
    # src/reporamp/module.py -> reporamp.module
    if parts and parts[0] == "src":
        parts.pop(0)

    if parts and parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)



def _resolve_internal_import(
    imported_module: str,
    available_modules: set[str],
) -> str | None:
    """Resolve an import to a known repository module or package."""
    if imported_module in available_modules:
        return imported_module

    # A package may be imported even if only one of its submodules
    # appears in the scanned repository.
    package_candidates = [
        module
        for module in available_modules
        if module.startswith(f"{imported_module}.")
    ]

    if package_candidates:
        return imported_module if imported_module in available_modules else None

    return None


def analyze_dependencies(
    modules: list[ModuleInfo],
    root: Path,
) -> DependencyGraph:
    """Build a deterministic graph of internal repository imports.

    Each ModuleInfo.path must identify a source file beneath root.
    """
    root = root.resolve()

    module_by_name = {
        _module_name(module.path.resolve(), root): module for module in modules
    }
    available_modules = set(module_by_name)

    edges: set[DependencyEdge] = set()
    unresolved: set[tuple[str, str]] = set()

    for source_name, module_info in sorted(module_by_name.items()):
        for imported in module_info.imports:
            if imported.level > 0:
                # Relative imports are resolved from the containing package.
                package_parts = source_name.split(".")[:-1]

                if module_info.path.name == "__init__.py":
                    package_parts = source_name.split(".")

                ascend = imported.level - 1

                if ascend > len(package_parts):
                    unresolved.add(
                        (source_name, imported.module or imported.name or "")
                    )
                    continue

                package_parts = package_parts[: len(package_parts) - ascend]
                base = ".".join(package_parts)
                imported_module = ".".join(
                    part for part in (base, imported.module) if part
                )
            else:
                imported_module = imported.module or ""

            resolved = _resolve_internal_import(
                imported_module,
                available_modules,
            )

            # `from package import symbol` may refer to a submodule.
            if resolved is None and imported.name:
                candidate = (
                    f"{imported_module}.{imported.name}"
                    if imported_module
                    else imported.name
                )
                if candidate in available_modules:
                    resolved = candidate

            if resolved is None:
                unresolved.add(
                    (
                        source_name,
                        imported_module or imported.name or "<unknown>",
                    )
                )
                continue

            edges.add(DependencyEdge(source=source_name, target=resolved))

    return DependencyGraph(
        modules=tuple(sorted(available_modules)),
        edges=tuple(sorted(edges, key=lambda edge: (edge.source, edge.target))),
        unresolved_imports=tuple(sorted(unresolved)),
    )


def find_dependency_cycles(
    graph: DependencyGraph,
) -> tuple[tuple[str, ...], ...]:
    """Return dependency cycles using depth-first search."""
    adjacency: dict[str, list[str]] = {module: [] for module in graph.modules}

    for edge in graph.edges:
        adjacency[edge.source].append(edge.target)

    for neighbors in adjacency.values():
        neighbors.sort()

    cycles: set[tuple[str, ...]] = set()
    visited: set[str] = set()
    active: list[str] = []
    active_positions: dict[str, int] = {}

    def visit(node: str) -> None:
        visited.add(node)
        active_positions[node] = len(active)
        active.append(node)

        for neighbor in adjacency[node]:
            if neighbor in active_positions:
                cycle = active[active_positions[neighbor] :]
                rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
                cycles.add(min(rotations))
            elif neighbor not in visited:
                visit(neighbor)

        active.pop()
        del active_positions[node]

    for module in graph.modules:
        if module not in visited:
            visit(module)

    return tuple(sorted(cycles))
