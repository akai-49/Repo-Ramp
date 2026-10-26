import json
from pathlib import Path

import pytest

from reporamp.analyzer import DependencyGraph, analyze_dependencies
from reporamp.parser import parse_python_file
from reporamp.report import render_json, render_markdown, write_reports


def build_analysis(root: Path):
    (root / "app.py").write_text(
        "from services.auth import login\n\ndef main():\n    login()\n",
        encoding="utf-8",
    )

    services = root / "services"
    services.mkdir()
    (services / "__init__.py").write_text("", encoding="utf-8")
    (services / "auth.py").write_text(
        "class AuthService:\n    pass\n\ndef login():\n    pass\n",
        encoding="utf-8",
    )

    modules = [
        parse_python_file(path)
        for path in (
            root / "app.py",
            services / "__init__.py",
            services / "auth.py",
        )
    ]
    graph = analyze_dependencies(modules, root)

    return modules, graph


def test_markdown_contains_summary_and_definitions(tmp_path: Path) -> None:
    modules, graph = build_analysis(tmp_path)

    report = render_markdown(modules, graph)

    assert "# RepoRamp Architecture Report" in report
    assert "Python modules analyzed: 3" in report
    assert "`AuthService`" in report
    assert "`login`" in report
    assert "`app` → `services.auth`" in report


def test_json_has_expected_schema(tmp_path: Path) -> None:
    modules, graph = build_analysis(tmp_path)

    payload = json.loads(render_json(modules, graph))

    assert payload["schema_version"] == 1
    assert payload["summary"]["modules"] == 3
    assert payload["summary"]["internal_dependencies"] == 1
    assert payload["dependencies"] == [{"source": "app", "target": "services.auth"}]


def test_json_output_is_deterministic(tmp_path: Path) -> None:
    modules, graph = build_analysis(tmp_path)

    first = render_json(modules, graph)
    second = render_json(modules, graph)

    assert first == second


def test_writes_both_report_files(tmp_path: Path) -> None:
    modules, graph = build_analysis(tmp_path)
    output_dir = tmp_path / "reports"

    markdown_path, json_path = write_reports(
        modules,
        graph,
        output_dir,
    )

    assert markdown_path.name == "report.md"
    assert json_path.name == "report.json"
    assert markdown_path.is_file()
    assert json_path.is_file()
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == 1


def test_rejects_file_as_output_directory(tmp_path: Path) -> None:
    modules, graph = build_analysis(tmp_path)
    output_path = tmp_path / "not_a_directory"
    output_path.write_text("occupied", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        write_reports(modules, graph, output_path)


def test_empty_analysis_produces_valid_reports() -> None:
    graph = DependencyGraph(
        modules=(),
        edges=(),
        unresolved_imports=(),
    )

    assert "Python modules analyzed: 0" in render_markdown([], graph)

    payload = json.loads(render_json([], graph))
    assert payload["modules"] == []
    assert payload["dependencies"] == []
