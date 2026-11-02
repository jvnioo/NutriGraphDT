"""Reglas de la respuesta de Investigación a A55 en el explicador sobre grafos de D1 (#240, #242).

Usa el fixture real de seis animales (`tests/fixtures/holofood/`): sus grafos tienen los taxones
aislados, como D1 mientras falte S-04. El modelo no está entrenado; estas pruebas comprueban las
reglas del wrapper y del contrato 2.0.0, no la calidad de una explicación. Requiere el extra
`graph`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from torch_geometric.data import HeteroData  # noqa: E402

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.explainability import (  # noqa: E402
    HeteroExplainer,
    IncompatibleExplainerError,
    RunRef,
    SplitRef,
    explain_across_seeds,
)
from nutrigraphdt.explainability.wrapper import has_isolated_taxa  # noqa: E402
from nutrigraphdt.graph.builder import add_reverse_edges, build_hetero_graph  # noqa: E402
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES  # noqa: E402
from nutrigraphdt.models.gnn.base import GraphMetadata  # noqa: E402
from nutrigraphdt.models.gnn.factory import build_model, load_model_config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN = RunRef(
    run_id="20261102-000000_hetero_sage_free_s0_f0",
    run_json="runs/constraints/d1/20261102-000000_hetero_sage_free_s0_f0/run.json",
    format_version="1.0.0",
    variant="hetero_sage",
    seed=42000,
    dataset_id="D1_holofood",
    split=SplitRef(version="1.0.0", sha256="a" * 64),
    git_commit=None,
)
D1_WARNINGS = {
    "diet_day_confounding",
    "exploratory_treatment_contrast",
    "model_not_better_than_day_only",
    "isolated_taxa_pending_s04",
}


@pytest.fixture
def graphs(holofood_fixture_sources: Path) -> dict[str, HeteroData]:
    sources = load_sources(holofood_fixture_sources)
    tables = DataPipeline({"D1_holofood": sources["D1_holofood"]}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(sources["D1_holofood_metadata"]).load(),
        metabolites=MetaboliteLoader(sources["D1_holofood_scfa_content"]).load(),
    )
    built = build_hetero_graph(tables).graphs
    return {graph_id: add_reverse_edges(graph) for graph_id, graph in built.items()}


def _model(graphs: dict[str, HeteroData]) -> Any:
    torch.manual_seed(0)
    config = load_model_config(REPO_ROOT / "configs" / "models" / "hetero_sage.yaml")
    metadata = GraphMetadata.from_graphs(list(graphs.values()))
    return build_model(config, metadata, target_names=MODEL_OUTPUT_NAMES).eval()


def _graph(graphs: dict[str, HeteroData], diet: str) -> HeteroData:
    return next(g for g in graphs.values() if str(g.diet_treatment) == diet)


def _attributes_explainer(model: Any, **kwargs: Any) -> HeteroExplainer:
    return HeteroExplainer(
        model, node_mask_type="attributes", edge_mask_type=None, epochs=2, top_k=5, **kwargs
    )


def test_d1_graphs_have_isolated_taxa(graphs: dict[str, HeteroData]) -> None:
    assert all(has_isolated_taxa(graph) for graph in graphs.values())


def test_d1_explanation_carries_the_c02_warnings(graphs: dict[str, HeteroData]) -> None:
    model = _model(graphs)
    control = _attributes_explainer(model).explain(_graph(graphs, "Control"), run=RUN, target=0)
    codes = {w.code for w in control.warnings}
    assert codes >= D1_WARNINGS | {"explainer_not_validated"}
    assert "insufficient_group_size" not in codes
    assert not control.importance.edges  # C-06: en D1 solo atributos

    phyto = _attributes_explainer(model).explain(_graph(graphs, "Prebiotic"), run=RUN, target=0)
    assert "insufficient_group_size" in {w.code for w in phyto.warnings}


def test_beating_day_only_removes_that_warning(graphs: dict[str, HeteroData]) -> None:
    explanation = _attributes_explainer(_model(graphs), beats_day_only=True).explain(
        _graph(graphs, "Control"), run=RUN, target=0
    )
    assert "model_not_better_than_day_only" not in {w.code for w in explanation.warnings}


def test_edges_are_refused_while_taxa_are_isolated(graphs: dict[str, HeteroData]) -> None:
    explainer = HeteroExplainer(_model(graphs), edge_mask_type="object", epochs=2)
    with pytest.raises(IncompatibleExplainerError, match="C-06"):
        explainer.explain(_graph(graphs, "Control"), run=RUN, target=0)


def test_only_explainable_outputs_are_explained(graphs: dict[str, HeteroData]) -> None:
    explainer = _attributes_explainer(_model(graphs), explainable_outputs=MODEL_OUTPUT_NAMES[:2])
    graph = _graph(graphs, "Control")
    explainer.explain(graph, run=RUN, target="log_propionate_acetate")
    with pytest.raises(ValueError, match="C-04"):
        explainer.explain(graph, run=RUN, target="log_total")


def test_stability_across_explainer_seeds(graphs: dict[str, HeteroData]) -> None:
    model = _model(graphs)
    graph = _graph(graphs, "Control")
    report = explain_across_seeds(
        lambda seed: _attributes_explainer(model, seed=seed).explain(graph, run=RUN, target=0),
        seeds=range(5),
    )
    assert len(report.explanations) == 5
    assert report.ci_low <= report.phi <= report.ci_high
    codes = {w.code for w in report.explanations[0].warnings}
    assert ("explainer_instability" in codes) == report.unstable
    with pytest.raises(ValueError, match="al menos 5"):
        explain_across_seeds(lambda seed: report.explanations[0], seeds=range(4))
