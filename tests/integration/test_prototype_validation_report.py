"""Validación del prototipo sintético y su reporte (A35-2, #29).

Genera el prototipo con `scripts/generate_synthetic_dataset.py --graphs`, lo valida con
`scripts/validate_graph.py --graphs` como procesos independientes y comprueba:

- que las cifras de `docs/graph/prototype-validation-report.md` coinciden con el resultado actual,
para
  que el reporte no quede desactualizado si cambian las reglas o los datos;
- los códigos de salida frente a grafos válidos, con defectos tensoriales, manipulados, ausentes
  o de otro dataset.

Requiere el extra `graph`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.synthetic import OutputRecord  # noqa: E402
from nutrigraphdt.graph.heterodata import MANIFEST_FILE, load_graphs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DOC = REPO_ROOT / "docs" / "graph" / "prototype-validation-report.md"
GENERATE_SCRIPT = REPO_ROOT / "scripts" / "generate_synthetic_dataset.py"
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "validate_graph.py"


def _run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


@pytest.fixture(scope="module")
def prototype(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("prototype") / "v1"
    generated = _run(GENERATE_SCRIPT, "--output", output, "--graphs")
    assert generated.returncode == 0, generated.stdout + generated.stderr
    return output


def _graph_file(prototype: Path, graph_id: str) -> Path:
    manifest = json.loads((prototype / "graphs" / MANIFEST_FILE).read_text(encoding="utf-8"))
    entry = next(item for item in manifest["graphs"] if item["graph_id"] == graph_id)
    return prototype / "graphs" / entry["file"]


def _copy_prototype(prototype: Path, destination: Path) -> Path:
    import shutil

    shutil.copytree(prototype, destination)
    return destination


# ---------------------------------------------------------------------------
# El reporte refleja el resultado actual
# ---------------------------------------------------------------------------


def test_report_figures_match_the_current_validation(prototype: Path, tmp_path: Path) -> None:
    report_path = tmp_path / "prototype.json"
    validated = _run(VALIDATE_SCRIPT, "--input", prototype, "--graphs", "--report", report_path)
    assert validated.returncode == 0, validated.stdout + validated.stderr
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    counts = json.loads((prototype / "metadata.json").read_text(encoding="utf-8"))["counts"]
    doc = REPORT_DOC.read_text(encoding="utf-8")

    assert f"(graph-integrity-rules.md), versión `{report['rules_version']}`." in doc
    assert f"| Estado | {report['status']} |" in doc
    assert f"| Familias evaluadas | {', '.join(report['evaluated'])} |" in doc
    assert report["not_evaluated"] == {}
    assert "| Familias no evaluadas | ninguna |" in doc
    for severity, count in report["summary"].items():
        assert f"| {severity} | {count} |" in doc
    deliverable = sum(graph["deliverable"] for graph in report["graphs"].values())
    assert f"| Grafos entregables | {deliverable} de {len(report['graphs'])} |" in doc

    for graph_id, graph in report["graphs"].items():
        declared = counts[graph_id]
        row = (
            f"| `{graph_id}` | {sum(declared['nodes'].values())} | "
            f"{sum(declared['edges'].values())} | {declared['outputs']} | {graph['ERROR']} | "
            f"{graph['ADVERTENCIA']} | {'sí' if graph['deliverable'] else 'no'} |"
        )
        assert row in doc, row

    rule_table = doc.split("| Regla | Severidad | Hallazgos |", 1)[1].split("\n\n", 1)[0]
    rows = [line for line in rule_table.splitlines() if line.startswith("| ") and "---" not in line]
    assert len(rows) == len(report["rules"])
    for rule_id, entry in report["rules"].items():
        assert f"| {rule_id} | {entry['severity']} | {entry['count']} |" in rows


# ---------------------------------------------------------------------------
# Script de validación con grafos
# ---------------------------------------------------------------------------


def test_graphs_are_validated_with_every_rule_family(prototype: Path) -> None:
    validated = _run(VALIDATE_SCRIPT, "--input", prototype, "--graphs")

    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert "familias evaluadas: INS, NOD, EDG, CON, OUT, MET, TEN" in validated.stdout
    assert "no evaluado TEN" not in validated.stdout


def test_without_graphs_the_tensor_rules_are_reported_as_not_evaluated(prototype: Path) -> None:
    validated = _run(VALIDATE_SCRIPT, "--input", prototype)

    assert validated.returncode == 0
    assert "no evaluado TEN: no se entregó HeteroData" in validated.stdout


def test_a_tensor_defect_withholds_only_its_graph(prototype: Path, tmp_path: Path) -> None:
    copy = _copy_prototype(prototype, tmp_path / "v1")
    graph_id = "synthetic:scenario:intervened:0001"
    data = load_graphs(copy / "graphs")[graph_id]
    data["taxon"].x[0, 0] = float("nan")
    torch.save(data, _graph_file(copy, graph_id))

    validated = _run(VALIDATE_SCRIPT, "--input", copy, "--graphs")

    assert validated.returncode == 1
    assert f"[{graph_id}] BLOQUEADO" in validated.stdout
    assert "[synthetic:scenario:basal:0001] entregable" in validated.stdout
    assert "TEN-10 (ERROR): 1" in validated.stdout


def test_a_tampered_graph_file_is_rejected(prototype: Path, tmp_path: Path) -> None:
    copy = _copy_prototype(prototype, tmp_path / "v1")
    graph_id = "synthetic:scenario:basal:0001"
    data = load_graphs(copy / "graphs")[graph_id]
    data.payload = OutputRecord("g", "metabolite", "m", 1.0, "synthetic", "u", "s")
    torch.save(data, _graph_file(copy, graph_id))

    validated = _run(VALIDATE_SCRIPT, "--input", copy, "--graphs")

    assert validated.returncode == 2
    assert "No se pudieron cargar los grafos" in validated.stderr


def test_missing_graphs_suggest_how_to_generate_them(prototype: Path, tmp_path: Path) -> None:
    validated = _run(VALIDATE_SCRIPT, "--input", prototype, "--graphs", tmp_path / "missing")

    assert validated.returncode == 2
    assert "No se encontraron grafos" in validated.stderr
    assert "generate_synthetic_dataset.py --graphs" in validated.stderr


def test_graphs_of_another_dataset_are_rejected(prototype: Path, tmp_path: Path) -> None:
    other = tmp_path / "seed-7"
    assert _run(GENERATE_SCRIPT, "--output", other, "--seed", "7").returncode == 0

    validated = _run(VALIDATE_SCRIPT, "--input", other, "--graphs", prototype / "graphs")

    assert validated.returncode == 2
    assert "Los grafos no corresponden al dataset" in validated.stderr
