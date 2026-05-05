"""Architecture guardrails for RF commissioning package imports."""

from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE_ROOT_IMPORT = "sc_linac_physics.applications.rf_commissioning"


def _iter_python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if path.name != "__init__.py"]


def test_rf_commissioning_internals_do_not_import_package_root() -> None:
    """Internal modules should import concrete submodules, not package root.

    Importing through the package root from inside the package increases
    coupling and can create circular-import hazards as exports evolve.
    """
    src_root = Path(__file__).resolve().parents[3] / "src"
    package_root = (
        src_root / "sc_linac_physics" / "applications" / "rf_commissioning"
    )

    violating_imports: list[str] = []
    for file_path in _iter_python_files(package_root):
        module = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != _PACKAGE_ROOT_IMPORT:
                continue

            rel_path = file_path.relative_to(src_root)
            violating_imports.append(
                f"{rel_path}:{node.lineno} imports from package root"
            )

    assert not violating_imports, (
        "Found rf_commissioning internal imports from package root:\n"
        + "\n".join(sorted(violating_imports))
    )
