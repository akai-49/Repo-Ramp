import ast
from dataclasses import dataclass
from pathlib import Path

from reporamp.analyzer import DependencyGraph, find_dependency_cycles

RULE_IDS = ("QR001", "QR002", "QR003", "QR004", "QR005", "QR006")

# `--fail-on` aliases for rule IDs.
RULE_ALIASES = {"cycles": "QR003"}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    module: str
    suggestion: str


def find_empty_modules(
    modules: dict[str, Path],
) -> list[Finding]:
    findings = []

    for module_name, file_path in modules.items():
        # An empty `__init__.py` is a package marker, not an unused module.
        if file_path.name == "__init__.py":
            continue

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (OSError, UnicodeError, SyntaxError):
            continue

        # Ignore only the actual module docstring.
        body = list(tree.body)

        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)

        if not body and not ast.get_docstring(tree):
            findings.append(
                Finding(
                    rule_id="QR001",
                    severity="warning",
                    message="Module contains no executable statements",
                    module=module_name,
                    suggestion=(
                        "Add the intended implementation or remove "
                        "the unused module"
                    ),
                )
            )

    return findings


def find_high_dependency_modules(
    graph: DependencyGraph,
    threshold: int = 5,
) -> list[Finding]:
    findings = []

    dependency_counts: dict[str, set[str]] = {}

    for edge in graph.edges:
        dependency_counts.setdefault(edge.source, set()).add(
            edge.target
        )

    for module, dependencies in dependency_counts.items():
        if len(dependencies) > threshold:
            findings.append(
                Finding(
                    rule_id="QR002",
                    severity="warning",
                    message=(
                        f"Module depends on {len(dependencies)} "
                        f"internal modules"
                    ),
                    module=module,
                    suggestion=(
                        "Review the module's responsibilities and "
                        "consider splitting it into smaller modules"
                    ),
                )
            )

    return findings


def find_cycle_findings(
    graph: DependencyGraph,
) -> list[Finding]:
    findings = []

    for cycle in find_dependency_cycles(graph):
        cycle_path = " -> ".join((*cycle, cycle[0]))

        findings.append(
            Finding(
                rule_id="QR003",
                severity="warning",
                message=f"Circular dependency detected: {cycle_path}",
                module=cycle[0],
                suggestion=(
                    "Break the cycle by moving shared functionality "
                    "into a separate module or reversing the dependency"
                ),
            )
        )

    return findings


def find_high_fan_in_modules(
    graph: DependencyGraph,
    threshold: int = 10,
) -> list[Finding]:
    importers: dict[str, set[str]] = {}

    for edge in graph.edges:
        importers.setdefault(edge.target, set()).add(edge.source)

    return [
        Finding(
            rule_id="QR004",
            severity="warning",
            message=f"Module is imported by {len(sources)} internal modules",
            module=module,
            suggestion=(
                "This may be a 'god module'; split unrelated responsibilities "
                "so changes to it affect fewer modules"
            ),
        )
        for module, sources in sorted(importers.items())
        if len(sources) > threshold
    ]


# Modules that are run or discovered by tools rather than imported.
ENTRY_POINT_NAMES = frozenset({"__main__", "conftest", "setup"})


def _is_entry_point(module: str, file_path: Path | None) -> bool:
    leaf = module.rsplit(".", maxsplit=1)[-1]
    return (
        leaf in ENTRY_POINT_NAMES
        or leaf.startswith("test_")
        or leaf.endswith("_test")
        or (file_path is not None and file_path.name == "__init__.py")
    )


def find_orphan_modules(
    modules: dict[str, Path],
    graph: DependencyGraph,
    entry_points: frozenset[str] = frozenset(),
) -> list[Finding]:
    imported = {edge.target for edge in graph.edges}

    return [
        Finding(
            rule_id="QR005",
            severity="info",
            message="Module is not imported by any other module",
            module=module,
            suggestion=(
                "Remove the module if it is unused, or register it as an "
                "entry point (for example a console script) if it is run directly"
            ),
        )
        for module in graph.modules
        if module not in imported
        and module not in entry_points
        and not _is_entry_point(module, modules.get(module))
    ]


def find_oversized_code(
    modules: dict[str, Path],
    max_module_lines: int = 1000,
    max_function_lines: int = 100,
) -> list[Finding]:
    findings = []

    for module_name, file_path in modules.items():
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (OSError, UnicodeError, SyntaxError):
            continue

        line_count = len(source.splitlines())

        if line_count > max_module_lines:
            findings.append(
                Finding(
                    rule_id="QR006",
                    severity="warning",
                    message=(
                        f"Module has {line_count} lines "
                        f"(limit {max_module_lines})"
                    ),
                    module=module_name,
                    suggestion="Split the module into smaller, focused modules",
                )
            )

        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        for node in sorted(functions, key=lambda item: item.lineno):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > max_function_lines:
                findings.append(
                    Finding(
                        rule_id="QR006",
                        severity="warning",
                        message=(
                            f"Function `{node.name}` (line {node.lineno}) has "
                            f"{length} lines (limit {max_function_lines})"
                        ),
                        module=module_name,
                        suggestion="Extract parts of the function into helpers",
                    )
                )

    return findings


def analyze_quality(
    modules: dict[str, Path],
    graph: DependencyGraph,
    dependency_threshold: int = 5,
    fan_in_threshold: int = 10,
    max_module_lines: int = 1000,
    max_function_lines: int = 100,
    entry_points: frozenset[str] = frozenset(),
) -> list[Finding]:
    findings = []

    findings.extend(find_empty_modules(modules))
    findings.extend(
        find_high_dependency_modules(
            graph,
            threshold=dependency_threshold,
        )
    )
    findings.extend(find_cycle_findings(graph))
    findings.extend(find_high_fan_in_modules(graph, threshold=fan_in_threshold))
    findings.extend(find_orphan_modules(modules, graph, entry_points))
    findings.extend(
        find_oversized_code(
            modules,
            max_module_lines=max_module_lines,
            max_function_lines=max_function_lines,
        )
    )

    return findings


def parse_rule_selection(value: str | None) -> frozenset[str]:
    """Parse a comma-separated list of rule IDs or aliases such as ``cycles``."""
    selected = set()

    for item in (value or "").split(","):
        item = item.strip()
        if not item:
            continue
        rule_id = RULE_ALIASES.get(item.lower(), item.upper())
        if rule_id not in RULE_IDS:
            known = ", ".join((*RULE_IDS, *RULE_ALIASES))
            raise ValueError(f"Unknown rule {item!r}; expected one of: {known}")
        selected.add(rule_id)

    return frozenset(selected)


def select_findings(
    findings: list[Finding],
    rule_ids: frozenset[str],
) -> list[Finding]:
    """Return the findings whose rule ID is in ``rule_ids``."""
    return [finding for finding in findings if finding.rule_id in rule_ids]
