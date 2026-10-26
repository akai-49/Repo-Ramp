import ast
import shlex
from pathlib import Path

from typer.testing import CliRunner

from reporamp.cli import app

REPO_ROOT = Path(__file__).resolve().parents[1]


def _hook_value(key: str) -> str:
    text = (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    prefix = f"  {key}: "
    lines = text.splitlines()
    return next(line[len(prefix) :] for line in lines if line.startswith(prefix))


def test_pre_commit_hook_command_fails_on_cycles(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import a\n", encoding="utf-8")
    command = shlex.split(_hook_value("entry")) + ast.literal_eval(_hook_value("args"))
    assert command[0] == "reporamp"
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, command[1:])

    assert result.exit_code == 2, result.output
    assert (tmp_path / ".reporamp-report" / "report.json").is_file()


def test_action_runs_reporamp_with_fail_on() -> None:
    action = (REPO_ROOT / "action.yml").read_text(encoding="utf-8")

    assert "using: composite" in action
    assert 'reporamp analyze "$REPORAMP_PATH"' in action
    assert '--fail-on "$REPORAMP_FAIL_ON"' in action
