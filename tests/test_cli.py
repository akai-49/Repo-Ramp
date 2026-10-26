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
