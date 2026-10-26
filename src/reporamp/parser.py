"""Parse Python source files into structured metadata."""

import ast
import tokenize
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImportInfo:
    """Represent a single imported module or symbol."""

    module: str | None
    name: str | None
    alias: str | None
    level: int
    line_number: int


@dataclass(frozen=True)
class FunctionInfo:
    """Represent a function or method definition."""

    name: str
    line_number: int
    end_line_number: int
    is_async: bool
    parent_class: str | None


@dataclass(frozen=True)
class ClassInfo:
    """Represent a class definition."""

    name: str
    line_number: int
    end_line_number: int
    bases: tuple[str, ...]


@dataclass(frozen=True)
class ModuleInfo:
    """Store structural information extracted from a Python file."""

    path: Path
    imports: tuple[ImportInfo, ...]
    functions: tuple[FunctionInfo, ...]
    classes: tuple[ClassInfo, ...]


def _expression_name(node: ast.expr) -> str:
    """Return a readable name for an AST expression."""
    try:
        return ast.unparse(node)
    except (ValueError, TypeError):
        return "<unknown>"


class _ModuleVisitor(ast.NodeVisitor):
    """Collect imports, top-level functions, classes, and methods."""

    def __init__(self) -> None:
        self.imports: list[ImportInfo] = []
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self._class_stack: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    module=alias.name,
                    name=None,
                    alias=alias.asname,
                    level=0,
                    line_number=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    module=node.module,
                    name=alias.name,
                    alias=alias.asname,
                    level=node.level,
                    line_number=node.lineno,
                )
            )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(
            ClassInfo(
                name=node.name,
                line_number=node.lineno,
                end_line_number=node.end_lineno or node.lineno,
                bases=tuple(_expression_name(base) for base in node.bases),
            )
        )

        self._class_stack.append(node.name)
        try:
            self.generic_visit(node)
        finally:
            self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node, is_async=True)

    def _record_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        is_async: bool,
    ) -> None:
        self.functions.append(
            FunctionInfo(
                name=node.name,
                line_number=node.lineno,
                end_line_number=node.end_lineno or node.lineno,
                is_async=is_async,
                parent_class=self._class_stack[-1] if self._class_stack else None,
            )
        )

        # Also discover nested functions and classes.
        self.generic_visit(node)


def parse_python_file(path: Path) -> ModuleInfo:
    """Parse a Python file without executing it.

    Args:
        path: Path to an existing Python source file.

    Returns:
        Structured imports, functions, and class definitions.

    Raises:
        FileNotFoundError: If the path does not exist.
        IsADirectoryError: If the path points to a directory.
        SyntaxError: If the source contains invalid Python syntax.
        UnicodeError: If the source cannot be decoded.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Python file not found: {path}")

    if path.is_dir():
        raise IsADirectoryError(f"Expected a Python file, got directory: {path}")

    with tokenize.open(path) as source_file:
        source = source_file.read()

    syntax_tree = ast.parse(source, filename=str(path))

    visitor = _ModuleVisitor()
    visitor.visit(syntax_tree)

    return ModuleInfo(
        path=path,
        imports=tuple(visitor.imports),
        functions=tuple(visitor.functions),
        classes=tuple(visitor.classes),
    )
