from pathlib import Path

import pytest

from reporamp.scanner import scan_repository


def test_finds_python_files_recursively(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")

    services = tmp_path / "services"
    services.mkdir()
    (services / "auth.py").write_text("def login(): pass", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result == [Path("app.py"), Path("services/auth.py")]


def test_excludes_generated_and_environment_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    for directory in (".venv", "__pycache__", ".git", "node_modules"):
        excluded = tmp_path / directory
        excluded.mkdir()
        (excluded / "ignored.py").write_text("", encoding="utf-8")

    assert scan_repository(tmp_path) == [Path("app.py")]


def test_ignores_non_python_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")
    (tmp_path / "app.py").write_text("", encoding="utf-8")

    assert scan_repository(tmp_path) == [Path("app.py")]


def test_raises_for_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        scan_repository(missing)


def test_raises_for_file_instead_of_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "app.py"
    file_path.write_text("", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        scan_repository(file_path)


def test_returns_deterministic_order(tmp_path: Path) -> None:
    for filename in ("zebra.py", "alpha.py", "middle.py"):
        (tmp_path / filename).write_text("", encoding="utf-8")

    assert scan_repository(tmp_path) == [
        Path("alpha.py"),
        Path("middle.py"),
        Path("zebra.py"),
    ]
