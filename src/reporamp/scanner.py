
"""Discover Python source files in a repository."""

import os
from collections.abc import Iterable
from fnmatch import fnmatch
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


def _is_excluded(relative_path: Path, patterns: Iterable[str]) -> bool:
    """Match a glob against the file or directory name or its relative path."""
    return any(
        fnmatch(relative_path.name, pattern)
        or fnmatch(relative_path.as_posix(), pattern)
        for pattern in patterns
    )


def scan_repository(root: Path, exclude: Iterable[str] = ()) -> list[Path]:
    """Return sorted Python file paths relative to the repository root.

    Directory symlinks are not followed. Generated and environment
    directories are excluded by name. Extra ``exclude`` glob patterns are
    matched against each file or directory name and its root-relative path.
    """
    exclude = tuple(exclude)
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
            and not _is_excluded((current_path / name).relative_to(root), exclude)
        )

        for filename in filenames:
            if filename.endswith(".py"):
                relative_path = (current_path / filename).relative_to(root)
                if not _is_excluded(relative_path, exclude):
                    python_files.append(relative_path)

    return sorted(python_files, key=lambda path: path.as_posix())
