import json
from pathlib import Path

from typer.testing import CliRunner

from reporamp.cli import app

runner = CliRunner()


def test_analyze_generates_reports(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "def main():\n    return 42\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "reports"

    result = runner.invoke(
        app,
        ["analyze", str(tmp_path), "--output", str(output_dir)],
    )

    assert result.exit_code == 0, result.output
    assert "Analysis completed successfully." in result.output
    assert (output_dir / "report.md").is_file()
    assert (output_dir / "report.json").is_file()

    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["summary"]["modules"] == 1


def test_analyze_rejects_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    result = runner.invoke(app, ["analyze", str(missing)])

    assert result.exit_code != 0


def test_help_is_available() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "analyze" in result.output


def test_analyze_continues_past_invalid_python(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def invalid(:\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = runner.invoke(app, ["analyze", str(tmp_path), "-o", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert "Could not parse broken.py" in result.output
    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["summary"]["modules"] == 1
    assert payload["summary"]["parse_errors"] == 1
    assert payload["parse_errors"][0]["path"] == "broken.py"
    markdown = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "## Parse Errors" in markdown
    assert "`broken.py`" in markdown


def test_analyze_strict_fails_on_invalid_python(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def invalid(:\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["analyze", str(tmp_path), "-o", str(tmp_path / "out"), "--strict"],
    )

    assert result.exit_code == 1
    assert "Could not parse broken.py" in result.output
    assert (tmp_path / "out" / "report.json").is_file()


def _write_hub(root: Path, dependency_count: int) -> None:
    names = [f"m{index}" for index in range(dependency_count)]
    for name in names:
        (root / f"{name}.py").write_text("x = 1\n", encoding="utf-8")
    (root / "hub.py").write_text(
        "".join(f"import {name}\n" for name in names),
        encoding="utf-8",
    )


def test_analyze_max_deps_controls_qr002(tmp_path: Path) -> None:
    _write_hub(tmp_path, 3)
    output_dir = tmp_path / "reports"

    default = runner.invoke(app, ["analyze", str(tmp_path), "-o", str(output_dir)])
    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert default.exit_code == 0, default.output
    assert payload["quality_findings"] == []

    strict = runner.invoke(
        app,
        ["analyze", str(tmp_path), "-o", str(output_dir), "--max-deps", "2"],
    )
    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert strict.exit_code == 0, strict.output
    assert [item["rule_id"] for item in payload["quality_findings"]] == ["QR002"]


def test_analyze_exclude_and_format(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "legacy").mkdir()
    (tmp_path / "legacy" / "old.py").write_text("def broken(:\n", encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = runner.invoke(
        app,
        [
            "analyze",
            str(tmp_path),
            "-o",
            str(output_dir),
            "--exclude",
            "legacy",
            "--exclude",
            "nothing*",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (output_dir / "report.md").exists()
    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["summary"]["modules"] == 1
    assert payload["summary"]["parse_errors"] == 0


def test_analyze_rejects_unknown_format(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path), "--format", "html"])

    assert result.exit_code != 0


def _write_cycle(root: Path) -> None:
    (root / "a.py").write_text("import b\n", encoding="utf-8")
    (root / "b.py").write_text("import a\n", encoding="utf-8")


def test_fail_on_exits_2_for_matching_findings(tmp_path: Path) -> None:
    _write_cycle(tmp_path)
    output_dir = tmp_path / "reports"

    result = runner.invoke(
        app,
        ["analyze", str(tmp_path), "-o", str(output_dir), "--fail-on", "cycles"],
    )

    assert result.exit_code == 2, result.output
    assert "[QR003]" in result.output
    assert (output_dir / "report.json").is_file()


def test_fail_on_passes_without_matching_findings(tmp_path: Path) -> None:
    _write_cycle(tmp_path)

    result = runner.invoke(
        app,
        ["analyze", str(tmp_path), "-o", str(tmp_path / "r"), "--fail-on", "QR002"],
    )

    assert result.exit_code == 0, result.output


def test_fail_on_rejects_unknown_rule(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path), "--fail-on", "QR9"])

    assert result.exit_code == 2
    assert "Unknown rule" in result.output
