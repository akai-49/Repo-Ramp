import ast
from dataclasses import dataclass
from pathlib import Path

from reporamp.analyzer import DependencyGraph, find_dependency_cycles


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


def analyze_quality(
    modules: dict[str, Path],
    graph: DependencyGraph,
    dependency_threshold: int = 5,
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

    return findings
