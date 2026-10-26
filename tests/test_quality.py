from dataclasses import FrozenInstanceError

import pytest

from reporamp.quality import Finding
from pathlib import Path

from reporamp.quality import find_empty_modules
from reporamp.analyzer import DependencyEdge, DependencyGraph
from reporamp.quality import find_high_dependency_modules
from reporamp.quality import find_cycle_findings
from reporamp.quality import analyze_quality
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

    assert rule_ids == {"QR001", "QR002", "QR003"}
