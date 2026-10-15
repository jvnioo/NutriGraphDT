"""Escalado de features y targets ajustado exclusivamente con train (A44-2, #96).

Estandariza los atributos nodales `x` por tipo de nodo y los AGCC a nivel de grafo
usando únicamente las estadísticas del subconjunto de entrenamiento (`train`), según
el §6.2 del diseño GNN (`docs/models/gnn-architecture.md`):

- `FeatureScaler`: Estandariza `x` por tipo de nodo y columna ignorando celdas con
  `missing_mask = True`. Tras escalar, las celdas ausentes quedan en `0.0` y conservan
  su `missing_mask` booleana. Transforma sobre copias sin modificar los grafos originales.
- `TargetScaler`: Estandariza los AGCC (`y_graph`) sobre las muestras de `train` con valor
  medido (`y_graph_mask = True`), con métodos `transform` e `inverse_transform`.

Ambos escaladores:
1. Manejan columnas constantes (desviación 0) y tipos con `F_t = 0` sin dividir por cero.
2. Se serializan a diccionarios compatibles con JSON para guardarse en la corrida (A44-5)
   y reconstruirse fielmente desde ese diccionario.
"""

from __future__ import annotations

import json
import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor
from torch_geometric.data import HeteroData

from nutrigraphdt.models.gnn.target import add_graph_target
from nutrigraphdt.models.metrics import DEFAULT_SCFA_TARGETS


@dataclass(frozen=True)
class NodeFeatureStats:
    """Estadísticas de estandarización para un tipo de nodo.

    Attributes
    ----------
    node_type : str
        Nombre del tipo de nodo (p. ej. 'host', 'taxon').
    num_features : int
        Número de columnas de feature (F_t).
    mean : tuple[float, ...]
        Media por columna sobre las celdas observadas de train.
    std : tuple[float, ...]
        Desviación estándar por columna (o 1.0 si la desviación es 0).
    observed_count : tuple[int, ...]
        Cantidad de celdas observadas (missing_mask = False) en train por columna.
    """

    node_type: str
    num_features: int
    mean: tuple[float, ...]
    std: tuple[float, ...]
    observed_count: tuple[int, ...]


