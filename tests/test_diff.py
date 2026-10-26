import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from reporamp.cli import app
from reporamp.diff import diff_reports, has_new_problems, load_report, render_diff

runner = CliRunner()


def _analyze(root: Path, output: Path) -> Path:
    result = runner.invoke(app, ["analyze", str(root), "-o", str(output)])
    assert result.exit_code == 0, result.output
    return output / "report.json"


def test_diff_detects_changes_between_reports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("import b\n", encoding="utf-8")
    (repo / "b.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "old.py").write_text("import a\n", encoding="utf-8")
    base = _analyze(repo, tmp_path / "base")

    (repo / "old.py").unlink()
    (repo / "b.py").write_text("import a\n", encoding="utf-8")
    head = _analyze(repo, tmp_path / "head")

    changes = diff_reports(load_report(base), load_report(head))

    assert changes["modules"] == {"added": [], "removed": ["old.py"]}
    assert changes["dependencies"] == {
        "added": [("b", "a")],
        "removed": [("old", "a")],
    }
    assert changes["cycles"] == {"added": [("a", "b")], "removed": []}
    assert ("QR003", "a", "Circular dependency detected: a -> b -> a") in changes[
        "findings"
    ]["added"]
    assert has_new_problems(changes)
    assert not has_new_problems(diff_reports(load_report(head), load_report(head)))

    markdown = render_diff(changes)
    assert "## New cycles (1)" in markdown
    assert "- a → b → a" in markdown
    assert "## Removed modules (1)" in markdown

    plain = runner.invoke(app, ["diff", str(base), str(head)])
    assert plain.exit_code == 0, plain.output
    assert "## New cycles (1)" in plain.output

    gated = runner.invoke(app, ["diff", str(base), str(head), "--fail-on-new"])
    assert gated.exit_code == 2

    same = runner.invoke(app, ["diff", str(head), str(head), "--fail-on-new"])
    assert same.exit_code == 0

    reverse = runner.invoke(app, ["diff", str(head), str(base)])
    assert "## Resolved cycles (1)" in reverse.output


def test_load_report_accepts_schema_v1(tmp_path: Path) -> None:
    path = tmp_path / "v1.json"
    path.write_text(json.dumps({"schema_version": 1, "modules": []}), "utf-8")

    assert load_report(path)["schema_version"] == 1


@pytest.mark.parametrize("payload", [{"schema_version": 99}, {}, []])
def test_load_report_rejects_unknown_schema(tmp_path: Path, payload) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), "utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        load_report(path)

    result = runner.invoke(app, ["diff", str(path), str(path)])
    assert result.exit_code == 1
