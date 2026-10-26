from pathlib import Path

from reporamp import __version__


def test_package_has_expected_initial_version() -> None:
    assert __version__ == "0.1.0"


def test_license_file_exists() -> None:
    license_file = Path(__file__).resolve().parents[1] / "LICENSE"
    assert license_file.read_text(encoding="utf-8").startswith("MIT License")
