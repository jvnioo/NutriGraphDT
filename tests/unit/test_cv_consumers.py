"""Los consumidores de D1 usan una sola asignación de folds (A65-P3, #172).

La evaluación oficial de D1 es la validación cruzada por corral del plan versionado
`configs/splits/d1_holofood_cv.json` (decisión del sublíder de Desarrollo del 01-11-2026; ver
`docs/models/cross-validation.md`). Estas pruebas leen el código de los scripts, sin datos: solo
`create_cv_folds.py` genera folds, y los consumidores leen el mismo plan y lo verifican contra su
cohorte antes de evaluar.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
CONSUMERS = ("compare_baselines_d1_composition.py", "evaluate_gnn_d1_composition.py")


def _called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_only_create_cv_folds_generates_folds() -> None:
    generators = sorted(
        path.name
        for path in [*SCRIPTS.glob("*.py"), *(REPO_ROOT / "src").rglob("*.py")]
        if "make_pen_folds" in _called_names(path)
    )
    assert generators == ["create_cv_folds.py"]


@pytest.mark.parametrize("script", CONSUMERS)
def test_consumers_read_and_verify_the_versioned_plan(script: str) -> None:
    path = SCRIPTS / script
    source = path.read_text(encoding="utf-8")
    assert 'REPO_ROOT / "configs" / "splits" / "d1_holofood_cv.json"' in source
    assert {"load", "verify_plan"} <= _called_names(path)
