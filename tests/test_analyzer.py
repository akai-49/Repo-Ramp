from pathlib import Path

from reporamp.analyzer import (
    DependencyEdge,
    DependencyGraph,
    analyze_dependencies,
    classify_import,
    coupling_metrics,
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

    graph = analyze_dependencies(modules, tmp_path)

    assert graph.modules == ("a_module", "app", "z_module")
    assert graph.edges == (
        DependencyEdge("app", "a_module"),
        DependencyEdge("app", "z_module"),
    )

def test_classifies_standard_library_imports() -> None:
    assert classify_import("pathlib") == "standard_library"
    assert classify_import("ast") == "standard_library"
    assert classify_import("os.path") == "standard_library"


def test_classifies_installed_third_party_imports() -> None:
    assert classify_import("pytest") == "third_party"


def test_classifies_unknown_imports() -> None:
    assert classify_import("reporamp_package_that_does_not_exist") == "unresolved"


def test_classifies_empty_import() -> None:
    assert classify_import("") == "unresolved"

def _write_app_package(root: Path) -> list:
    app_dir = root / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("VERSION = 1\n", encoding="utf-8")
    (app_dir / "models.py").write_text("", encoding="utf-8")
    (app_dir / "services.py").write_text("", encoding="utf-8")
    return [
        _parse(root, "app/__init__.py"),
        _parse(root, "app/models.py"),
        _parse(root, "app/services.py"),
    ]


def test_from_package_import_submodules(tmp_path: Path) -> None:
    modules = _write_app_package(tmp_path)
    (tmp_path / "app" / "api.py").write_text(
        "from app import models, services, VERSION\n",
        encoding="utf-8",
    )
    modules.append(_parse(tmp_path, "app/api.py"))

    graph = analyze_dependencies(modules, tmp_path)

    assert graph.edges == (
        DependencyEdge("app.api", "app"),
        DependencyEdge("app.api", "app.models"),
        DependencyEdge("app.api", "app.services"),
    )


def test_relative_from_dot_import_submodules(tmp_path: Path) -> None:
    modules = _write_app_package(tmp_path)
    (tmp_path / "app" / "api.py").write_text(
        "from . import models\nfrom . import VERSION\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "__init__.py").write_text(
        "from . import services\n",
        encoding="utf-8",
    )
    modules = [
        _parse(tmp_path, path)
        for path in (
            "app/__init__.py",
            "app/api.py",
            "app/models.py",
            "app/services.py",
        )
    ]

    graph = analyze_dependencies(modules, tmp_path)

    assert graph.edges == (
        DependencyEdge("app", "app.services"),
        DependencyEdge("app.api", "app"),
        DependencyEdge("app.api", "app.models"),
    )


def test_coupling_metrics() -> None:
    graph = DependencyGraph(
        modules=("a", "b", "c", "lonely"),
        edges=(
            DependencyEdge("a", "b"),
            DependencyEdge("a", "c"),
            DependencyEdge("b", "c"),
        ),
        unresolved_imports=(),
    )

    metrics = {item.module: item for item in coupling_metrics(graph)}

    assert [item.module for item in coupling_metrics(graph)] == [
        "a",
        "b",
        "c",
        "lonely",
    ]
    assert (metrics["a"].fan_in, metrics["a"].fan_out) == (0, 2)
    assert metrics["a"].instability == 1.0
    assert metrics["b"].instability == 0.5
    assert metrics["c"].instability == 0.0
    assert metrics["lonely"].instability is None
