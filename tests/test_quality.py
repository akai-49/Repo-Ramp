from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from reporamp.analyzer import DependencyEdge, DependencyGraph
from reporamp.quality import (
    Finding,
    analyze_quality,
    find_cycle_findings,
    find_empty_modules,
    find_high_dependency_modules,
    find_high_fan_in_modules,
    find_orphan_modules,
    find_oversized_code,
    parse_rule_selection,
    select_findings,
)


def test_finding_stores_its_fields():
    finding = Finding(
        rule_id="QR001",
        severity="warning",
        message="Too many dependencies",
        module="reporamp.cli",
        suggestion="Split responsibilities",
    )

    assert finding.rule_id == "QR001"
    assert finding.severity == "warning"
    assert finding.message == "Too many dependencies"
    assert finding.module == "reporamp.cli"
    assert finding.suggestion == "Split responsibilities"


def test_finding_is_immutable():
    finding = Finding(
        rule_id="QR001",
        severity="warning",
        message="Too many dependencies",
        module="reporamp.cli",
        suggestion="Split responsibilities",
    )

    with pytest.raises(FrozenInstanceError):
        finding.severity = "critical"

def test_detects_empty_module(tmp_path: Path):
    module_path = tmp_path / "empty.py"
    module_path.write_text("", encoding="utf-8")

    findings = find_empty_modules({"empty": module_path})

    assert len(findings) == 1
    assert findings[0].rule_id == "QR001"
    assert findings[0].module == "empty"


def test_does_not_flag_module_with_function(tmp_path: Path):
    module_path = tmp_path / "helpers.py"
    module_path.write_text(
        "def greet():\n    return 'Hello'\n",
        encoding="utf-8",
    )

    findings = find_empty_modules({"helpers": module_path})

    assert findings == []


def test_does_not_flag_docstring_only_module(tmp_path: Path):
    module_path = tmp_path / "documented.py"
    module_path.write_text(
        '"""Module documentation."""\n',
        encoding="utf-8",
    )

    findings = find_empty_modules({"documented": module_path})

    assert findings == []



def test_detects_module_with_too_many_dependencies():
    graph = DependencyGraph(
        modules=("main", "a", "b", "c", "d", "e", "f"),
        edges=(
            DependencyEdge("main", "a"),
            DependencyEdge("main", "b"),
            DependencyEdge("main", "c"),
            DependencyEdge("main", "d"),
            DependencyEdge("main", "e"),
            DependencyEdge("main", "f"),
        ),
        unresolved_imports=(),
    )

    findings = find_high_dependency_modules(graph)

    assert len(findings) == 1
    assert findings[0].rule_id == "QR002"
    assert findings[0].module == "main"
    assert "6 internal modules" in findings[0].message


def test_does_not_flag_module_at_threshold():
    graph = DependencyGraph(
        modules=("main", "a", "b", "c", "d", "e"),
        edges=(
            DependencyEdge("main", "a"),
            DependencyEdge("main", "b"),
            DependencyEdge("main", "c"),
            DependencyEdge("main", "d"),
            DependencyEdge("main", "e"),
        ),
        unresolved_imports=(),
    )

    findings = find_high_dependency_modules(graph)

    assert findings == []


def test_counts_distinct_dependencies_only():
    graph = DependencyGraph(
        modules=("main", "a", "b", "c", "d", "e"),
        edges=(
            DependencyEdge("main", "a"),
            DependencyEdge("main", "a"),
            DependencyEdge("main", "b"),
            DependencyEdge("main", "c"),
            DependencyEdge("main", "d"),
            DependencyEdge("main", "e"),
        ),
        unresolved_imports=(),
    )

    findings = find_high_dependency_modules(graph)

    assert findings == []


def test_detects_circular_dependency():
    graph = DependencyGraph(
        modules=("auth", "users"),
        edges=(
            DependencyEdge("auth", "users"),
            DependencyEdge("users", "auth"),
        ),
        unresolved_imports=(),
    )

    findings = find_cycle_findings(graph)

    assert len(findings) == 1
    assert findings[0].rule_id == "QR003"
    assert "auth -> users -> auth" in findings[0].message
    assert findings[0].module == "auth"
    assert findings[0].suggestion


