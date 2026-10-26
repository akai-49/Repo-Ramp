
"""Discover Python source files in a repository."""

import os
from pathlib import Path

EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "site-packages",
        "node_modules",
        "build",
        "dist",
    }
)


def scan_repository(root: Path) -> list[Path]:
    """Return sorted Python file paths relative to the repository root.

    Directory symlinks are not followed. Generated and environment
    directories are excluded by name.
    """
    root = Path(root).expanduser()

    if not root.exists():
        raise FileNotFoundError(f"Repository directory not found: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Repository root is not a directory: {root}")

    root = root.resolve()
    python_files: list[Path] = []

    for current_directory, directory_names, filenames in os.walk(
        root,
        followlinks=False,
    ):
        current_path = Path(current_directory)

        # Do not descend into excluded directories or directory symlinks.
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in EXCLUDED_DIRECTORIES
            and not (current_path / name).is_symlink()
        )

        for filename in filenames:
            if filename.endswith(".py"):
                full_path = current_path / filename
                python_files.append(full_path.relative_to(root))

    return sorted(python_files, key=lambda path: path.as_posix())
