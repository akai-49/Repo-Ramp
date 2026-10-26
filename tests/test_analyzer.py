from pathlib import Path

from reporamp.analyzer import (
    DependencyEdge,
    DependencyGraph,
    analyze_dependencies,
    find_dependency_cycles,
)
from reporamp.parser import parse_python_file


def _parse(root: Path, relative_path: str):
    return parse_python_file(root / relative_path)


def test_detects_internal_import_chain(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "from services.auth import login\n",
        encoding="utf-8",
    )

    services = tmp_path / "services"
    services.mkdir()
    (services / "__init__.py").write_text("", encoding="utf-8")
    (services / "auth.py").write_text(
        "import database\n",
        encoding="utf-8",
    )
    (tmp_path / "database.py").write_text("", encoding="utf-8")

    modules = [
        _parse(tmp_path, "app.py"),
        _parse(tmp_path, "services/__init__.py"),
        _parse(tmp_path, "services/auth.py"),
        _parse(tmp_path, "database.py"),
    ]

    graph = analyze_dependencies(modules, tmp_path)

    assert DependencyEdge("app", "services.auth") in graph.edges
    assert DependencyEdge("services.auth", "database") in graph.edges


def test_reports_unresolved_imports(tmp_path: Path) -> None:
    file_path = tmp_path / "app.py"
    file_path.write_text(
        "import external_library\n",
        encoding="utf-8",
    )

    graph = analyze_dependencies([parse_python_file(file_path)], tmp_path)

    assert ("app", "external_library") in graph.unresolved_imports
    assert graph.edges == ()


def test_finds_dependency_cycle() -> None:
    graph = DependencyGraph(
        modules=("a", "b", "c"),
        edges=(
            DependencyEdge("a", "b"),
            DependencyEdge("b", "a"),
            DependencyEdge("b", "c"),
        ),
        unresolved_imports=(),
    )

    assert find_dependency_cycles(graph) == (("a", "b"),)


def test_acyclic_graph_has_no_cycles() -> None:
    graph = DependencyGraph(
        modules=("app", "database", "services"),
        edges=(
            DependencyEdge("app", "services"),
            DependencyEdge("services", "database"),
        ),
        unresolved_imports=(),
    )

    assert find_dependency_cycles(graph) == ()


def test_graph_output_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "import z_module\nimport a_module\n",
        encoding="utf-8",
    )
    (tmp_path / "z_module.py").write_text("", encoding="utf-8")
    (tmp_path / "a_module.py").write_text("", encoding="utf-8")

    modules = [
        parse_python_file(tmp_path / name)
        for name in ("z_module.py", "app.py", "a_module.py")
    ]

    graph = analyze_dependencies(modules,tmp_path)

    assert graph.modules == ("a_module", "app", "z_module")
    assert graph.edges == (
        DependencyEdge("app", "a_module"),
        DependencyEdge("app", "z_module"),
    )
