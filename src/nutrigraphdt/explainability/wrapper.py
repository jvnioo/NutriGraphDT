"""Wrapper de explicadores para HeteroData en NutriGraphDT (A60-P1, #170).

Encapsula la configuración, ejecución y validación de explicadores de PyG
(`torch_geometric.explain`) sobre modelos heterogéneos (`SCFAGraphModel`), adaptando
entradas y salidas de `HeteroData` y generando artefactos conformes al contrato versionado
`1.0.0` (A55-P3, #156).

Principios:
1. Asociación no es causalidad: la importancia mide sensibilidad dentro del modelo entrenado,
   no evidencia causal ni validación biológica.
2. La atención no es una explicación por defecto: los pesos de atención en `hetero_gat`
   requieren advertencia explícita (`uses_attention=True`).
3. Detección activa de incompatibilidad: combinaciones incompatibles (como máscaras de aristas
   sobre `homo_sage`, o `AttentionExplainer` en modelos sin atención) fallan con un mensaje
   explícito (`IncompatibleExplainerError`), sin producir resultados parciales silenciosos.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Literal

import torch
import torch_geometric
from torch import Tensor, nn
from torch_geometric.data import HeteroData
from torch_geometric.explain import Explainer
from torch_geometric.explain.algorithm import (
    AttentionExplainer,
    CaptumExplainer,
    ExplainerAlgorithm,
    GNNExplainer,
    PGExplainer,
)
from torch_geometric.explain.algorithm.utils import clear_masks, set_hetero_masks
from torch_geometric.nn import MessagePassing

from nutrigraphdt.explainability.contract import (
    ATTENTION_WARNING,
    EXPLANATION_FORMAT,
    EXPLANATION_FORMAT_VERSION,
    SYNTHETIC_WARNING,
    AttributeImportance,
    EdgeImportance,
    EdgeRef,
    Evidence,
    ExplainerRef,
    Explanation,
    Importance,
    NodeImportance,
    NodeRef,
    RunRef,
    Scale,
    SplitRef,
    Subgraph,
    TargetRef,
    Warning_,
    validate_explanation,
)
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES
from nutrigraphdt.models.gnn.base import EdgeType, SCFAGraphModel, layer_edge_types

DEFAULT_MODEL_CONFIG: Final[dict[str, str]] = {
    "mode": "regression",
    "return_type": "raw",
    "task_level": "graph",
}

WARNING_MESSAGES: Final[Mapping[str, str]] = {
    "association_not_causation": (
        "La importancia calculada refleja asociación dentro del modelo, no relación causal "
        "ni validación biológica."
    ),
    "importance_is_not_evidence": (
        "La importancia es una propiedad del modelo entrenado; la evidencia de cada arista "
        "proviene del grafo de conocimiento y no cambia con la explicación."
    ),
    "synthetic_data": (
        "La instancia explicada pertenece a un dataset sintético; los valores no corresponden "
        "a observaciones biológicas reales."
    ),
    "attention_is_not_explanation": (
        "La importancia proviene de coeficientes de atención; los pesos de atención no "
        "constituyen una explicación formal por defecto."
    ),
}


class IncompatibleExplainerError(ValueError):
    """El explicador o la configuración elegida es incompatible con el modelo o los datos."""


class HeteroAdapter(nn.Module):
    """Reconstruye el `HeteroData` del modelo y devuelve salida unidimensional `[B, 1]`.

    PyG Explainer invoca el modelo pasando `(x_dict, edge_index_dict)`. Los modelos de
    NutriGraphDT reciben un `HeteroData`. Este adaptador combina las entradas enmascaradas con
    las características estáticas del grafo (nodos sin atributos, máscaras de valores ausentes,
    aristas que no reciben convolución) y selecciona la columna objetivo correspondiente.
    """

    def __init__(self, model: SCFAGraphModel, template: HeteroData, output_index: int) -> None:
        super().__init__()
        self.model = model
        self.template = template
        self.output_index = output_index

    def forward(
        self,
        x_dict: Mapping[str, Tensor],
        edge_index_dict: Mapping[EdgeType, Tensor],
        **_: Any,
    ) -> Tensor:
        graph = HeteroData()
        for node_type in self.template.node_types:
            store = self.template[node_type]
            graph[node_type].x = x_dict.get(node_type, store.x)
            if "missing_mask" in store:
                graph[node_type].missing_mask = store.missing_mask
            if "node_id" in store:
                graph[node_type].node_id = store.node_id
        for edge_type in self.template.edge_types:
            store = self.template[edge_type]
            if edge_type in edge_index_dict:
                graph[edge_type].edge_index = edge_index_dict[edge_type]
            elif "edge_index" in store:
                graph[edge_type].edge_index = store.edge_index
            if "edge_attr" in store:
                graph[edge_type].edge_attr = store.edge_attr
        output: Tensor = self.model(graph)
        return output[:, [self.output_index]]


def explained_inputs(
    data: HeteroData, model: SCFAGraphModel
) -> tuple[dict[str, Tensor], dict[EdgeType, Tensor], list[EdgeType]]:
    """Extrae `x_dict` y `edge_index_dict` aptos para optimización por gradiente.

    - Excluye tipos de nodo sin columnas numéricas (`metabolite`, `phenotype`): máscaras
      sobre tensores de ancho 0 no reciben gradiente y provocan fallos de PyTorch.
    - Excluye tipos de arista que no intervienen en ninguna capa convolucional del modelo:
      aristas sin convolución no reciben gradiente de máscara.
    """
    x_dict = {
        node_type: data[node_type].x
        for node_type in data.node_types
        if "x" in data[node_type] and data[node_type].x.shape[1] > 0
    }
    relevant = {
        edge_type
        for layer in layer_edge_types(model.metadata, model.config.num_layers)
        for edge_type in layer
    }
    edges = {
        edge_type: data[edge_type].edge_index
        for edge_type in data.edge_types
        if edge_type in relevant and "edge_index" in data[edge_type]
    }
    skipped = sorted(edge_type for edge_type in data.edge_types if edge_type not in relevant)
    return x_dict, edges, skipped


def edge_mask_reach(adapter: HeteroAdapter, edges: Mapping[EdgeType, Tensor]) -> int:
    """Calcula cuántas capas `MessagePassing` del modelo reciben la máscara de aristas."""
    masks = {et: torch.ones(ei.shape[1]) for et, ei in edges.items()}
    set_hetero_masks(adapter, masks, dict(edges))
    reached = sum(
        1
        for m in adapter.modules()
        if isinstance(m, MessagePassing) and getattr(m, "explain", False)
    )
    clear_masks(adapter)
    return reached


def edge_mask_effect(
    adapter: HeteroAdapter,
    x_dict: Mapping[str, Tensor],
    edges: Mapping[EdgeType, Tensor],
) -> float:
    """Calcula |salida(máscaras=1) − salida(máscaras=0)|. Cero si la máscara no se utiliza."""
    outputs: list[float] = []
    for value in (1.0, 0.0):
        masks = {et: torch.full((ei.shape[1],), value) for et, ei in edges.items()}
        set_hetero_masks(adapter, masks, dict(edges), apply_sigmoid=False)
        with torch.no_grad():
            outputs.append(float(adapter(x_dict, edges)[0, 0]))
        clear_masks(adapter)
    return abs(outputs[0] - outputs[1])


@dataclass(frozen=True)
class HeteroExplainerConfig:
    """Configuración del wrapper de explicadores."""

    algorithm: str | ExplainerAlgorithm = "gnn_explainer"
    explanation_type: Literal["model", "phenomenon"] = "model"
    node_mask_type: Literal["attributes", "object"] | None = "attributes"
    edge_mask_type: Literal["object"] | None = "object"
    epochs: int = 100
    lr: float = 0.01
    seed: int = 42
    top_k: int = 10
    unit: str = "1"
    extra_config: dict[str, Any] = field(default_factory=dict)


class HeteroExplainer:
    """Wrapper de explicabilidad sobre modelos `SCFAGraphModel` y datos `HeteroData`."""

    def __init__(
        self,
        model: SCFAGraphModel,
        *,
        config: HeteroExplainerConfig | None = None,
        algorithm: str | ExplainerAlgorithm = "gnn_explainer",
        explanation_type: Literal["model", "phenomenon"] = "model",
        node_mask_type: Literal["attributes", "object"] | None = "attributes",
        edge_mask_type: Literal["object"] | None = "object",
        epochs: int = 100,
        lr: float = 0.01,
        seed: int = 42,
        top_k: int = 10,
        unit: str = "1",
        run: RunRef | Mapping[str, Any] | None = None,
        node_feature_names: Mapping[str, Sequence[str]] | None = None,
        extra_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.model = model
        # AttentionExplainer solo opera sobre aristas
        is_attention_alg = (
            isinstance(algorithm, str) and "attention" in algorithm.lower()
        ) or isinstance(algorithm, AttentionExplainer)
        if is_attention_alg and node_mask_type == "attributes":
            node_mask_type = None

        if config is not None:
            self.config = config
        else:
            self.config = HeteroExplainerConfig(
                algorithm=algorithm,
                explanation_type=explanation_type,
                node_mask_type=node_mask_type,
                edge_mask_type=edge_mask_type,
                epochs=epochs,
                lr=lr,
                seed=seed,
                top_k=top_k,
                unit=unit,
                extra_config=dict(extra_config or {}),
            )
        self.run_ref = self._resolve_run_ref(run)
        self.node_feature_names = dict(node_feature_names or {})

    def _resolve_run_ref(self, run: RunRef | Mapping[str, Any] | None) -> RunRef | None:
        if run is None:
            return None
        if isinstance(run, RunRef):
            return run
        return RunRef.model_validate(dict(run))

    def _build_algorithm(self) -> tuple[ExplainerAlgorithm, str, str, dict[str, Any], bool]:
        """Instancia el algoritmo de PyG y devuelve sus metadatos y configuración."""
        alg = self.config.algorithm
        epochs = self.config.epochs
        lr = self.config.lr
        uses_attention = False

        if isinstance(alg, str):
            name_lower = alg.lower().replace("-", "_")
            if name_lower in ("gnn_explainer", "gnnexplainer"):
                algorithm: ExplainerAlgorithm = GNNExplainer(epochs=epochs, lr=lr)
                alg_name = "GNNExplainer"
                alg_path = "torch_geometric.explain.algorithm.GNNExplainer"
                cfg = {"epochs": epochs, "lr": lr, **self.config.extra_config}
            elif name_lower in ("attention", "attention_explainer", "attentionexplainer"):
                algorithm = AttentionExplainer()
                alg_name = "AttentionExplainer"
                alg_path = "torch_geometric.explain.algorithm.AttentionExplainer"
                cfg = dict(self.config.extra_config)
                uses_attention = True
            elif name_lower in ("integrated_gradients", "captum_integrated_gradients"):
                if importlib.util.find_spec("captum") is None:
                    raise IncompatibleExplainerError(
                        "CaptumExplainer('IntegratedGradients') requiere 'captum'. "
                        "Instale el extra: pip install -e '.[explain]'."
                    )
                algorithm = CaptumExplainer("IntegratedGradients")
                alg_name = "Captum IntegratedGradients"
                alg_path = "torch_geometric.explain.algorithm.CaptumExplainer"
                cfg = {"method": "IntegratedGradients", **self.config.extra_config}
            elif name_lower in ("saliency", "captum_saliency"):
                if importlib.util.find_spec("captum") is None:
                    raise IncompatibleExplainerError(
                        "CaptumExplainer('Saliency') requiere 'captum'. "
                        "Instale el extra: pip install -e '.[explain]'."
                    )
                algorithm = CaptumExplainer("Saliency")
                alg_name = "Captum Saliency"
                alg_path = "torch_geometric.explain.algorithm.CaptumExplainer"
                cfg = {"method": "Saliency", **self.config.extra_config}
            elif name_lower in ("pg_explainer", "pgexplainer"):
                algorithm = PGExplainer(epochs=epochs, lr=lr)
                alg_name = "PGExplainer"
                alg_path = "torch_geometric.explain.algorithm.PGExplainer"
                cfg = {"epochs": epochs, "lr": lr, **self.config.extra_config}
            else:
                raise IncompatibleExplainerError(f"Algoritmo desconocido: {alg!r}.")
        elif isinstance(alg, ExplainerAlgorithm):
            algorithm = alg
            alg_name = alg.__class__.__name__
            alg_path = f"{alg.__class__.__module__}.{alg.__class__.__qualname__}"
            cfg = {"epochs": epochs, "lr": lr, **self.config.extra_config}
            if isinstance(alg, AttentionExplainer):
                uses_attention = True
        else:
            raise TypeError(f"Se esperaba str o ExplainerAlgorithm; recibido {type(alg)!r}.")

        return algorithm, alg_name, alg_path, cfg, uses_attention

    def _resolve_target(self, target: str | int | None) -> tuple[str, int]:
        target_names = list(getattr(self.model, "target_names", ()))
        if not target_names:
            target_names = list(MODEL_OUTPUT_NAMES)

        if target is None:
            return target_names[0], 0
        if isinstance(target, int):
            if not (0 <= target < len(target_names)):
                raise ValueError(
                    f"Índice de target {target} fuera de rango [0, {len(target_names) - 1}]."
                )
            return target_names[target], target
        if isinstance(target, str):
            if target in target_names:
                return target, target_names.index(target)
            raise ValueError(
                f"Target {target!r} no encontrado en el modelo. Opciones: {target_names}."
            )
        raise TypeError(f"Target debe ser str o int; recibido {type(target)!r}.")

    def _model_variant(self) -> str:
        var = getattr(self.model, "variant", None)
        if var:
            return str(var)
        cfg = getattr(self.model, "config", None)
        if cfg is not None:
            cfg_var = getattr(cfg, "variant", None)
            if cfg_var:
                return str(cfg_var)
        cls_name = self.model.__class__.__name__
        if cls_name == "HomoSAGE":
            return "homo_sage"
        if cls_name == "HeteroSAGE":
            return "hetero_sage"
        if cls_name == "HeteroGAT":
            return "hetero_gat"
        return cls_name.lower()

    def _ensure_compatibility(
        self,
        adapter: HeteroAdapter,
        x_dict: Mapping[str, Tensor],
        edges: Mapping[EdgeType, Tensor],
        algorithm: ExplainerAlgorithm,
        uses_attention: bool,
    ) -> None:
        """Verifica compatibilidad técnica antes de optimizar máscaras."""
        variant = self._model_variant()
        has_attention = variant == "hetero_gat" or any(
            "GAT" in m.__class__.__name__ for m in self.model.modules()
        )

        # 1. AttentionExplainer requiere un modelo con capas de atención y solo admite aristas
        if uses_attention:
            if not has_attention:
                raise IncompatibleExplainerError(
                    f"AttentionExplainer requiere un modelo con capas de atención ('hetero_gat'). "
                    f"La variante actual es {variant!r}."
                )
            if self.config.node_mask_type is not None:
                raise IncompatibleExplainerError(
                    "AttentionExplainer solo calcula importancia de aristas; "
                    "no admite máscaras de nodos ni atributos (node_mask_type=None)."
                )

        # 2. Máscaras de aristas en modelos homogéneos o sin alcance de mensaje
        if self.config.edge_mask_type is not None:
            reach = edge_mask_reach(adapter, edges)
            if reach == 0:
                raise IncompatibleExplainerError(
                    f"La variante {variant!r} es incompatible con explicaciones de aristas: "
                    "las máscaras de aristas no llegan a ninguna capa MessagePassing (reach=0). "
                    "En 'homo_sage' el grafo se homogeniza internamente, por lo que las máscaras "
                    "por tripleta no tienen efecto. Utilice solo máscaras de nodos o una variante "
                    "heterogénea ('hetero_sage', 'hetero_gat')."
                )
            effect = edge_mask_effect(adapter, x_dict, edges)
            if effect == 0.0:
                raise IncompatibleExplainerError(
                    "Las máscaras de aristas no alteran la predicción del modelo (efecto=0.0). "
                    "Los valores devueltos por el explicador no explicarían la salida."
                )

    def explain(
        self,
        data: HeteroData,
        *,
        target: str | int | None = None,
        top_k: int | None = None,
        unit: str | None = None,
        run: RunRef | Mapping[str, Any] | None = None,
    ) -> Explanation:
        """Genera una explicación conforme al contrato `1.0.0` para la instancia dada."""
        k = top_k if top_k is not None else self.config.top_k
        output_unit = unit if unit is not None else self.config.unit
        target_name, target_index = self._resolve_target(target)

        algorithm, alg_name, alg_path, alg_cfg, uses_attention = self._build_algorithm()

        graph_id = getattr(data, "graph_id", None)
        if graph_id is None:
            raise ValueError(
                "El HeteroData no tiene graph_id; no se puede identificar la instancia."
            )
        is_synthetic = bool(
            getattr(data, "is_synthetic", False) or str(graph_id).startswith("synthetic:")
        )
        run_ref = self._resolve_run_ref(run) or self.run_ref
        if run_ref is None and not is_synthetic:
            raise ValueError(
                "Las explicaciones sobre datos no sintéticos requieren `run` con la trazabilidad "
                "del run.json; no se generan referencias de corrida ficticias."
            )

        # Modelo en eval sin requerir gradientes de pesos durante la optimización de máscaras.
        # El estado se restaura también si la comprobación de compatibilidad falla.
        eval_model = self.model
        was_training = eval_model.training
        orig_grads = [p.requires_grad for p in eval_model.parameters()]
        adapter = HeteroAdapter(eval_model, data, target_index).eval()
        x_dict, edges, _skipped = explained_inputs(data, eval_model)

        try:
            eval_model.eval()
            for p in eval_model.parameters():
                p.requires_grad = False

            self._ensure_compatibility(adapter, x_dict, edges, algorithm, uses_attention)

            # Ejecutar explicador PyG
            torch.manual_seed(self.config.seed)
            explainer = Explainer(
                adapter,
                algorithm=algorithm,
                explanation_type=self.config.explanation_type,
                node_mask_type=self.config.node_mask_type,
                edge_mask_type=self.config.edge_mask_type,
                model_config=DEFAULT_MODEL_CONFIG,
            )

            kwargs: dict[str, Any] = {"index": 0}
            if self.config.explanation_type == "phenomenon":
                with torch.no_grad():
                    kwargs["target"] = adapter(dict(x_dict), dict(edges))

            if isinstance(algorithm, PGExplainer):
                for epoch in range(self.config.epochs):
                    algorithm.train(epoch, adapter, dict(x_dict), dict(edges), **kwargs)
            pyg_explanation = explainer(dict(x_dict), dict(edges), **kwargs)

            # Predicción puntual del modelo, aún en modo eval
            with torch.no_grad():
                model_output = float(adapter(x_dict, edges)[0, 0].item())
        finally:
            clear_masks(adapter)
            for p, orig in zip(eval_model.parameters(), orig_grads, strict=False):
                p.requires_grad = orig
            if was_training:
                eval_model.train()

        # Recolección y validación de máscaras
        node_masks: dict[str, Tensor] = {}
        edge_masks: dict[EdgeType, Tensor] = {}
        if self.config.node_mask_type is not None:
            try:
                node_masks = dict(pyg_explanation.collect("node_mask"))
            except KeyError:
                node_masks = {}
            if not node_masks:
                raise IncompatibleExplainerError(
                    f"El explicador {alg_name} no produjo máscaras de nodos solicitadas."
                )

        if self.config.edge_mask_type is not None:
            try:
                edge_masks = dict(pyg_explanation.collect("edge_mask"))
            except KeyError:
                edge_masks = {}
            if not edge_masks:
                raise IncompatibleExplainerError(
                    f"El explicador {alg_name} no produjo máscaras de aristas solicitadas."
                )

        return self._build_contract_explanation(
            data=data,
            graph_id=str(graph_id),
            is_synthetic=is_synthetic,
            run_ref=run_ref,
            target_name=target_name,
            target_index=target_index,
            unit=output_unit,
            model_output=model_output,
            node_masks=node_masks,
            edge_masks=edge_masks,
            alg_name=alg_name,
            alg_path=alg_path,
            alg_cfg=alg_cfg,
            uses_attention=uses_attention,
            k=k,
        )

    def _build_contract_explanation(
        self,
        data: HeteroData,
        graph_id: str,
        is_synthetic: bool,
        run_ref: RunRef | None,
        target_name: str,
        target_index: int,
        unit: str,
        model_output: float,
        node_masks: Mapping[str, Tensor],
        edge_masks: Mapping[EdgeType, Tensor],
        alg_name: str,
        alg_path: str,
        alg_cfg: dict[str, Any],
        uses_attention: bool,
        k: int,
    ) -> Explanation:
        # Metadatos del target
        sample_id = getattr(data, "sample_id", None)

        # Normalización de importancias
        raw_vals: list[float] = []
        for nm in node_masks.values():
            raw_vals.extend(nm.abs().reshape(-1).tolist())
        for em in edge_masks.values():
            raw_vals.extend(em.abs().reshape(-1).tolist())

        max_val = max(raw_vals) if raw_vals else 1.0
        norm_factor = max_val if max_val > 0.0 else 1.0

        # Construcción de importancia de atributos y nodos
        nodes_dict: dict[tuple[str, str], float] = {}
        attributes: list[AttributeImportance] = []

        # Asegurar que todos los nodos existentes en el grafo figuren en la explicación (EXP-05)
        for node_type in data.node_types:
            store = data[node_type]
            node_ids = list(getattr(store, "node_id", []))
            if not node_ids and "x" in store:
                node_ids = [
                    f"{'synthetic:' if is_synthetic else ''}{node_type}:{i:04d}"
                    for i in range(store.x.shape[0])
                ]
            for nid in node_ids:
                nodes_dict[(node_type, str(nid))] = 0.0

        for node_type, mask in node_masks.items():
            store = data[node_type]
            node_ids = list(getattr(store, "node_id", []))
            if not node_ids:
                node_ids = [
                    f"{'synthetic:' if is_synthetic else ''}{node_type}:{i:04d}"
                    for i in range(mask.shape[0])
                ]

            feature_names = self._feature_names(
                data, node_type, mask.shape[1] if mask.ndim > 1 else 1
            )

            for i, nid in enumerate(node_ids):
                row_mask = mask[i]
                if self.config.node_mask_type == "attributes" and mask.ndim > 1:
                    row_abs = row_mask.abs()
                    node_imp = float(
                        (row_abs.sum() / (norm_factor * mask.shape[1])).clamp(0.0, 1.0).item()
                    )
                    nodes_dict[(node_type, str(nid))] = round(node_imp, 6)
                    for col_idx, col_name in enumerate(feature_names):
                        attr_imp = float((row_abs[col_idx] / norm_factor).clamp(0.0, 1.0).item())
                        attributes.append(
                            AttributeImportance(
                                node_type=node_type,
                                node_id=str(nid),
                                attribute=col_name,
                                importance=round(attr_imp, 6),
                            )
                        )
                else:
                    node_val = float((row_mask.abs().mean() / norm_factor).clamp(0.0, 1.0).item())
                    nodes_dict[(node_type, str(nid))] = round(node_val, 6)

        nodes: list[NodeImportance] = [
            NodeImportance(node_type=nt, node_id=nid, importance=imp)
            for (nt, nid), imp in nodes_dict.items()
        ]

        # Construcción de importancia de aristas
        edges: list[EdgeImportance] = []
        if self.config.edge_mask_type is not None:
            for edge_type in data.edge_types:
                store = data[edge_type]
                source_type, relation_type, target_type = edge_type
                if "edge_index" not in store:
                    continue
                edge_index = store.edge_index
                num_edges = edge_index.shape[1]

                src_nodes = [n.node_id for n in nodes if n.node_type == source_type]
                tgt_nodes = [n.node_id for n in nodes if n.node_type == target_type]

                mask_for_type = edge_masks.get(edge_type)
                is_reverse = relation_type.startswith("rev_")

                for e in range(num_edges):
                    src_idx = int(edge_index[0, e].item())
                    tgt_idx = int(edge_index[1, e].item())
                    source_id = (
                        src_nodes[src_idx]
                        if src_idx < len(src_nodes)
                        else f"{source_type}_{src_idx}"
                    )
                    target_id = (
                        tgt_nodes[tgt_idx]
                        if tgt_idx < len(tgt_nodes)
                        else f"{target_type}_{tgt_idx}"
                    )

                    if mask_for_type is not None:
                        raw_edge_imp = float(mask_for_type[e].abs().item())
                        edge_imp = round(
                            float(torch.tensor(raw_edge_imp / norm_factor).clamp(0.0, 1.0).item()),
                            6,
                        )
                    else:
                        edge_imp = 0.0

                    if is_reverse:
                        evidence = None
                    else:
                        ev_status = (
                            store.evidence_status[e]
                            if "evidence_status" in store and e < len(store.evidence_status)
                            else ("synthetic" if is_synthetic else "observed")
                        )
                        ev_method = (
                            store.evidence_method[e]
                            if "evidence_method" in store and e < len(store.evidence_method)
                            else ("synthetic_generator" if is_synthetic else "measurement")
                        )
                        ev_source = (
                            store.evidence_source[e]
                            if "evidence_source" in store and e < len(store.evidence_source)
                            else None
                        )
                        evidence = Evidence(
                            evidence_status=str(ev_status),
                            evidence_method=str(ev_method),
                            evidence_source=str(ev_source) if ev_source else None,
                        )

                    edges.append(
                        EdgeImportance(
                            source_type=source_type,
                            relation_type=relation_type,
                            target_type=target_type,
                            source_id=source_id,
                            target_id=target_id,
                            importance=edge_imp,
                            evidence=evidence,
                        )
                    )

        # Construcción de Subgrafo top-k (EXP-07)
        edge_scores = {
            (e.source_type, e.relation_type, e.target_type, e.source_id, e.target_id): e.importance
            for e in edges
        }
        ranked = sorted(edge_scores, key=lambda key: (-edge_scores[key], key))
        sub_count = min(k, len(ranked))
        top_edge_keys = ranked[:sub_count]

        sub_edges = [
            EdgeRef(
                source_type=k_edge[0],
                relation_type=k_edge[1],
                target_type=k_edge[2],
                source_id=k_edge[3],
                target_id=k_edge[4],
            )
            for k_edge in top_edge_keys
        ]
        sub_endpoints = sorted(
            {(k_edge[0], k_edge[3]) for k_edge in top_edge_keys}
            | {(k_edge[2], k_edge[4]) for k_edge in top_edge_keys}
        )
        sub_nodes = [NodeRef(node_type=t, node_id=i) for t, i in sub_endpoints]

        subgraph = Subgraph(
            k=k,
            selection="top_k_edges_by_importance",
            tie_break="lexicographic_edge_key",
            nodes=sub_nodes,
            edges=sub_edges,
        )

        # Advertencias obligatorias (EXP-08)
        warnings = [
            Warning_(
                code="association_not_causation",
                message=WARNING_MESSAGES["association_not_causation"],
            ),
            Warning_(
                code="importance_is_not_evidence",
                message=WARNING_MESSAGES["importance_is_not_evidence"],
            ),
        ]
        if is_synthetic:
            warnings.append(
                Warning_(code=SYNTHETIC_WARNING, message=WARNING_MESSAGES["synthetic_data"])
            )
        if uses_attention:
            warnings.append(
                Warning_(
                    code=ATTENTION_WARNING, message=WARNING_MESSAGES["attention_is_not_explanation"]
                )
            )

        # Trazabilidad de corrida: sin `run`, solo se admite la referencia sintética de ejemplo
        if run_ref is None:
            run_ref = self._synthetic_run_ref()

        # Ensamblado del artefacto final
        payload: dict[str, Any] = {
            "format": EXPLANATION_FORMAT,
            "format_version": EXPLANATION_FORMAT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "run": run_ref.model_dump(),
            "explainer": ExplainerRef(
                name=alg_name,
                library="torch_geometric",
                library_version=torch_geometric.__version__,
                algorithm=alg_path,
                explanation_type=self.config.explanation_type,
                node_mask_type=self.config.node_mask_type,
                edge_mask_type=self.config.edge_mask_type,
                seed=self.config.seed,
                config=alg_cfg,
                uses_attention=uses_attention,
            ).model_dump(),
            "target": TargetRef(
                graph_id=str(graph_id),
                sample_id=str(sample_id) if sample_id is not None else None,
                is_synthetic=is_synthetic,
                output=target_name,
                output_index=target_index,
                unit=unit,
                model_output=round(model_output, 4),
            ).model_dump(),
            "importance": Importance(
                scale=Scale(
                    kind="normalized",
                    range=(0.0, 1.0),
                    normalization="max_abs",
                    aggregation=(
                        "sum_over_feature_mask"
                        if self.config.node_mask_type == "attributes"
                        else "node_mask_object"
                    ),
                ),
                nodes=nodes,
                attributes=attributes,
                edges=edges,
            ).model_dump(),
            "subgraph": subgraph.model_dump(),
            "warnings": [w.model_dump() for w in warnings],
        }

        return validate_explanation(payload)

    def _feature_names(self, data: HeteroData, node_type: str, count: int) -> list[str]:
        if node_type in self.node_feature_names:
            names = list(self.node_feature_names[node_type])
            if len(names) >= count:
                return names[:count]
        # Búsqueda en metadata del dataset si existe
        schema = getattr(data, "node_feature_schema", None)
        if isinstance(schema, Mapping) and node_type in schema:
            cols = schema[node_type]
            names = [
                col.get("name", str(col)) if isinstance(col, dict) else str(col) for col in cols
            ]
            if len(names) >= count:
                return names[:count]
        return [f"{node_type}_col_{i}" for i in range(count)]

    def _synthetic_run_ref(self) -> RunRef:
        """Referencia de ejemplo para grafos sintéticos sin corrida registrada.

        El `sha256` en ceros indica que no hay partición versionada; nunca se usa con datos
        reales, para los que `explain` exige `run`.
        """
        variant = self._model_variant()
        return RunRef(
            run_id=f"run_{variant}_s{self.config.seed}",
            run_json=f"runs/run_{variant}_s{self.config.seed}/run.json",
            format_version="1.0.0",
            variant=str(variant),
            seed=self.config.seed,
            dataset_id="synthetic-v1",
            split=SplitRef(version="synthetic", sha256="0" * 64),
            git_commit=None,
        )


__all__ = [
    "DEFAULT_MODEL_CONFIG",
    "HeteroAdapter",
    "HeteroExplainer",
    "HeteroExplainerConfig",
    "IncompatibleExplainerError",
    "edge_mask_effect",
    "edge_mask_reach",
    "explained_inputs",
]