def test_no_findings_for_acyclic_dependencies():
    graph = DependencyGraph(
        modules=("main", "auth", "users"),
        edges=(
            DependencyEdge("main", "auth"),
            DependencyEdge("auth", "users"),
        ),
        unresolved_imports=(),
    )

    findings = find_cycle_findings(graph)

    assert findings == []


def test_analyze_quality_combines_findings(tmp_path: Path):
    empty_file = tmp_path / "empty.py"
    empty_file.write_text("", encoding="utf-8")

    graph = DependencyGraph(
        modules=("main", "a", "b", "c", "d", "e", "f", "g"),
        edges=(
            DependencyEdge("main", "a"),
            DependencyEdge("main", "b"),
            DependencyEdge("main", "c"),
            DependencyEdge("main", "d"),
            DependencyEdge("main", "e"),
            DependencyEdge("main", "f"),
            DependencyEdge("main", "g"),
            DependencyEdge("a", "b"),
            DependencyEdge("b", "a"),
        ),
        unresolved_imports=(),
    )

    findings = analyze_quality(
        modules={"empty": empty_file},
        graph=graph,
    )

    rule_ids = {finding.rule_id for finding in findings}

    assert rule_ids == {"QR001", "QR002", "QR003", "QR005"}


def test_does_not_flag_empty_package_init(tmp_path: Path):
    init_path = tmp_path / "__init__.py"
    init_path.write_text("", encoding="utf-8")
    empty_path = tmp_path / "empty.py"
    empty_path.write_text("", encoding="utf-8")

    findings = find_empty_modules({"pkg": init_path, "pkg.empty": empty_path})

    assert [finding.module for finding in findings] == ["pkg.empty"]


def test_parse_rule_selection_accepts_ids_and_aliases():
    assert parse_rule_selection(" qr003, QR002 ,") == {"QR002", "QR003"}
    assert parse_rule_selection("cycles") == {"QR003"}
    assert parse_rule_selection(None) == frozenset()


def test_parse_rule_selection_rejects_unknown_rules():
    with pytest.raises(ValueError, match="QR999"):
        parse_rule_selection("QR999")


def test_select_findings_filters_by_rule():
    findings = [
        Finding("QR001", "warning", "empty", "a", "fix"),
        Finding("QR003", "warning", "cycle", "b", "fix"),
    ]

    assert select_findings(findings, frozenset({"QR003"})) == [findings[1]]


def test_detects_high_fan_in_module():
    graph = DependencyGraph(
        modules=("core", "a", "b", "c"),
        edges=(
            DependencyEdge("a", "core"),
            DependencyEdge("b", "core"),
            DependencyEdge("c", "core"),
            DependencyEdge("a", "b"),
        ),
        unresolved_imports=(),
    )

    findings = find_high_fan_in_modules(graph, threshold=2)

    assert [(f.rule_id, f.module) for f in findings] == [("QR004", "core")]
    assert "imported by 3 internal modules" in findings[0].message
    assert findings[0].suggestion
    assert find_high_fan_in_modules(graph, threshold=3) == []


def test_detects_orphan_modules_but_not_entry_points(tmp_path: Path):
    graph = DependencyGraph(
        modules=(
            "app",
            "app.__main__",
            "app.cli",
            "app.core",
            "app.unused",
            "conftest",
            "tests.test_core",
        ),
        edges=(DependencyEdge("app.cli", "app.core"),),
        unresolved_imports=(),
    )
    init_path = tmp_path / "__init__.py"

    findings = find_orphan_modules(
        {"app": init_path},
        graph,
        entry_points=frozenset({"app.cli"}),
    )

    assert [(f.rule_id, f.severity, f.module) for f in findings] == [
        ("QR005", "info", "app.unused")
    ]
    assert findings[0].suggestion


def test_detects_oversized_modules_and_functions(tmp_path: Path):
    module_path = tmp_path / "big.py"
    module_path.write_text(
        "def small():\n    return 1\n\n\n"
        "def large():\n    a = 1\n    b = 2\n    return a + b\n",
        encoding="utf-8",
    )

    findings = find_oversized_code(
        {"big": module_path},
        max_module_lines=5,
        max_function_lines=3,
    )

    assert [f.rule_id for f in findings] == ["QR006", "QR006"]
    assert "8 lines (limit 5)" in findings[0].message
    assert "`large` (line 5) has 4 lines (limit 3)" in findings[1].message
    assert all(f.suggestion for f in findings)
    assert find_oversized_code({"big": module_path}) == []
