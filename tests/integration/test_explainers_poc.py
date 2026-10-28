"""Prueba de concepto de explicadores de PyG sobre los modelos heterogéneos (#157).

Ejecuta `scripts/explainers_poc.py` con pocas épocas y comprueba que:

- existe al menos una ruta compatible (máscaras de atributos y de aristas sobre los modelos
  heterogéneos);
- las combinaciones incompatibles fallan de forma explícita o se marcan como no válidas, en vez
  de entregar valores silenciosos (máscaras de aristas en `homo_sage`);
- el reporte distingue importancia de nodos, atributos y aristas y advierte que asociación no
  implica causalidad.

Requiere el extra `graph`; Captum es opcional.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch_geometric")

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "explainers_poc_script", REPO_ROOT / "scripts" / "explainers_poc.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE  # `dataclass` busca el módulo en `sys.modules`
_SPEC.loader.exec_module(_MODULE)

CAPTUM = importlib.util.find_spec("captum") is not None


@pytest.fixture(scope="module")
def output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("explainers_poc")
    assert _MODULE.main(["--explainer-epochs", "3", "--output", str(path)]) == 0
    return path


@pytest.fixture(scope="module")
def report(output: Path) -> dict[str, Any]:
    return dict(json.loads((output / "explainers_poc.json").read_text(encoding="utf-8")))


def _results(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (variant["variant"], result["method"]): result
        for variant in report["variants"]
        for result in variant["results"]
    }


def _variant(report: dict[str, Any], name: str) -> dict[str, Any]:
    return dict(next(v for v in report["variants"] if v["variant"] == name))


def test_report_records_versions_and_configuration(report: dict[str, Any]) -> None:
    assert report["issue"] == "#157"
    assert report["target"]["model"] == "sin entrenar"
    assert report["target"]["graph_id"].startswith("synthetic:")
    assert report["explainer_epochs"] == 3
    assert {"python", "torch", "torch_geometric", "captum"} <= set(report["versions"])
    assert [v["variant"] for v in report["variants"]] == list(_MODULE.VARIANTS)


@pytest.mark.parametrize("variant", ["hetero_sage", "hetero_gat"])
def test_gnnexplainer_gives_attribute_and_edge_masks_on_hetero_models(
    report: dict[str, Any], variant: str
) -> None:
    result = _results(report)[(variant, "GNNExplainer")]
    assert result["status"] == "ok"
    data = _variant(report, variant)
    assert data["edge_mask_layers_reached"] > 0
    assert data["edge_mask_effect"] > 0
    # Atributos: [nodos, columnas] por tipo explicado; aristas: [aristas] por tripleta.
    assert set(result["node_mask_shapes"]) == set(data["explained_node_types"])
    assert all(len(shape) == 2 for shape in result["node_mask_shapes"].values())
    assert set(result["edge_mask_shapes"]) == {"|".join(et) for et in data["explained_edge_types"]}
    assert all(len(shape) == 1 for shape in result["edge_mask_shapes"].values())


def test_node_and_attribute_routes_work_on_every_variant(report: dict[str, Any]) -> None:
    results = _results(report)
    for variant in _MODULE.VARIANTS:
        attributes = results[(variant, "GNNExplainer (solo atributos)")]
        nodes = results[(variant, "GNNExplainer (solo nodos)")]
        assert attributes["status"] == nodes["status"] == "ok"
        assert attributes["edge_mask_shapes"] == nodes["edge_mask_shapes"] == {}
        # Atributos: una columna por atributo de x; nodos: una sola columna por nodo.
        assert {shape[1] for shape in nodes["node_mask_shapes"].values()} == {1}
        assert any(shape[1] > 1 for shape in attributes["node_mask_shapes"].values())


def test_edge_masks_on_homogeneous_variant_are_never_accepted(report: dict[str, Any]) -> None:
    data = _variant(report, "homo_sage")
    assert data["edge_mask_layers_reached"] == 0
    results = _results(report)
    edge_methods = [r for (v, _), r in results.items() if v == "homo_sage" and r["edge_mask_type"]]
    assert edge_methods
    assert not [r for r in edge_methods if r["status"] == "ok"]
    assert results[("homo_sage", "GNNExplainer")]["status"] == "error"
    assert results[("homo_sage", "PGExplainer")]["status"] == "invalid"


def test_attention_is_only_available_on_attention_layers(report: dict[str, Any]) -> None:
    results = _results(report)
    assert results[("hetero_gat", "AttentionExplainer")]["status"] == "ok"
    assert results[("hetero_sage", "AttentionExplainer")]["status"] != "ok"
    assert results[("homo_sage", "AttentionExplainer")]["status"] == "error"


def test_captum_is_optional(report: dict[str, Any]) -> None:
    results = _results(report)
    captum = [r for (_, m), r in results.items() if m.startswith("Captum")]
    if CAPTUM:
        assert results[("hetero_sage", "Captum IntegratedGradients")]["status"] == "ok"
    else:
        assert {r["status"] for r in captum} == {"not_available"}


def test_edge_types_without_convolution_do_not_change_prediction(report: dict[str, Any]) -> None:
    for variant in report["variants"]:
        assert variant["skipped_edges_do_not_change_prediction"] is True
        skipped = {tuple(et) for et in variant["skipped_edge_types"]}
        assert not skipped & {tuple(et) for et in variant["explained_edge_types"]}


def test_markdown_distinguishes_masks_and_warns(output: Path) -> None:
    text = (output / "explainers_poc.md").read_text(encoding="utf-8")
    for phrase in (
        "Importancia de atributos",
        "Importancia de nodos",
        "Importancia de aristas",
        "no causalidad",
        "no se interpretan como explicación",
        "sintéticos",
    ):
        assert phrase in text
