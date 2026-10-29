"""Pruebas de verificación de la auditoría y revisión de explicabilidad (A60-P5, #167).

Comprueba que el documento de revisión existe, que todos los PRs y actividades de A60
están catalogados, que los criterios de aceptación están formalmente verificados y que
el documento está enlazado en el índice general de la documentación.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_MODELS = REPO_ROOT / "docs" / "models"
REVIEW_DOC = DOCS_MODELS / "explainability-pr-cross-review.md"
INDEX_DOC = REPO_ROOT / "docs" / "README.md"


def test_review_document_exists() -> None:
    """Verifica que el informe de revisión A60-P5 existe y no está vacío."""
    assert REVIEW_DOC.exists(), f"No se encontró el documento de revisión en {REVIEW_DOC}"
    content = REVIEW_DOC.read_text(encoding="utf-8")
    assert len(content) > 1000, "El documento de revisión es demasiado corto o está incompleto"


def test_review_contains_all_a60_activities() -> None:
    """Verifica que las 5 actividades (A60-P1 a A60-P5) y sus issues estén inventariadas."""
    content = REVIEW_DOC.read_text(encoding="utf-8")
    for act in ("A60-P1", "A60-P2", "A60-P3", "A60-P4", "A60-P5"):
        assert act in content, f"Actividad {act} no mencionada en la revisión"

    for issue_id in ("#170", "#171", "#169", "#168", "#167"):
        assert issue_id in content, f"Issue {issue_id} no trazado en la revisión"


def test_review_verifies_all_acceptance_criteria() -> None:
    """Verifica que la matriz de criterios (CR-01 a CR-11) esté completa y cumplida."""
    content = REVIEW_DOC.read_text(encoding="utf-8")
    for i in range(1, 12):
        crit_id = f"CR-{i:02d}"
        assert crit_id in content, f"Criterio {crit_id} ausente en la matriz de verificación"

    # Verificar que no quedan criterios pendientes
    assert "Cumplido" in content
    assert "Pendiente" not in content


def test_review_is_linked_in_docs_readme() -> None:
    """Verifica que el informe esté correctamente indexado en docs/README.md."""
    index_content = INDEX_DOC.read_text(encoding="utf-8")
    assert "models/explainability-pr-cross-review.md" in index_content, (
        "El documento de revisión no está enlazado en docs/README.md"
    )