class FeatureScaler:
    """Estandarizador de atributos nodales `x` ajustado exclusivamente con `train`.

    Calcula la media y desviación estándar por columna para cada tipo de nodo presente
    en los grafos de entrenamiento, ignorando las celdas con `missing_mask = True`.
    Aplica la transformación sobre copias profundas de los grafos para preservar los
    originales. Las celdas ausentes se fijan en `0.0` y conservan su máscara booleana.
    """

    def __init__(self, stats: Mapping[str, NodeFeatureStats] | None = None) -> None:
        self._stats: dict[str, NodeFeatureStats] = dict(stats) if stats is not None else {}
        self._is_fitted: bool = stats is not None

    @property
    def is_fitted(self) -> bool:
        """Indica si el escalador ya fue ajustado con estadísticas de train."""
        return self._is_fitted

    @property
    def stats(self) -> dict[str, NodeFeatureStats]:
        """Copia de las estadísticas de estandarización por tipo de nodo."""
        return dict(self._stats)

    @classmethod
    def fit(cls, train_graphs: Sequence[HeteroData]) -> FeatureScaler:
        """Ajusta un nuevo `FeatureScaler` sobre los grafos de entrenamiento.

        Parameters
        ----------
        train_graphs : Sequence[HeteroData]
            Grafos pertenecientes exclusivamente a la partición de entrenamiento.

        Returns
        -------
        FeatureScaler
            Instancia ajustada.
        """
        scaler = cls()
        return scaler.fit_graphs(train_graphs)

    def fit_graphs(self, train_graphs: Sequence[HeteroData]) -> FeatureScaler:
        """Calcula medias y desviaciones estándar por columna de `x` sobre `train_graphs`.

        Parameters
        ----------
        train_graphs : Sequence[HeteroData]
            Grafos pertenecientes exclusivamente a la partición de entrenamiento.

        Returns
        -------
        FeatureScaler
            La misma instancia ajustada.

        Raises
        ------
        ValueError
            Si `train_graphs` está vacío.
        """
        if not train_graphs:
            raise ValueError("train_graphs no puede estar vacío para ajustar FeatureScaler.")

        node_types = sorted({nt for g in train_graphs for nt in g.node_types})
        stats_by_type: dict[str, NodeFeatureStats] = {}

        for node_type in node_types:
            stores = [g[node_type] for g in train_graphs if node_type in g.node_types]
            stores_with_x = [s for s in stores if "x" in s and s.x is not None]

            if not stores_with_x:
                continue

            num_features = stores_with_x[0].x.size(1)
            # Manejo de F_t = 0 (tipos sin atributos numéricos, p. ej. diet en D1)
            if num_features == 0:
                stats_by_type[node_type] = NodeFeatureStats(
                    node_type=node_type,
                    num_features=0,
                    mean=(),
                    std=(),
                    observed_count=(),
                )
                continue

            # Validar consistencia de dimensiones entre grafos
            for store in stores_with_x:
                if store.x.size(1) != num_features:
                    raise ValueError(
                        f"Dimensión inconsistente de x para '{node_type}': "
                        f"se esperaba {num_features}, se encontró {store.x.size(1)}."
                    )

            x_tensors: list[Tensor] = []
            mask_tensors: list[Tensor] = []

            for store in stores_with_x:
                x = store.x.detach().to(torch.float32)
                if "missing_mask" in store and store.missing_mask is not None:
                    mask = store.missing_mask.detach()
                    if mask.shape != x.shape:
                        raise ValueError(
                            f"missing_mask de '{node_type}' tiene forma {list(mask.shape)}, "
                            f"distinta de x {list(x.shape)}."
                        )
                else:
                    mask = torch.zeros_like(x, dtype=torch.bool)
                x_tensors.append(x)
                mask_tensors.append(mask)

            x_all = torch.cat(x_tensors, dim=0) if x_tensors else torch.empty((0, num_features))
            mask_all = (
                torch.cat(mask_tensors, dim=0)
                if mask_tensors
                else torch.empty((0, num_features), dtype=torch.bool)
            )

            observed = ~mask_all
            observed_counts = observed.sum(dim=0)

            means: list[float] = []
            stds: list[float] = []
            counts: list[int] = []

            for col in range(num_features):
                count_col = int(observed_counts[col].item())
                counts.append(count_col)

                if count_col == 0:
                    # Sin datos observados: neutralizar a media 0 y desviación 1
                    means.append(0.0)
                    stds.append(1.0)
                else:
                    col_obs = observed[:, col]
                    col_vals = x_all[col_obs, col]
                    if torch.isnan(col_vals).any() or torch.isinf(col_vals).any():
                        raise ValueError(
                            f"Se encontró valor no finito (NaN o Inf) en celdas observadas "
                            f"de '{node_type}' columna {col}. Si el valor es faltante, "
                            "debe marcarse con missing_mask = True."
                        )
                    mean_val = float(col_vals.mean().item())
                    var_val = float(((col_vals - mean_val) ** 2).mean().item())
                    std_val = float(math.sqrt(max(var_val, 0.0)))

                    # Manejo de columnas constantes (desviación 0) sin dividir por cero
                    if std_val <= 1e-12 or math.isclose(std_val, 0.0, abs_tol=1e-12):
                        std_val = 1.0

                    means.append(mean_val)
                    stds.append(std_val)

            stats_by_type[node_type] = NodeFeatureStats(
                node_type=node_type,
                num_features=num_features,
                mean=tuple(means),
                std=tuple(stds),
                observed_count=tuple(counts),
            )

        self._stats = stats_by_type
        self._is_fitted = True
        return self

    def transform_graph(self, graph: HeteroData, inplace: bool = False) -> HeteroData:
        """Estandariza los atributos `x` de un grafo.

        Las celdas observadas se centran y reducen; las celdas ausentes se fijan en `0.0`
        y conservan su `missing_mask = True`.

        Parameters
        ----------
        graph : HeteroData
            Grafo a estandarizar.
        inplace : bool, default=False
            Si es False (por defecto), opera sobre una copia profunda y preserva el original.

        Returns
        -------
        HeteroData
            Grafo con features estandarizadas.
        """
        if not self._is_fitted:
            raise RuntimeError("FeatureScaler debe ajustarse con fit() antes de transformar.")

        if not self._stats:
            warnings.warn(
                "FeatureScaler está ajustado pero no contiene estadísticas "
                "para ningún tipo de nodo; los atributos del grafo no serán modificados.",
                UserWarning,
                stacklevel=2,
            )

        target_graph = graph if inplace else graph.clone()

        for node_type in target_graph.node_types:
            store = target_graph[node_type]
            has_features = "x" in store and store.x is not None and store.x.size(1) > 0

            if node_type not in self._stats:
                if has_features:
                    warnings.warn(
                        f"El tipo de nodo '{node_type}' tiene atributos 'x' ({store.x.size(1)} "
                        "columnas) pero no fue observado en el conjunto de entrenamiento (train); "
                        "no será escalado.",
                        UserWarning,
                        stacklevel=2,
                    )
                continue

            stats = self._stats[node_type]

            if "x" not in store or store.x is None or stats.num_features == 0:
                continue

            if store.x.size(1) != stats.num_features:
                raise ValueError(
                    f"Dimensión de features incompatible para '{node_type}': "
                    f"se esperaban {stats.num_features} columnas, "
                    f"pero el grafo tiene {store.x.size(1)}."
                )

            mask = (
                store.missing_mask.detach()
                if "missing_mask" in store and store.missing_mask is not None
                else torch.zeros_like(store.x, dtype=torch.bool)
            )

            mean_t = torch.tensor(stats.mean, dtype=store.x.dtype, device=store.x.device)
            std_t = torch.tensor(stats.std, dtype=store.x.dtype, device=store.x.device)

            scaled_x = (store.x - mean_t) / std_t
            # Nota técnica: celdas ausentes quedan estrictamente en 0.0
            scaled_x = torch.where(mask, torch.zeros_like(scaled_x), scaled_x)

            store.x = scaled_x
            store.missing_mask = mask.clone()

        return target_graph

    def transform(
        self,
        graphs: Sequence[HeteroData],
        inplace: bool = False,
    ) -> list[HeteroData]:
        """Aplica la estandarización a una secuencia de grafos.

        Parameters
        ----------
        graphs : Sequence[HeteroData]
            Lista o secuencia de grafos.
        inplace : bool, default=False
            Si es False (por defecto), transforma sobre copias sin modificar los originales.

        Returns
        -------
        list[HeteroData]
            Lista de grafos transformados.
        """
        return [self.transform_graph(g, inplace=inplace) for g in graphs]

    def transform_subsets(
        self,
        subsets: Mapping[str, Sequence[HeteroData]],
        inplace: bool = False,
    ) -> dict[str, list[HeteroData]]:
        """Estandariza un mapeo de subconjuntos (p. ej. `{'train': ..., 'val': ..., 'test': ...}`).

        Parameters
        ----------
        subsets : Mapping[str, Sequence[HeteroData]]
            Mapeo con secuencias de grafos por partición.
        inplace : bool, default=False
            Si es False (por defecto), opera sobre copias.

        Returns
        -------
        dict[str, list[HeteroData]]
            Diccionario con grafos estandarizados por subconjunto.
        """
        return {k: self.transform(v, inplace=inplace) for k, v in subsets.items()}

    def to_dict(self) -> dict[str, Any]:
        """Serializa las estadísticas a un diccionario JSON-compatible.

        Returns
        -------
        dict[str, Any]
            Estructura con estadísticas por tipo de nodo.
        """
        return {
            "node_types": {
                node_type: {
                    "num_features": stats.num_features,
                    "mean": list(stats.mean),
                    "std": list(stats.std),
                    "observed_count": list(stats.observed_count),
                }
                for node_type, stats in self._stats.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FeatureScaler:
        """Reconstruye un `FeatureScaler` desde un diccionario serializado.

        Parameters
        ----------
        data : Mapping[str, Any]
            Diccionario obtenido mediante `to_dict()`.

        Returns
        -------
        FeatureScaler
            Instancia reconstruida y ajustada.
        """
        node_types_dict = data.get("node_types", {})
        stats_map: dict[str, NodeFeatureStats] = {}

        for node_type, item in node_types_dict.items():
            stats_map[node_type] = NodeFeatureStats(
                node_type=node_type,
                num_features=int(item["num_features"]),
                mean=tuple(float(v) for v in item.get("mean", ())),
                std=tuple(float(v) for v in item.get("std", ())),
                observed_count=tuple(int(v) for v in item.get("observed_count", ())),
            )

        return cls(stats=stats_map)

    def to_json(self, indent: int | None = None) -> str:
        """Exporta las estadísticas a una cadena JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> FeatureScaler:
        """Reconstruye un `FeatureScaler` desde una cadena JSON."""
        return cls.from_dict(json.loads(json_str))


class TargetScaler:
    """Estandarizador de los targets de AGCC ajustado exclusivamente con `train`.

    Calcula la media y desviación estándar de cada AGCC sobre las muestras de `train`
    con valor medido (`y_graph_mask = True`). Permite transformar tensores y grafos
    hacia la escala estandarizada y revertirlos mediante `inverse_transform` antes de
    evaluar métricas.
    """

    def __init__(
        self,
        targets: Sequence[str] = DEFAULT_SCFA_TARGETS,
        mean: Sequence[float] | None = None,
        std: Sequence[float] | None = None,
        observed_count: Sequence[int] | None = None,
    ) -> None:
        self._targets: tuple[str, ...] = tuple(targets)
        if not self._targets:
            raise ValueError("targets no puede ser una secuencia vacía.")

        if mean is not None and std is not None:
            if len(mean) != len(self._targets) or len(std) != len(self._targets):
                raise ValueError("mean y std deben tener la misma longitud que targets.")
            self._mean: tuple[float, ...] = tuple(float(v) for v in mean)
            self._std: tuple[float, ...] = tuple(float(v) for v in std)
            self._observed_count: tuple[int, ...] = (
                tuple(int(v) for v in observed_count)
                if observed_count is not None
                else tuple(0 for _ in self._targets)
            )
            self._is_fitted: bool = True
        else:
            self._mean = ()
            self._std = ()
            self._observed_count = ()
            self._is_fitted = False

    @property
    def targets(self) -> tuple[str, ...]:
        """Secuencia de nombres canónicos de los AGCC objetivo."""
        return self._targets

    @property
    def is_fitted(self) -> bool:
        """Indica si el escalador fue ajustado con datos de entrenamiento."""
        return self._is_fitted

    @property
    def mean(self) -> Tensor:
        """Tensor 1D con la media por AGCC."""
        if not self._is_fitted:
            raise RuntimeError("TargetScaler no ha sido ajustado.")
        return torch.tensor(self._mean, dtype=torch.float32)

    @property
    def std(self) -> Tensor:
        """Tensor 1D con la desviación estándar por AGCC."""
        if not self._is_fitted:
            raise RuntimeError("TargetScaler no ha sido ajustado.")
        return torch.tensor(self._std, dtype=torch.float32)

    @property
    def mean_tuple(self) -> tuple[float, ...]:
        """Tupla con las medias de train."""
        return self._mean

    @property
    def std_tuple(self) -> tuple[float, ...]:
        """Tupla con las desviaciones estándar de train."""
        return self._std

    @property
    def observed_count(self) -> tuple[int, ...]:
        """Cantidad de muestras de train con valor medido por AGCC."""
        return self._observed_count

    @classmethod
    def fit(
        cls,
        data: Sequence[HeteroData] | Tensor,
        mask: Tensor | None = None,
        targets: Sequence[str] = DEFAULT_SCFA_TARGETS,
    ) -> TargetScaler:
        """Crea y ajusta un `TargetScaler` a partir de grafos o tensores de train.

        Parameters
        ----------
        data : Sequence[HeteroData] | Tensor
            Grafos de entrenamiento o tensor de targets `[N, len(targets)]`.
        mask : Tensor | None, default=None
            Máscara booleana si data es Tensor. Si data son grafos, se toma `y_graph_mask`.
        targets : Sequence[str], default=DEFAULT_SCFA_TARGETS
            Nombres de los AGCC.

        Returns
        -------
        TargetScaler
            Instancia ajustada.
        """
        scaler = cls(targets=targets)
        return scaler.fit_data(data, mask=mask)

    def fit_data(
        self,
        data: Sequence[HeteroData] | Tensor,
        mask: Tensor | None = None,
    ) -> TargetScaler:
        """Ajusta estadísticas de media y desviación sobre las muestras de `train`.

        Parameters
        ----------
        data : Sequence[HeteroData] | Tensor
            Grafos de entrenamiento o tensor de targets.
        mask : Tensor | None, default=None
            Máscara de valores medidos.

        Returns
        -------
        TargetScaler
            La misma instancia ajustada.
        """
        if isinstance(data, Tensor):
            y_tensor = data.detach().to(torch.float32)
            if mask is not None:
                mask_tensor = mask.detach().to(torch.bool)
            else:
                mask_tensor = torch.ones_like(y_tensor, dtype=torch.bool)
        else:
            if not data:
                raise ValueError("train_graphs no puede estar vacío para ajustar TargetScaler.")
            y_list: list[Tensor] = []
            mask_list: list[Tensor] = []
            for g in data:
                if "y_graph" in g and "y_graph_mask" in g:
                    y_list.append(g.y_graph.detach().to(torch.float32))
                    mask_list.append(g.y_graph_mask.detach().to(torch.bool))
                else:
                    g_temp = add_graph_target(g.clone(), targets=self._targets)
                    y_list.append(g_temp.y_graph.detach().to(torch.float32))
                    mask_list.append(g_temp.y_graph_mask.detach().to(torch.bool))

            y_tensor = torch.cat(y_list, dim=0)
            mask_tensor = torch.cat(mask_list, dim=0)

        if y_tensor.dim() == 1:
            y_tensor = y_tensor.unsqueeze(0)
        if mask_tensor.dim() == 1:
            mask_tensor = mask_tensor.unsqueeze(0)

        num_targets = len(self._targets)
        if y_tensor.size(-1) != num_targets:
            raise ValueError(
                f"Dimensión incompatible de target: se esperaban {num_targets} columnas, "
                f"se obtuvieron {y_tensor.size(-1)}."
            )
        if mask_tensor.shape != y_tensor.shape:
            raise ValueError(
                f"Forma de mask ({list(mask_tensor.shape)}) no coincide "
                f"con target ({list(y_tensor.shape)})."
            )

        observed = mask_tensor == True  # noqa: E712
        observed_counts = observed.sum(dim=0)

        means: list[float] = []
        stds: list[float] = []
        counts: list[int] = []

        for col in range(num_targets):
            count_col = int(observed_counts[col].item())
            counts.append(count_col)

            if count_col == 0:
                means.append(0.0)
                stds.append(1.0)
            else:
                vals = y_tensor[observed[:, col], col]
                if torch.isnan(vals).any() or torch.isinf(vals).any():
                    target_name = self._targets[col] if col < len(self._targets) else str(col)
                    raise ValueError(
                        f"Se encontró valor no finito (NaN o Inf) en target observado "
                        f"'{target_name}'. Si el valor no fue medido, debe marcarse "
                        "con y_graph_mask = False."
                    )
                mean_val = float(vals.mean().item())
                var_val = float(((vals - mean_val) ** 2).mean().item())
                std_val = float(math.sqrt(max(var_val, 0.0)))

                # Manejo de columnas constantes (desviación 0)
                if std_val <= 1e-12 or math.isclose(std_val, 0.0, abs_tol=1e-12):
                    std_val = 1.0

                means.append(mean_val)
                stds.append(std_val)

        self._mean = tuple(means)
        self._std = tuple(stds)
        self._observed_count = tuple(counts)
        self._is_fitted = True
        return self

    def transform(
        self,
        y: Tensor | Sequence[float] | Sequence[Sequence[float]],
        mask: Tensor | None = None,
    ) -> Tensor:
        """Estandariza los valores del target según la media y desviación de `train`.

        Parameters
        ----------
        y : Tensor | Sequence[float] | Sequence[Sequence[float]]
            Valores en la escala original.
        mask : Tensor | None, default=None
            Máscara de valores observados. Si se suministra, las celdas enmascaradas
            se fijan en `0.0`.

        Returns
        -------
        Tensor
            Targets en la escala estandarizada.
        """
        if not self._is_fitted:
            raise RuntimeError("TargetScaler debe ajustarse con fit() antes de transformar.")

        y_tensor = y if isinstance(y, Tensor) else torch.tensor(y, dtype=torch.float32)

        mean_t = torch.tensor(self._mean, dtype=y_tensor.dtype, device=y_tensor.device)
        std_t = torch.tensor(self._std, dtype=y_tensor.dtype, device=y_tensor.device)

        scaled = (y_tensor - mean_t) / std_t

        if mask is not None:
            mask_t = mask.to(device=y_tensor.device, dtype=torch.bool)
            scaled = torch.where(mask_t, scaled, torch.zeros_like(scaled))

        return scaled

    def inverse_transform(
        self,
        y: Tensor | Sequence[float] | Sequence[Sequence[float]],
        mask: Tensor | None = None,
    ) -> Tensor:
        """Invierte la estandarización para recuperar los targets en las unidades de la fuente.

        Permite recuperar la predicción y objetivos originales antes de calcular
        métricas de evaluación (§6.2 gnn-architecture.md).

        Parameters
        ----------
        y : Tensor | Sequence[float] | Sequence[Sequence[float]]
            Valores en escala estandarizada.
        mask : Tensor | None, default=None
            Máscara opcional para preservar ceros en posiciones no medidas.

        Returns
        -------
        Tensor
            Targets recuperados en la escala original.
        """
        if not self._is_fitted:
            raise RuntimeError("TargetScaler debe ajustarse con fit() antes de inverse_transform.")

        y_tensor = y if isinstance(y, Tensor) else torch.tensor(y, dtype=torch.float32)

        mean_t = torch.tensor(self._mean, dtype=y_tensor.dtype, device=y_tensor.device)
        std_t = torch.tensor(self._std, dtype=y_tensor.dtype, device=y_tensor.device)

        unscaled = y_tensor * std_t + mean_t

        if mask is not None:
            mask_t = mask.to(device=y_tensor.device, dtype=torch.bool)
            unscaled = torch.where(mask_t, unscaled, torch.zeros_like(unscaled))

        return unscaled

    def transform_graph(self, graph: HeteroData, inplace: bool = False) -> HeteroData:
        """Estandariza `y_graph` en un grafo si está presente.

        Parameters
        ----------
        graph : HeteroData
            Grafo a transformar.
        inplace : bool, default=False
            Si es False (por defecto), opera sobre una copia.

        Returns
        -------
        HeteroData
            Grafo con target estandarizado.
        """
        target_graph = graph if inplace else graph.clone()
        if "y_graph" in target_graph and "y_graph_mask" in target_graph:
            target_graph.y_graph = self.transform(
                target_graph.y_graph,
                mask=target_graph.y_graph_mask,
            )
        return target_graph

    def transform_graphs(
        self,
        graphs: Sequence[HeteroData],
        inplace: bool = False,
    ) -> list[HeteroData]:
        """Aplica la estandarización de targets a una secuencia de grafos."""
        return [self.transform_graph(g, inplace=inplace) for g in graphs]

    def to_dict(self) -> dict[str, Any]:
        """Serializa las estadísticas del target a un diccionario JSON-compatible.

        Returns
        -------
        dict[str, Any]
            Diccionario con nombres de target, medias y desviaciones estándar.
        """
        return {
            "targets": list(self._targets),
            "mean": list(self._mean),
            "std": list(self._std),
            "observed_count": list(self._observed_count),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TargetScaler:
        """Reconstruye un `TargetScaler` desde un diccionario serializado.

        Parameters
        ----------
        data : Mapping[str, Any]
            Estructura generada por `to_dict()`.

        Returns
        -------
        TargetScaler
            Instancia reconstruida y ajustada.
        """
        return cls(
            targets=tuple(data["targets"]),
            mean=tuple(float(v) for v in data.get("mean", ())),
            std=tuple(float(v) for v in data.get("std", ())),
            observed_count=tuple(int(v) for v in data.get("observed_count", ())),
        )

    def to_json(self, indent: int | None = None) -> str:
        """Exporta las estadísticas a una cadena JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> TargetScaler:
        """Reconstruye un `TargetScaler` desde una cadena JSON."""
        return cls.from_dict(json.loads(json_str))


def scalers_to_dict(
    feature_scaler: FeatureScaler,
    target_scaler: TargetScaler,
) -> dict[str, Any]:
    """Empaqueta ambos escaladores en un único diccionario serializable para A44-5.

    Parameters
    ----------
    feature_scaler : FeatureScaler
        Escalador de features por nodo.
    target_scaler : TargetScaler
        Escalador de targets por grafo.

    Returns
    -------
    dict[str, Any]
        Diccionario listo para JSON con ambos escaladores.
    """
    return {
        "feature_scaler": feature_scaler.to_dict(),
        "target_scaler": target_scaler.to_dict(),
    }


def scalers_from_dict(
    data: Mapping[str, Any],
) -> tuple[FeatureScaler, TargetScaler]:
    """Reconstruye el par `(FeatureScaler, TargetScaler)` desde un diccionario.

    Parameters
    ----------
    data : Mapping[str, Any]
        Estructura generada por `scalers_to_dict()`.

    Returns
    -------
    tuple[FeatureScaler, TargetScaler]
        Tupla con las instancias deserializadas.
    """
    feature_scaler = FeatureScaler.from_dict(data["feature_scaler"])
    target_scaler = TargetScaler.from_dict(data["target_scaler"])
    return feature_scaler, target_scaler


__all__ = [
    "FeatureScaler",
    "NodeFeatureStats",
    "TargetScaler",
    "scalers_from_dict",
    "scalers_to_dict",
]
