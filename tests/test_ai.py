import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from typer.testing import CliRunner

from reporamp.ai import (
    AI_MODEL,
    AISummaryUnavailable,
    build_analysis_context,
    generate_ai_summary,
    generate_architecture_summary,
)
from reporamp.analyzer import DependencyEdge, DependencyGraph
from reporamp.cli import app
from reporamp.parser import ModuleInfo

runner = CliRunner()


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


class _FakeAPIError(Exception):
    pass


def _install_fake_sdk(
    monkeypatch, *, text="Overview", stop_reason="end_turn", error=None
):
    calls = []

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if error:
                raise _FakeAPIError(error)
            return SimpleNamespace(
                stop_reason=stop_reason,
                content=[
                    SimpleNamespace(type="thinking", thinking=""),
                    SimpleNamespace(type="text", text=text),
                ],
            )

    class _Client:
        def __init__(self, api_key):
            calls.append({"api_key": api_key})
            self.messages = _Messages()

    fake = ModuleType("anthropic")
    fake.Anthropic = _Client
    fake.APIError = _FakeAPIError
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return calls


def test_generate_ai_summary_sends_only_context(monkeypatch) -> None:
    calls = _install_fake_sdk(monkeypatch, text="  Layered design.  ")
    context = {"module_count": 1, "dependencies": []}

    assert generate_ai_summary(context) == "Layered design."
    assert calls[0] == {"api_key": "test-key"}
    request = calls[1]
    assert request["model"] == AI_MODEL
    assert json.loads(request["messages"][0]["content"]) == context


def test_generate_ai_summary_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(AISummaryUnavailable, match="ANTHROPIC_API_KEY"):
        generate_ai_summary({})


def test_generate_ai_summary_requires_sdk(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "anthropic", None)

    with pytest.raises(AISummaryUnavailable, match=r"reporamp\[ai\]"):
        generate_ai_summary({})


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"error": "boom"}, "request failed: boom"),
        ({"stop_reason": "refusal"}, "declined"),
        ({"text": "   "}, "empty"),
    ],
)
def test_generate_ai_summary_failures(monkeypatch, kwargs, match) -> None:
    _install_fake_sdk(monkeypatch, **kwargs)

    with pytest.raises(AISummaryUnavailable, match=match):
        generate_ai_summary({})


def test_context_paths_are_relative_to_root(tmp_path: Path) -> None:
    module = ModuleInfo(
        path=tmp_path / "pkg" / "a.py", imports=(), functions=(), classes=()
    )
    graph = DependencyGraph(modules=("pkg.a",), edges=(), unresolved_imports=())

    context = build_analysis_context([module], graph, root=tmp_path)

    assert context["module_names"] == ["pkg/a.py"]


def test_cli_ai_uses_claude_summary(monkeypatch, tmp_path: Path) -> None:
    _install_fake_sdk(monkeypatch, text="Claude says hello.")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(app, ["analyze", str(tmp_path), "-o", str(out), "--ai"])

    assert result.exit_code == 0, result.output
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "## Architecture Summary\n\nClaude says hello." in report


def test_cli_ai_falls_back_to_local_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "out"

    result = runner.invoke(app, ["analyze", str(tmp_path), "-o", str(out), "--ai"])

    assert result.exit_code == 0, result.output
    assert "AI summary unavailable (ANTHROPIC_API_KEY is not set)" in result.output
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "The repository contains 1 Python modules" in report


def test_cli_without_ai_has_no_summary(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "out"

    runner.invoke(app, ["analyze", str(tmp_path), "-o", str(out)])

    assert "Architecture Summary" not in (out / "report.md").read_text("utf-8")
