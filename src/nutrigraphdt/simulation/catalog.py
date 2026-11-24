"""Lector y validador del catálogo de escenarios (A93-P2, #310).

Lee los archivos JSON de ``configs/scenarios/`` y verifica que su contenido
sea coherente con los identificadores canónicos de DS-04.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.data.synthetic.scenarios import (
    SCENARIO_BASAL_GRAPH_ID,
    SCENARIO_INTERVENED_GRAPH_ID,
)

CATALOG_SCHEMA_VERSION: Final[str] = "1.0.0"
"""Versión del esquema de los archivos de catálogo."""

REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "scenario_id",
    "label",
    "description",
    "is_synthetic",
    "synthetic_data_warning",
    "source",
)


class CatalogError(ValueError):
    """El catálogo de escenarios tiene un error de validación."""


@dataclass(frozen=True)
class ScenarioCatalogEntry:
    """Entrada del catálogo de escenarios.

    Attributes:
        schema_version: Versión del esquema.
        scenario_id: Identificador canónico del escenario.
        label: Nombre corto legible.
        description: Descripción del escenario.
        intervention_variable: Variable intervenida (``None`` para el basal).
        intervention_basal_value: Valor basal (``None`` para el basal).
        intervention_intervened_value: Valor intervenido (``None`` para el basal).
        intervention_unit: Unidad (``None`` para el basal).
        is_synthetic: Siempre ``True``.
        synthetic_data_warning: Advertencia de datos sintéticos.
        source: Módulo generador.
    """

    schema_version: str
    scenario_id: str
    label: str
    description: str
    intervention_variable: str | None
    intervention_basal_value: float | None
    intervention_intervened_value: float | None
    intervention_unit: str | None
    is_synthetic: bool
    synthetic_data_warning: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "label": self.label,
            "description": self.description,
            "intervention_variable": self.intervention_variable,
            "intervention_basal_value": self.intervention_basal_value,
            "intervention_intervened_value": self.intervention_intervened_value,
            "intervention_unit": self.intervention_unit,
            "is_synthetic": self.is_synthetic,
            "synthetic_data_warning": self.synthetic_data_warning,
            "source": self.source,
        }


def _load_entry(path: Path) -> ScenarioCatalogEntry:
    """Lee y valida un archivo de catálogo JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"No se pudo leer el catálogo '{path}': {exc}") from exc

    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise CatalogError(f"Catálogo '{path}' le faltan campos obligatorios: {missing}.")

    if data["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise CatalogError(
            f"Catálogo '{path}' tiene schema_version='{data['schema_version']}'; "
            f"se esperaba '{CATALOG_SCHEMA_VERSION}'."
        )

    if not data["is_synthetic"]:
        raise CatalogError(
            f"Catálogo '{path}' tiene is_synthetic=false; "
            "los escenarios de referencia son siempre sintéticos."
        )

    return ScenarioCatalogEntry(
        schema_version=data["schema_version"],
        scenario_id=data["scenario_id"],
        label=data["label"],
        description=data["description"],
        intervention_variable=data.get("intervention_variable"),
        intervention_basal_value=data.get("intervention_basal_value"),
        intervention_intervened_value=data.get("intervention_intervened_value"),
        intervention_unit=data.get("intervention_unit"),
        is_synthetic=data["is_synthetic"],
        synthetic_data_warning=data["synthetic_data_warning"],
        source=data["source"],
    )


@dataclass(frozen=True)
class ScenarioCatalog:
    """Catálogo versionado de los dos escenarios de referencia.

    Attributes:
        basal: Entrada del escenario basal.
        intervened: Entrada del escenario intervenido.
        catalog_dir: Directorio del catálogo.
    """

    basal: ScenarioCatalogEntry
    intervened: ScenarioCatalogEntry
    catalog_dir: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_dir": str(self.catalog_dir),
            "basal": self.basal.to_dict(),
            "intervened": self.intervened.to_dict(),
        }


def load_scenario_catalog(catalog_dir: str | Path) -> ScenarioCatalog:
    """Lee el catálogo de escenarios de ``catalog_dir``.

    Args:
        catalog_dir: Directorio que contiene ``basal_v1.json`` e
            ``intervened_v1.json``.

    Returns:
        ``ScenarioCatalog`` con las dos entradas validadas.

    Raises:
        CatalogError: Si algún archivo no existe, tiene errores de formato
            o sus identificadores no coinciden con los canónicos de DS-04.
    """
    catalog_dir = Path(catalog_dir)
    basal_path = catalog_dir / "basal_v1.json"
    intervened_path = catalog_dir / "intervened_v1.json"

    for p in (basal_path, intervened_path):
        if not p.exists():
            raise CatalogError(f"Archivo de catálogo no encontrado: {p}")

    basal_entry = _load_entry(basal_path)
    intervened_entry = _load_entry(intervened_path)

    if basal_entry.scenario_id != SCENARIO_BASAL_GRAPH_ID:
        raise CatalogError(
            f"El catálogo basal declara scenario_id='{basal_entry.scenario_id}'; "
            f"se esperaba '{SCENARIO_BASAL_GRAPH_ID}'."
        )
    if intervened_entry.scenario_id != SCENARIO_INTERVENED_GRAPH_ID:
        raise CatalogError(
            f"El catálogo intervenido declara scenario_id='{intervened_entry.scenario_id}'; "
            f"se esperaba '{SCENARIO_INTERVENED_GRAPH_ID}'."
        )

    return ScenarioCatalog(
        basal=basal_entry,
        intervened=intervened_entry,
        catalog_dir=catalog_dir,
    )


__all__ = [
    "CATALOG_SCHEMA_VERSION",
    "REQUIRED_FIELDS",
    "CatalogError",
    "ScenarioCatalog",
    "ScenarioCatalogEntry",
    "load_scenario_catalog",
]
