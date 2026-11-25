"""Corrida activa de la Web App y sus metadatos (A88-P3, #300), sin Streamlit.

La corrida que usan las páginas se elige por configuración: `configs/platform.json` (clave
`run`) o, si está definida, la variable de entorno `NUTRIGRAPHDT_RUN`. Debe ser una corrida de
`nutrigraphdt.api.DEMO_RUNS`. Las páginas no escriben rutas: piden la corrida activa.

`run_metadata` lee `run.json` y `metrics.csv` de la corrida sin cargar el modelo ni PyTorch, para
que el pie de página y la página de inicio no esperen al motor.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Final

from nutrigraphdt.api.contract import API_CONTRACT_VERSION

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
PLATFORM_CONFIG: Final[Path] = REPO_ROOT / "configs" / "platform.json"
RUN_ENV: Final[str] = "NUTRIGRAPHDT_RUN"


class PlatformConfigError(ValueError):
    """La corrida configurada no existe en `DEMO_RUNS`."""


def active_run_name(config: str | Path = PLATFORM_CONFIG) -> str:
    """Nombre de la corrida activa: `NUTRIGRAPHDT_RUN` o la clave `run` de la configuración.

    Raises:
        PlatformConfigError: si la corrida no está en `DEMO_RUNS`.
    """
    from nutrigraphdt.api.demo import DEMO_RUNS

    name = os.environ.get(RUN_ENV) or json.loads(Path(config).read_text(encoding="utf-8"))["run"]
    if name not in DEMO_RUNS:
        raise PlatformConfigError(
            f"La corrida configurada {name!r} no existe; las disponibles son {sorted(DEMO_RUNS)}."
        )
    return str(name)


def run_metadata(name: str) -> dict[str, Any]:
    """Metadatos de la corrida `name` para la interfaz, sin cargar el modelo.

    Devuelve el nombre, rótulo, si es sintética, `run_id`, variante, `dataset_id`, semilla,
    fold, commit, animales por partición, versión del contrato y las métricas de test.
    """
    from nutrigraphdt.api.demo import DEMO_RUNS

    run = DEMO_RUNS[name]
    info = json.loads((run.run_dir / "run.json").read_text(encoding="utf-8"))
    metrics_path = run.run_dir / "metrics.csv"
    metrics: list[dict[str, str]] = []
    if metrics_path.exists():
        with metrics_path.open(encoding="utf-8", newline="") as handle:
            metrics = list(csv.DictReader(handle))
    return {
        "name": run.name,
        "label": run.label,
        "description": run.description,
        "is_synthetic": run.is_synthetic,
        "run_id": info["run_id"],
        "variant": info["variant"],
        "edges_arm": info["edges_arm"],
        "dataset_id": info["dataset_id"],
        "seed": info["seed"],
        "fold": info["fold"],
        "commit": (info.get("git") or {}).get("commit"),
        "n_animals": {split: len(ids) for split, ids in info["sample_ids"].items()},
        "contract_version": API_CONTRACT_VERSION,
        "metrics": metrics,
    }


__all__ = [
    "PLATFORM_CONFIG",
    "RUN_ENV",
    "PlatformConfigError",
    "active_run_name",
    "run_metadata",
]
