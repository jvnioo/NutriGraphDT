"""Configuración del entrenamiento GNN y control de semillas (A44-4, #98).

`TrainingConfig` declara los parámetros de una corrida; `configs/training/default.json` tiene los
valores iniciales del §6 de `docs/models/gnn-architecture.md`. La configuración del modelo es
aparte (A41-8, #84). La validación es de Pydantic v2 con `extra="forbid"` y modo estricto.

`set_seed` fija `random`, `numpy` y `torch` y activa los algoritmos deterministas de PyTorch, para
que la misma configuración y la misma semilla repitan los pesos iniciales y el orden de lotes.

`add_override_arguments` y `apply_overrides` permiten sobrescribir los campos del pipeline GNN
clásico desde la línea de comandos; la configuración resultante se vuelve a validar. Las
opciones específicas del pipeline composicional se declaran en su propio script.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from nutrigraphdt.constraints.structural import structural_constraints

MAX_SEED: Final[int] = 2**32 - 1
"""Mayor semilla que acepta `numpy.random.seed`."""

DEVICE_PATTERN: Final[str] = r"^(cpu|cuda(:\d+)?)$"


class TrainingConfigError(ValueError):
    """Configuración de entrenamiento inválida; el mensaje indica el origen y los campos."""


class TrainingConfig(BaseModel):
    """Parámetros de una corrida de entrenamiento.

    `split_file` es relativa a la raíz del repositorio o absoluta, como en `get_split`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    lr: float = Field(gt=0.0, description="Tasa de aprendizaje de Adam.")
    weight_decay: float = Field(ge=0.0, description="Decaimiento de pesos de Adam.")
    batch_size: int = Field(ge=1, description="Grafos por lote.")
    max_epochs: int = Field(ge=1, description="Épocas máximas.")
    patience: int = Field(ge=1, description="Épocas sin mejora en val antes de detener.")
    seed: int = Field(ge=0, le=MAX_SEED, description="Semilla de random, numpy y torch.")
    device: str = Field(default="cpu", pattern=DEVICE_PATTERN)
    dataset_id: str = Field(min_length=1)
    split_file: str = Field(min_length=1, description="Archivo de partición de A40-1.")
    constraint_lambda: float = Field(
        default=0.0, ge=0.0, description="Peso global de la pérdida de restricciones."
    )
    constraint_terms: tuple[str, ...] = Field(
        default=(), description="Nombres de restricciones activas incluidas en la penalización."
    )

    @field_validator("constraint_lambda")
    @classmethod
    def _finite_constraint_lambda(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("constraint_lambda debe ser finito.")
        return value

    @field_validator("constraint_terms", mode="before")
    @classmethod
    def _normalize_constraint_terms(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        raise ValueError("constraint_terms debe ser una lista o tupla de nombres.")

    @model_validator(mode="after")
    def _validate_constraint_terms(self) -> TrainingConfig:
        names = tuple(constraint.metadata.name for constraint in structural_constraints())
        if len(set(self.constraint_terms)) != len(self.constraint_terms):
            raise ValueError("constraint_terms debe contener nombres únicos.")
        unknown = sorted(set(self.constraint_terms) - set(names))
        if unknown:
            raise ValueError(f"constraint_terms contiene restricciones desconocidas: {unknown}.")
        if self.constraint_lambda > 0 and not self.constraint_terms:
            raise ValueError("constraint_lambda > 0 requiere al menos un constraint_term.")
        return self


def parse_training_config(
    data: Mapping[str, Any], *, source: str = "configuración"
) -> TrainingConfig:
    """Valida un diccionario y devuelve la configuración.

    Raises:
        TrainingConfigError: si falta un campo, sobra uno o algún valor es inválido.
    """
    if not isinstance(data, Mapping):
        raise TrainingConfigError(f"{source}: se esperaba un objeto JSON.")
    try:
        return TrainingConfig.model_validate(dict(data))
    except ValidationError as exc:
        raise TrainingConfigError(
            f"{source}: configuración de entrenamiento inválida.\n{_format_errors(exc)}"
        ) from exc


def load_training_config(path: str | Path) -> TrainingConfig:
    """Lee y valida un JSON de `configs/training/`.

    Raises:
        TrainingConfigError: si el JSON no se puede interpretar o la configuración es inválida.
        FileNotFoundError: si el archivo no existe.
    """
    config_path = Path(path)
    try:
        content = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrainingConfigError(f"{config_path}: JSON inválido: {exc}") from exc
    return parse_training_config(content, source=str(config_path))


_OVERRIDE_TYPES: Final[dict[str, type]] = {
    "lr": float,
    "weight_decay": float,
    "batch_size": int,
    "max_epochs": int,
    "patience": int,
    "seed": int,
    "device": str,
    "dataset_id": str,
    "split_file": str,
}


def add_override_arguments(parser: argparse.ArgumentParser) -> None:
    """Agrega los argumentos de override del pipeline GNN clásico a `parser`.

    Un argumento omitido vale `None` y no sobrescribe el archivo. Los campos específicos del
    pipeline composicional no se exponen aquí.
    """
    group = parser.add_argument_group("sobrescritura de la configuración de entrenamiento")
    for name, value_type in _OVERRIDE_TYPES.items():
        group.add_argument(
            f"--{name.replace('_', '-')}",
            dest=name,
            type=value_type,
            default=None,
            help=TrainingConfig.model_fields[name].description,
        )


def overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Valores pasados explícitamente por línea de comandos (los que no son `None`)."""
    return {
        name: getattr(args, name)
        for name in _OVERRIDE_TYPES
        if getattr(args, name, None) is not None
    }


def apply_overrides(config: TrainingConfig, overrides: Mapping[str, Any]) -> TrainingConfig:
    """Nueva configuración con `overrides` aplicados y validados como en el archivo.

    Raises:
        TrainingConfigError: si un valor sobrescrito es inválido o el campo no existe.
    """
    if not overrides:
        return config
    return parse_training_config(
        {**config.model_dump(), **overrides}, source="sobrescritura por línea de comandos"
    )


def set_seed(seed: int) -> None:
    """Fija `random`, `numpy` y `torch` y activa los algoritmos deterministas de PyTorch.

    `torch.use_deterministic_algorithms(True)` hace que una operación sin implementación
    determinista lance un error en lugar de dar resultados distintos entre corridas. El estado
    es global del proceso.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed debe ser un entero en [0, {MAX_SEED}]; se recibió {seed!r}.")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(raíz)"
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)


__all__ = [
    "MAX_SEED",
    "TrainingConfig",
    "TrainingConfigError",
    "add_override_arguments",
    "apply_overrides",
    "load_training_config",
    "overrides_from_args",
    "parse_training_config",
    "set_seed",
]
