"""Tests unitarios para las funciones de análisis y reporte de explicabilidad (A71-P2, A71-P3)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from nutrigraphdt.explainability.analysis import (
    StabilityRow,
    build_stability_rows,
    collect_top_k_elements,
    generate_explainability_report,
    parse_outputs_argument,
    write_stability_csv,
    write_top_k_csv,
)
from nutrigraphdt.explainability.contract import (
    EdgeImportance,
    EdgeRef,
    Evidence,
    ExplainerRef,
    Explanation,
    Importance,
    NodeRef,
    RunRef,
    Scale,
    SplitRef,
    Subgraph,
    TargetRef,
)
from nutrigraphdt.explainability.criteria import StabilityReport
from nutrigraphdt.explainability.out_of_fold import AnimalExplanations, OutOfFoldPlan


def _dummy_run_ref() -> RunRef:
    return RunRef(
        run_id="run_0",
        run_json="runs/d1/run_0/run.json",
        format_version="1.0.0",
        variant="hetero_sage",
        seed=0,
        dataset_id="d1",
        split=SplitRef(version="1.0.0", sha256="0" * 64),
        git_commit="a" * 40,
    )


def _dummy_explanation(sample_id: str, output: str, seed: int) -> Explanation:
    return Explanation(
        format="nutrigraphdt-explanation",
        format_version="2.0.0",
        created_at="2026-11-08T00:00:00Z",
        run=_dummy_run_ref(),
        explainer=ExplainerRef(
            name="EdgeGradientSaliency",
            library="nutrigraphdt",
            library_version="2.0.0",
            algorithm="edge_saliency",
            explanation_type="model",
            node_mask_type=None,
            edge_mask_type="object",
            seed=seed,
            config={},
        ),
        target=TargetRef(
            graph_id=sample_id,
            sample_id=sample_id,
            is_synthetic=False,
            output=output,
            output_index=0,
            unit="log_ratio",
            model_output=1.23,
        ),
        importance=Importance(
            scale=Scale(
                kind="normalized",
                range=(0.0, 1.0),
                normalization="max_abs",
                aggregation="mean",
            ),
            nodes=[],
            attributes=[],
            edges=[
                EdgeImportance(
                    source_type="taxon",
                    relation_type="has_capacity",
                    target_type="function",
                    source_id="Prevotella",
                    target_id="ko:K00932",
                    importance=0.8,
                    evidence=Evidence(
                        evidence_status="annotated",
                        evidence_method="kegg",
                        evidence_source=None,
                    ),
                )
            ],
        ),
        subgraph=Subgraph(
            k=1,
            selection="top_k_edges_by_abs_importance",
            tie_break="lexicographic_edge_key",
            nodes=[
                NodeRef(node_type="taxon", node_id="Prevotella"),
                NodeRef(node_type="function", node_id="ko:K00932"),
            ],
            edges=[
                EdgeRef(
                    source_type="taxon",
                    relation_type="has_capacity",
                    target_type="function",
                    source_id="Prevotella",
                    target_id="ko:K00932",
                )
            ],
        ),
        warnings=[],
    )


def _dummy_stability_report(exp0: Explanation, exp1: Explanation | None = None) -> StabilityReport:
    """Construye un StabilityReport con la API real (ci_low, ci_high, d, kendall_mean, unstable)."""
    exps: tuple[Explanation, ...] = (exp0,) if exp1 is None else (exp0, exp1)
    return StabilityReport(
        seeds=tuple(range(len(exps))),
        explanations=exps,
        phi=0.85,
        ci_low=0.70,
        ci_high=0.95,
        k=1,
        d=5,
        kendall_mean=0.80,
        unstable=False,
    )


def _dummy_plan() -> OutOfFoldPlan:
    """Plan mínimo con un animal y una semilla."""
    return OutOfFoldPlan(
        seeds=(0,),
        assignments={"A1": {}},
        missing={"A1": ()},
    )


def test_parse_outputs_argument() -> None:
    assert parse_outputs_argument(["propionate", "butyrate"]) == (
        "log_propionate_acetate",
        "log_butyrate_acetate",
    )
    assert parse_outputs_argument(["log_butyrate_acetate"]) == ("log_butyrate_acetate",)
    with pytest.raises(ValueError, match="no reconocidas"):
        parse_outputs_argument(["invalid_target"])


def test_build_stability_rows() -> None:
    exp0 = _dummy_explanation("A1", "log_butyrate_acetate", 0)
    exp1 = _dummy_explanation("A1", "log_butyrate_acetate", 1)

    rep0 = _dummy_stability_report(exp0, exp1)
    # plan_phi < INSTABILITY_THRESHOLD (0.40) → animal inestable por plan
    animal = AnimalExplanations(
        sample_id="A1",
        output="log_butyrate_acetate",
        by_seed={0: rep0},
        missing_seeds=(),
        plan_phi=0.35,
        plan_ci=(0.20, 0.50),
    )

    rows = build_stability_rows([animal])
    assert len(rows) == 1
    row = rows[0]
    assert row.sample_id == "A1"
    assert row.output == "log_butyrate_acetate"
    assert row.plan_phi == pytest.approx(0.35, abs=1e-4)
    # rep0.unstable=False → 0 seeds inestables
    assert row.unstable_seeds_count == 0


def test_write_stability_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "stability.csv"
    row = StabilityRow(
        sample_id="A1",
        output="log_butyrate_acetate",
        k=1,
        d=5,
        explainer_phi_mean=0.75,
        explainer_ci_low_mean=0.60,
        explainer_ci_high_mean=0.90,
        kendall_mean=0.80,
        unstable_seeds_count=0,
        plan_phi=0.80,
        plan_ci_low=0.70,
        plan_ci_high=0.90,
        total_seeds=2,
        missing_seeds="",
    )
    write_stability_csv(csv_file, [row])
    assert csv_file.exists()

    with open(csv_file, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 1
    assert reader[0]["sample_id"] == "A1"
    assert reader[0]["unstable_seeds_count"] == "0"


def test_collect_top_k_elements_and_write_csv(tmp_path: Path) -> None:
    exp0 = _dummy_explanation("A1", "log_butyrate_acetate", 0)
    rep0 = StabilityReport(
        seeds=(0,),
        explanations=(exp0,),
        phi=1.0,
        ci_low=1.0,
        ci_high=1.0,
        k=1,
        d=1,
        kendall_mean=float("nan"),
        unstable=False,
    )
    animal = AnimalExplanations(
        sample_id="A1",
        output="log_butyrate_acetate",
        by_seed={0: rep0},
        missing_seeds=(),
        plan_phi=1.0,
        plan_ci=(1.0, 1.0),
    )

    rows = collect_top_k_elements([animal])
    assert len(rows) >= 1  # al menos la arista Prevotella->ko:K00932
    csv_file = tmp_path / "top_k_elements.csv"
    write_top_k_csv(csv_file, rows)
    assert csv_file.exists()


def test_generate_explainability_report(tmp_path: Path) -> None:
    exp0 = _dummy_explanation("A1", "log_butyrate_acetate", 0)
    rep0 = StabilityReport(
        seeds=(0,),
        explanations=(exp0,),
        phi=1.0,
        ci_low=1.0,
        ci_high=1.0,
        k=1,
        d=1,
        kendall_mean=float("nan"),
        unstable=False,
    )
    animal = AnimalExplanations(
        sample_id="A1",
        output="log_butyrate_acetate",
        by_seed={0: rep0},
        missing_seeds=(),
        plan_phi=0.80,
        plan_ci=(0.70, 0.90),
    )
    plan = _dummy_plan()
    report_md = tmp_path / "report.md"

    content = generate_explainability_report(
        [animal],
        plan,
        variant="hetero_sage",
        edges_arm="free",
        top_k=5,
    )
    report_md.write_text(content, encoding="utf-8")

    assert report_md.exists()
    assert "asociación ≠ causalidad" in content or "asociaciones aprendidas" in content
    assert "Estructura funcional anotada, no mecanística" in content
    assert "El modelo explicado no supera a los modelos tabulares" in content
    assert "Cómo leer el top-k" in content
    assert "Bajo soporte del propionato" in content
    assert "0,40" in content


def test_top_k_composition_counts_fixed_and_off_target_edges() -> None:
    from nutrigraphdt.explainability.analysis import TopKElementRow, top_k_composition

    out = "log_butyrate_acetate"
    rows = [
        TopKElementRow(
            out,
            "edge",
            "(function:ko:K1) -[produces]-> (metabolite:propionate)",
            3,
            0.3,
            "annotated",
        ),
        TopKElementRow(
            out, "edge", "(function:ko:K2) -[produces]-> (metabolite:butyrate)", 1, 0.1, "annotated"
        ),
        TopKElementRow(
            out, "edge", "(taxon:g__A) -[has_capacity]-> (function:ko:K2)", 4, 0.4, "annotated"
        ),
        TopKElementRow(out, "taxon", "g__A", 4, 0.4, "annotated"),
        TopKElementRow("log_propionate_acetate", "taxon", "g__B", 9, 0.9, "annotated"),
    ]

    composition = top_k_composition(rows, out)

    assert composition.edge_appearances == 8
    assert composition.share("produces") == pytest.approx(0.5)
    assert composition.share("has_capacity") == pytest.approx(0.5)
    assert composition.share("measured_in") == 0.0
    assert composition.off_target_produces_share == pytest.approx(0.75)
    assert composition.taxon_appearances == 4
