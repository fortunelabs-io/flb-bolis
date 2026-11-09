"""Tests that the host package stays offline (specification section 7)."""

import ast
from pathlib import Path

import bolis

FORBIDDEN_TOP_LEVEL_MODULES = frozenset({"socket", "urllib", "http", "requests"})


def _top_level_imports(source: str) -> set[str]:
    """Collects the top-level module name of every import in a source file.

    Args:
        source: The text of one Python source file.

    Returns:
        The set of top-level module names that the file imports, such as
        {"os", "bolis"} for "import os" and "from bolis.cli import main".
    """
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.level == 0
        ):
            names.add(node.module.split(".")[0])
    return names


def test_package_imports_no_networking_module() -> None:
    """No module of the host package imports socket, urllib, http, or requests."""
    package_dir = Path(bolis.__file__).parent
    for path in package_dir.rglob("*.py"):
        imported = _top_level_imports(path.read_text(encoding="utf-8"))
        forbidden = imported & FORBIDDEN_TOP_LEVEL_MODULES
        message = f"{path} imports {sorted(forbidden)}, which reaches the network."
        assert not forbidden, message
