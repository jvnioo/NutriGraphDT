"""Configuración YAML y fábrica de modelos GNN (A41-8, #84).

Un archivo de `configs/models/` declara la variante (`variant`) y sus hiperparámetros; cambiar
de variante o de valores solo requiere editar el YAML. La validación es de Pydantic v2 con
`extra="forbid"` y modo estricto: una clave desconocida, un tipo incorrecto (por ejemplo, `true`
donde va un entero) o un valor fuera de rango se rechaza con un mensaje que nombra el campo.

Los rangos repiten los de los constructores (`ModelConfig`, `HomoSAGE`, `HeteroSAGE`,
`HeteroGAT`) para fallar al leer el archivo, antes de construir el modelo. Los valores por
defecto son los iniciales del §6 de `docs/models/gnn-architecture.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Final, Literal, TypeAlias

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from nutrigraphdt.models.gnn.base import GraphMetadata, ModelConfig, SCFAGraphModel
from nutrigraphdt.models.gnn.hetero_gat import HeteroGAT
from nutrigraphdt.models.gnn.hetero_sage import HeteroSAGE
from nutrigraphdt.models.gnn.homo_sage import HomoSAGE
from nutrigraphdt.models.gnn.initialization import initialize_lazy_parameters

MODEL_VARIANTS: Final[tuple[str, ...]] = ("homo_sage", "hetero_sage", "hetero_gat")

NeighborAggregation: TypeAlias = Literal["mean", "max", "sum"]
RelationAggregation: TypeAlias = Literal["mean", "sum"]


class ModelConfigError(ValueError):
    """Configuración de modelo inválida; el mensaje indica el origen y los campos."""


class _CommonModelConfig(BaseModel):
    """Hiperparámetros comunes a las tres variantes (`ModelConfig`)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    hidden_channels: int = Field(default=64, ge=1)
    num_layers: int = Field(default=2, ge=1)
    dropout: float = Field(default=0.2, ge=0.0, lt=1.0)

    def common(self) -> ModelConfig:
        """Los hiperparámetros comunes como `ModelConfig`."""
        return ModelConfig(
            hidden_channels=self.hidden_channels,
            num_layers=self.num_layers,
            dropout=self.dropout,
        )


class HomoSAGEConfig(_CommonModelConfig):
    """`homo_sage` (#78): `SAGEConv` compartida sobre el grafo homogéneo."""

    variant: Literal["homo_sage"]
    aggr: NeighborAggregation = "mean"


class HeteroSAGEConfig(_CommonModelConfig):
    """`hetero_sage` (#79): `HeteroConv` con una `SAGEConv` por relación."""

    variant: Literal["hetero_sage"]
    aggr: NeighborAggregation = "mean"
    relation_aggr: RelationAggregation = "sum"


class HeteroGATConfig(_CommonModelConfig):
    """`hetero_gat` (#80): `HeteroConv` con una `GATConv` por relación."""

    variant: Literal["hetero_gat"]
    heads: int = Field(default=4, ge=1)
    concat: bool = True
    relation_aggr: RelationAggregation = "sum"

    @model_validator(mode="after")
    def _heads_divide_hidden(self) -> HeteroGATConfig:
        if self.concat and self.hidden_channels % self.heads != 0:
            raise ValueError(
                f"hidden_channels ({self.hidden_channels}) debe ser divisible por heads "
                f"({self.heads}) cuando concat es true."
            )
        return self


GNNModelConfig: TypeAlias = Annotated[
    HomoSAGEConfig | HeteroSAGEConfig | HeteroGATConfig,
    Field(discriminator="variant"),
]
"""Configuración de cualquier variante; `variant` decide qué campos se admiten."""

_ADAPTER: Final[TypeAdapter[GNNModelConfig]] = TypeAdapter(GNNModelConfig)


def parse_model_config(data: Mapping[str, Any], *, source: str = "configuración") -> GNNModelConfig:
    """Valida un diccionario (por ejemplo, el YAML ya leído) y devuelve la configuración.

    Raises:
        ModelConfigError: si falta `variant`, la variante no existe o algún campo es inválido.
    """
    if not isinstance(data, Mapping):
        raise ModelConfigError(f"{source}: se esperaba un objeto con 'variant'.")
    try:
        return _ADAPTER.validate_python(dict(data))
    except ValidationError as exc:
        raise ModelConfigError(
            f"{source}: configuración de modelo inválida "
            f"(variantes: {', '.join(MODEL_VARIANTS)}).\n{_format_errors(exc)}"
        ) from exc


def load_model_config(path: str | Path) -> GNNModelConfig:
    """Lee y valida un YAML de `configs/models/`.

    Raises:
        ModelConfigError: si el YAML no se puede interpretar o la configuración es inválida.
        FileNotFoundError: si el archivo no existe.
    """
    config_path = Path(path)
    try:
        content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ModelConfigError(f"{config_path}: YAML inválido: {exc}") from exc
    return parse_model_config(content, source=str(config_path))


def build_model(cfg: GNNModelConfig, metadata: GraphMetadata) -> SCFAGraphModel:
    """Instancia la variante de `cfg` para el dataset descrito por `metadata`.

    Devuelve el modelo con las capas perezosas ya inicializadas (`initialize_lazy_parameters`),
    listo para crear el optimizador. Fije la semilla antes de llamar: la inicialización de los
    pesos es aleatoria.
    """
    common = cfg.common()
    model: SCFAGraphModel
    if isinstance(cfg, HomoSAGEConfig):
        model = HomoSAGE(metadata, common, aggr=cfg.aggr)
    elif isinstance(cfg, HeteroSAGEConfig):
        model = HeteroSAGE(metadata, common, aggr=cfg.aggr, relation_aggr=cfg.relation_aggr)
    else:
        model = HeteroGAT(
            metadata,
            common,
            heads=cfg.heads,
            concat=cfg.concat,
            relation_aggr=cfg.relation_aggr,
        )
    initialize_lazy_parameters(model)
    return model


def _format_errors(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(raíz)"
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)


__all__ = [
    "MODEL_VARIANTS",
    "GNNModelConfig",
    "HeteroGATConfig",
    "HeteroSAGEConfig",
    "HomoSAGEConfig",
    "ModelConfigError",
    "build_model",
    "load_model_config",
    "parse_model_config",
]
