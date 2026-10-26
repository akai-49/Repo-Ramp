import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from reporamp.cli import app
from reporamp.config import load_config

runner = CliRunner()


def _write_pyproject(root: Path, body: str) -> None:
    (root / "pyproject.toml").write_text(
        f"[project]\nname = 'demo'\n\n[tool.reporamp]\n{body}",
        encoding="utf-8",
    )


def test_missing_pyproject_returns_empty_config(tmp_path: Path) -> None:
    assert load_config(tmp_path) == {}


def test_loads_all_settings(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        'max_deps = 8\nexclude = ["tests"]\nfail_on = ["QR003", "QR002"]\n'
        'format = "json"\n',
    )

    assert load_config(tmp_path) == {
        "max_deps": 8,
        "exclude": ["tests"],
        "fail_on": "QR003,QR002",
        "format": "json",
    }


@pytest.mark.parametrize(
    "body",
    ["max_deps = -1\n", 'exclude = "tests"\n', 'format = "html"\n', "typo = 1\n"],
)
def test_rejects_invalid_settings(tmp_path: Path, body: str) -> None:
    _write_pyproject(tmp_path, body)

    with pytest.raises(ValueError):
        load_config(tmp_path)


def test_cli_uses_config_and_flags_override(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import a\n", encoding="utf-8")
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "c.py").write_text("x = 1\n", encoding="utf-8")
    _write_pyproject(
        tmp_path,
        'exclude = ["skip"]\nfail_on = "cycles"\nformat = "json"\n',
    )
    output_dir = tmp_path / "reports"

    from_config = runner.invoke(app, ["analyze", str(tmp_path), "-o", str(output_dir)])

    assert from_config.exit_code == 2, from_config.output
    assert not (output_dir / "report.md").exists()
    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["summary"]["modules"] == 2

    overridden = runner.invoke(
        app,
        [
            "analyze",
            str(tmp_path),
            "-o",
            str(output_dir),
            "--fail-on",
            "QR002",
            "--format",
            "md",
            "--exclude",
            "nothing",
        ],
    )

    assert overridden.exit_code == 0, overridden.output
    assert "Python modules analyzed: 3" in (output_dir / "report.md").read_text(
        encoding="utf-8"
    )


def test_cli_reports_invalid_config(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, "max_deps = 'many'\n")

    result = runner.invoke(app, ["analyze", str(tmp_path)])

    assert result.exit_code == 1
    assert "max_deps" in result.output
