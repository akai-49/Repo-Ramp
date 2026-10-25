from reporamp import __version__


def test_package_has_expected_initial_version() -> None:
    assert __version__ == "0.1.0"
