"""Tests del contrato de salida de las explicaciones (A55-P3, #156)."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from nutrigraphdt.data.synthetic import generate_synthetic_dataset
from nutrigraphdt.explainability import (
    EXPLANATION_FORMAT_VERSION,
    ExplanationContractError,
    validate_explanation,
)
from nutrigraphdt.models.composition import MODEL_OUTPUT_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "docs" / "models" / "examples" / "explanation-synthetic.json"
DOCUMENT = REPO_ROOT / "docs" / "models" / "explanation-contract.md"
Record = dict[str, Any]


@pytest.fixture
def example() -> Record:
    data: Record = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return data


def _problems(data: Record) -> list[str]:
    with pytest.raises(ExplanationContractError) as error:
        validate_explanation(data)
    return error.value.problems


# ---------------------------------------------------------------------------
# El ejemplo versionado
# ---------------------------------------------------------------------------


def test_example_is_valid(example: Record) -> None:
    explanation = validate_explanation(example)
    assert explanation.format_version == EXPLANATION_FORMAT_VERSION
    assert explanation.target.output in MODEL_OUTPUT_NAMES
    assert explanation.target.output_index == MODEL_OUTPUT_NAMES.index(explanation.target.output)


def test_example_matches_the_synthetic_generator(example: Record) -> None:
    """Identificadores, aristas y evidencia del ejemplo son los del dataset sintético."""
    dataset = generate_synthetic_dataset()
    nodes = {(n.node_type, n.node_id) for n in dataset.nodes}
    edges = {
        (e.source_type, e.relation_type, e.target_type, e.source_id, e.target_id): e
        for e in dataset.edges
    }
    assert example["target"]["graph_id"] == dataset.instances[0].graph_id
    assert example["run"]["dataset_id"] == dataset.metadata["dataset_id"]
    for node in example["importance"]["nodes"]:
        assert (node["node_type"], node["node_id"]) in nodes
    for edge in example["importance"]["edges"]:
        key = tuple(edge[k] for k in ("source_type", "relation_type", "target_type"))
        key += (edge["source_id"], edge["target_id"])
        if edge["relation_type"].startswith("rev_"):
            assert edge["evidence"] is None
            continue
        record = edges[key]  # type: ignore[index]
        assert edge["evidence"]["evidence_status"] == record.evidence_status
        assert edge["evidence"]["evidence_method"] == record.evidence_method


def test_example_separates_evidence_from_importance_and_has_no_raw_data(example: Record) -> None:
    text = EXAMPLE.read_text(encoding="utf-8")
    for forbidden in ("raw_attributes", '"x"', "/home/", "C:\\\\", "SAMEA"):
        assert forbidden not in text
    for edge in example["importance"]["edges"]:
        assert "importance" not in (edge["evidence"] or {})
    codes = {w["code"] for w in example["warnings"]}
    assert {"association_not_causation", "importance_is_not_evidence", "synthetic_data"} <= codes


def test_document_links_the_example_and_is_linked_from_docs() -> None:
    document = DOCUMENT.read_text(encoding="utf-8")
    assert "examples/explanation-synthetic.json" in document
    for rule in (f"EXP-{i:02d}" for i in range(1, 11)):
        assert rule in document
    index = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "models/explanation-contract.md" in index


# ---------------------------------------------------------------------------
# Reglas EXP-01 a EXP-10
# ---------------------------------------------------------------------------

Mutation = Callable[[Record], object]


def _edge(data: Record, index: int = 0) -> Record:
    edge: Record = data["importance"]["edges"][index]
    return edge


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        (lambda d: d.update(format_version="1.0.0"), "EXP-01"),
        (lambda d: d["importance"]["nodes"][0].update(raw_attributes={"abundance": 1}), "EXP-01"),
        (lambda d: d["run"].update(run_json="/home/user/runs/run.json"), "EXP-01"),
        (lambda d: d["run"]["split"].update(sha256="abc"), "EXP-01"),
        (lambda d: d.pop("warnings"), "EXP-01"),
        (lambda d: d["importance"]["nodes"][0].update(importance=1.5), "EXP-02"),
        (lambda d: d["importance"]["scale"].update(range=[0.0, 10.0]), "EXP-02"),
        (lambda d: d["importance"]["nodes"][0].update(node_type="enzyme"), "EXP-03"),
        (lambda d: _edge(d).update(relation_type="feeds"), "EXP-03"),
        (lambda d: d["importance"]["nodes"].append(d["importance"]["nodes"][0]), "EXP-04"),
        (
            lambda d: d["importance"]["attributes"][0].update(node_id="synthetic:taxon:0009"),
            "EXP-05",
        ),
        (lambda d: _edge(d).update(evidence=None), "EXP-01"),
        (lambda d: _edge(d)["evidence"].update(evidence_method="measurement"), "EXP-06"),
        (
            lambda d: _edge(d)["evidence"].update(
                evidence_status="observed", evidence_method="measurement"
            ),
            "EXP-06",
        ),
        (lambda d: d["subgraph"].update(k=2), "EXP-07"),
        (lambda d: d["subgraph"]["nodes"].pop(), "EXP-07"),
        (lambda d: d["subgraph"]["edges"].__setitem__(0, _ref(_edge(d, 6))), "EXP-07"),
        (lambda d: d["subgraph"]["edges"].pop(), "EXP-07"),
        (lambda d: d["warnings"].pop(0), "EXP-08"),
        (lambda d: d["explainer"].update(uses_attention=True), "EXP-08"),
        (lambda d: d["target"].update(is_synthetic=False), "EXP-09"),
    ],
    ids=[
        "other-version",
        "extra-raw-field",
        "absolute-run-path",
        "bad-sha256",
        "no-warnings",
        "importance-out-of-range",
        "normalized-wrong-range",
        "unknown-node-type",
        "unknown-relation",
        "repeated-node",
        "attribute-of-unlisted-node",
        "edge-without-evidence",
        "method-not-supporting-status",
        "real-evidence-in-synthetic",
        "more-edges-than-k",
        "subgraph-node-missing",
        "subgraph-not-top-k",
        "subgraph-fewer-than-k",
        "missing-causality-warning",
        "attention-without-warning",
        "synthetic-flag-mismatch",
    ],
)
def test_each_rule_rejects_its_defect(example: Record, mutate: Mutation, rule: str) -> None:
    data = copy.deepcopy(example)
    mutate(data)
    problems = _problems(data)
    assert any(problem.startswith(rule) for problem in problems), problems


def _ref(edge: Record) -> Record:
    return {k: edge[k] for k in ("source_type", "relation_type", "target_type")} | {
        "source_id": edge["source_id"],
        "target_id": edge["target_id"],
    }


def test_ties_are_broken_by_the_lexicographic_edge_key(example: Record) -> None:
    data = copy.deepcopy(example)
    edges = data["importance"]["edges"]
    for edge in edges:
        edge["importance"] = 0.5
    ranked = sorted(
        edges,
        key=lambda e: (
            e["source_type"],
            e["relation_type"],
            e["target_type"],
            e["source_id"],
            e["target_id"],
        ),
    )[: data["subgraph"]["k"]]
    data["subgraph"]["edges"] = [_ref(e) for e in ranked]
    ends = {(e["source_type"], e["source_id"]) for e in ranked} | {
        (e["target_type"], e["target_id"]) for e in ranked
    }
    data["subgraph"]["nodes"] = [{"node_type": t, "node_id": i} for t, i in sorted(ends)]
    validate_explanation(data)

    data["subgraph"]["edges"][0] = _ref(sorted(edges, key=lambda e: e["target_id"])[-1])
    assert any(p.startswith("EXP-07") for p in _problems(data))


def test_reverse_relations_are_not_listed(example: Record) -> None:
    """C-09: una relación inversa se suma a su arista directa; listarla es un error."""
    assert not any(e["relation_type"].startswith("rev_") for e in example["importance"]["edges"])
    data = copy.deepcopy(example)
    direct = _edge(data, 3)
    data["importance"]["edges"].append(
        {
            "source_type": direct["target_type"],
            "relation_type": "rev_" + direct["relation_type"],
            "target_type": direct["source_type"],
            "source_id": direct["target_id"],
            "target_id": direct["source_id"],
            "importance": 0.0,
            "evidence": direct["evidence"],
        }
    )
    assert any(p.startswith("EXP-03") and "inversa" in p for p in _problems(data))


def test_signed_scale_requires_max_abs(example: Record) -> None:
    """C-01: una escala con signo se normaliza con max_abs."""
    data = copy.deepcopy(example)
    data["importance"]["scale"].update(range=[-1.0, 1.0], normalization="sum_to_one")
    assert any(p.startswith("EXP-02") and "max_abs" in p for p in _problems(data))
    data["importance"]["scale"]["normalization"] = "max_abs"
    validate_explanation(data)


def test_integrated_gradients_declares_its_baseline(example: Record) -> None:
    """C-01: la línea base de IntegratedGradients queda en explainer.config (EXP-10)."""
    data = copy.deepcopy(example)
    data["explainer"].update(name="Captum IntegratedGradients", config={"method": "IG"})
    assert any(p.startswith("EXP-10") for p in _problems(data))
    data["explainer"]["config"]["baseline"] = "zeros"
    validate_explanation(data)


def _as_d1(data: Record) -> None:
    data["target"].update(is_synthetic=False, graph_id="D1_holofood:SAMEA0000000")
    data["run"]["dataset_id"] = "D1_holofood"
    for edge in data["importance"]["edges"]:
        edge["evidence"] = {
            "evidence_status": "observed",
            "evidence_method": "measurement",
            "evidence_source": None,
        }


def test_d1_explanation_requires_the_c02_warnings(example: Record) -> None:
    data = copy.deepcopy(example)
    _as_d1(data)
    problem = next(p for p in _problems(data) if p.startswith("EXP-08"))
    assert "diet_day_confounding" in problem and "exploratory_treatment_contrast" in problem


def test_isolated_taxa_require_their_warning(example: Record) -> None:
    """C-02: con taxones y sin aristas que los toquen, falta `isolated_taxa_pending_s04`."""
    data = copy.deepcopy(example)
    _as_d1(data)
    kept = [
        e
        for e in data["importance"]["edges"]
        if "taxon" not in (e["source_type"], e["target_type"])
    ]
    data["importance"]["edges"] = kept
    scores = {tuple(_ref(e).values()): e["importance"] for e in kept}
    top = sorted(scores, key=lambda key: (-abs(scores[key]), key))[: data["subgraph"]["k"]]
    data["subgraph"]["edges"] = [
        dict(
            zip(
                ("source_type", "relation_type", "target_type", "source_id", "target_id"),
                key,
                strict=True,
            )
        )
        for key in top
    ]
    ends = {(key[0], key[3]) for key in top} | {(key[2], key[4]) for key in top}
    data["subgraph"]["nodes"] = [{"node_type": t, "node_id": i} for t, i in sorted(ends)]
    data["warnings"] += [
        {"code": "diet_day_confounding", "message": "m"},
        {"code": "exploratory_treatment_contrast", "message": "m"},
    ]
    assert any("isolated_taxa_pending_s04" in p for p in _problems(data))
    data["warnings"].append({"code": "isolated_taxa_pending_s04", "message": "m"})
    validate_explanation(data)


def test_all_problems_are_reported_together(example: Record) -> None:
    data = copy.deepcopy(example)
    data["importance"]["nodes"][0]["importance"] = 2.0
    data["warnings"] = data["warnings"][2:]
    data["target"]["is_synthetic"] = False
    rules = {problem.split(":")[0] for problem in _problems(data)}
    assert {"EXP-02", "EXP-08", "EXP-09"} <= rules
