from reporamp.ai import build_analysis_context
from reporamp.analyzer import DependencyEdge, DependencyGraph
from reporamp.parser import ModuleInfo
from reporamp.ai import generate_architecture_summary
from pathlib import Path
def test_build_analysis_context_for_empty_repository() -> None:
    empty_graph = DependencyGraph(
        modules=(),
        edges=(),
        unresolved_imports=(),
    )

    context = build_analysis_context([], empty_graph)

    assert context == {
        "module_count": 0,
        "dependency_count": 0,
        "unresolved_import_count": 0,
        "cycle_count": 0,
    }

def test_build_analysis_context_for_empty_repository() -> None:
    empty_graph = DependencyGraph(
        modules=(),
        edges=(),
        unresolved_imports=(),
    )

    context = build_analysis_context([], empty_graph)

    assert context == {
    "module_count": 0,
    "module_names": [],
    "dependency_count": 0,
    "dependencies": [],
    "unresolved_import_count": 0,
    "cycle_count": 0,
    "cycles": [],
}


def test_build_analysis_context_with_dependency() -> None:
    graph = DependencyGraph(
        modules=("main", "auth"),
        edges=(DependencyEdge(source="main", target="auth"),),
        unresolved_imports=(),
    )

    modules = [
        ModuleInfo(
            path=Path("main.py"),
            imports=(),
            functions=(),
            classes=(),
        ),
        ModuleInfo(
            path=Path("auth.py"),
            imports=(),
            functions=(),
            classes=(),
        ),
    ]

    context = build_analysis_context(modules, graph)

    assert context == {
    "module_count": 2,
    "module_names": ["auth.py", "main.py"],
    "dependency_count": 1,
    "dependencies": [
        {"source": "main", "target": "auth"}
    ],
    "unresolved_import_count": 0,
    "cycle_count": 0,
    "cycles": [],
}

def test_generate_architecture_summary() -> None:
    context = {
        "module_count": 2,
        "module_names": ["auth.py", "main.py"],
        "dependency_count": 1,
        "dependencies": [
            {"source": "main", "target": "auth"}
        ],
        "unresolved_import_count": 0,
        "cycle_count": 0,
        "cycles": [],
    }

    summary = generate_architecture_summary(context)

    assert "2 Python modules" in summary
    assert "1 internal dependencies" in summary
    assert "0 unresolved imports" in summary
    assert "0 dependency cycles" in summary
    assert "Module relationships:" in summary
    assert "- main depends on auth." in summary
