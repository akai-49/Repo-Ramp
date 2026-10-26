from pathlib import Path

import pytest

from reporamp.parser import parse_python_file


def test_extracts_imports_functions_and_classes(tmp_path: Path) -> None:
    source = """
import os as operating_system
from pathlib import Path
from services.auth import login as authenticate

class UserService(BaseService):
    def get_user(self, user_id: int) -> str:
        return str(user_id)

def main():
    authenticate()
"""
    file_path = tmp_path / "app.py"
    file_path.write_text(source, encoding="utf-8")

    result = parse_python_file(file_path)

    assert result.path == file_path
    assert [item.module for item in result.imports] == [
        "os",
        "pathlib",
        "services.auth",
    ]
    assert result.imports[0].alias == "operating_system"
    assert result.imports[2].name == "login"
    assert result.imports[2].alias == "authenticate"

    assert [item.name for item in result.classes] == ["UserService"]
    assert result.classes[0].bases == ("BaseService",)

    assert [item.name for item in result.functions] == [
        "get_user",
        "main",
    ]
    assert result.functions[0].parent_class == "UserService"
    assert result.functions[1].parent_class is None


def test_extracts_async_functions(tmp_path: Path) -> None:
    file_path = tmp_path / "async_app.py"
    file_path.write_text(
        "async def fetch_data():\n    return 42\n",
        encoding="utf-8",
    )

    result = parse_python_file(file_path)

    assert len(result.functions) == 1
    assert result.functions[0].name == "fetch_data"
    assert result.functions[0].is_async is True


def test_extracts_relative_imports(tmp_path: Path) -> None:
    file_path = tmp_path / "module.py"
    file_path.write_text(
        "from ..services import auth\n",
        encoding="utf-8",
    )

    result = parse_python_file(file_path)

    assert result.imports[0].module == "services"
    assert result.imports[0].level == 2


def test_reports_syntax_errors(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.py"
    file_path.write_text("def broken(:\n    pass\n", encoding="utf-8")

    with pytest.raises(SyntaxError):
        parse_python_file(file_path)


def test_missing_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_python_file(tmp_path / "missing.py")


def test_does_not_execute_source_code(tmp_path: Path) -> None:
    marker = tmp_path / "should_not_exist.txt"
    file_path = tmp_path / "unsafe.py"

    file_path.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )

    parse_python_file(file_path)

    assert not marker.exists()


def test_reports_source_line_numbers(tmp_path: Path) -> None:
    file_path = tmp_path / "locations.py"
    file_path.write_text(
        "import os\n\nclass Example:\n    def method(self):\n        pass\n",
        encoding="utf-8",
    )

    result = parse_python_file(file_path)

    assert result.imports[0].line_number == 1
    assert result.classes[0].line_number == 3
    assert result.classes[0].end_line_number == 5
    assert result.functions[0].line_number == 4
    assert result.functions[0].end_line_number == 5
