"""Load RepoRamp settings from a repository's pyproject.toml."""

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPORT_FORMATS = ("md", "json", "both")
INTEGER_KEYS = ("max_deps", "max_fan_in", "max_module_lines", "max_function_lines")


def _string_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"[tool.reporamp] {key} must be a list of strings")
    return value


def load_config(root: Path) -> dict[str, object]:
    """Return validated ``[tool.reporamp]`` settings, or ``{}`` if absent.

    Supported keys: ``max_deps``, ``max_fan_in``, ``max_module_lines`` and
    ``max_function_lines`` (ints), ``exclude`` (list of globs),
    ``fail_on`` (comma-separated string or list of rule IDs) and
    ``format`` (``md``, ``json`` or ``both``).
    """
    path = Path(root) / "pyproject.toml"

    if not path.is_file():
        return {}

    with path.open("rb") as config_file:
        data = tomllib.load(config_file)

    raw = data.get("tool", {}).get("reporamp", {})
    config: dict[str, object] = {}

    for key, value in raw.items():
        if key in INTEGER_KEYS:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"[tool.reporamp] {key} must be an integer >= 0")
            config[key] = value
        elif key == "exclude":
            config[key] = _string_list(value, key)
        elif key == "fail_on":
            config[key] = (
                value if isinstance(value, str) else ",".join(_string_list(value, key))
            )
        elif key == "format":
            if value not in REPORT_FORMATS:
                choices = ", ".join(REPORT_FORMATS)
                raise ValueError(f"[tool.reporamp] format must be one of: {choices}")
            config[key] = value
        else:
            raise ValueError(f"Unknown [tool.reporamp] setting: {key}")

    return config


def load_entry_points(root: Path) -> frozenset[str]:
    """Return modules named by ``[project.scripts]`` and ``gui-scripts``."""
    path = Path(root) / "pyproject.toml"

    if not path.is_file():
        return frozenset()

    with path.open("rb") as config_file:
        project = tomllib.load(config_file).get("project", {})

    targets = [
        *project.get("scripts", {}).values(),
        *project.get("gui-scripts", {}).values(),
    ]

    return frozenset(target.split(":", 1)[0].strip() for target in targets)
