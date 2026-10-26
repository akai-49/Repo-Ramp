import asyncio
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from reporamp.cli import app
from reporamp.mcp_server import (
    TOOLS,
    analyze_repo,
    get_cycles,
    get_findings,
    who_imports,
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import a\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("import a\n", encoding="utf-8")
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    return tmp_path


def test_analyze_repo_returns_json_report(repo: Path) -> None:
    report = analyze_repo(str(repo))

    assert report["schema_version"] == 2
    assert report["summary"]["modules"] == 4
    assert report["modules"][0]["path"] == "a.py"


def test_get_cycles(repo: Path) -> None:
    assert get_cycles(str(repo)) == [["a", "b"]]


def test_who_imports(repo: Path) -> None:
    assert who_imports(str(repo), "a") == ["b", "c"]
    assert who_imports(str(repo), "c") == []

    with pytest.raises(ValueError, match="Unknown module"):
        who_imports(str(repo), "missing")


def test_get_findings(repo: Path) -> None:
    all_rules = {item["rule_id"] for item in get_findings(str(repo))}
    cycles = get_findings(str(repo), "QR003")

    assert {"QR001", "QR003"} <= all_rules
    assert [item["module"] for item in cycles] == ["a"]
    assert get_findings(str(repo), "cycles") == cycles

    with pytest.raises(ValueError):
        get_findings(str(repo), "QR999")


def test_tools_reject_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        get_cycles(str(tmp_path / "missing"))


def test_tools_respect_pyproject_config(repo: Path) -> None:
    (repo / "pyproject.toml").write_text(
        '[tool.reporamp]\nexclude = ["c.py"]\n', encoding="utf-8"
    )

    assert who_imports(str(repo), "a") == ["b"]


def test_server_registers_tools() -> None:
    pytest.importorskip("mcp")
    from reporamp.mcp_server import create_server

    tools = asyncio.run(create_server().list_tools())

    assert sorted(tool.name for tool in tools) == sorted(t.__name__ for t in TOOLS)


def test_cli_mcp_reports_missing_extra(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.setitem(sys.modules, "mcp.server", None)
    monkeypatch.setitem(sys.modules, "mcp.server.mcpserver", None)

    result = CliRunner().invoke(app, ["mcp"])

    assert result.exit_code == 1
    assert "reporamp[mcp]" in result.output
