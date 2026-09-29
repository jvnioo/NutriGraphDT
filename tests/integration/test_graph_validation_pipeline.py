"""Integración del validador en el pipeline y su guía de uso (VG-07).

Exporta un dataset con el script de DS-05, lo valida con `scripts/validate_graph.py` como proceso
independiente y comprueba el reporte y los códigos de salida frente a datasets válidos,
corrompidos después de exportar e ilegibles. También ejecuta los bloques Python de
`docs/graph-validation-usage.md` tal como están escritos.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
USAGE_DOC = REPO_ROOT / "docs" / "graph-validation-usage.md"
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


@pytest.fixture
def exported(tmp_path: Path) -> Path:
    output = tmp_path / "v1"
    generated = _run(GENERATE_SCRIPT, "--output", output)
    assert generated.returncode == 0, generated.stderr
    return output


def _rewrite_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")


def test_valid_dataset_passes_with_warnings_and_writes_the_report(
    exported: Path, tmp_path: Path
) -> None:
    report_path = tmp_path / "reports" / "report.json"

    validated = _run(VALIDATE_SCRIPT, "--input", exported, "--report", report_path)

    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert "estado: valid" in validated.stdout
    assert "[synthetic:scenario:basal:0001] entregable" in validated.stdout
    assert "[synthetic:scenario:intervened:0001] entregable" in validated.stdout
    assert "INS-06 (ADVERTENCIA)" in validated.stdout
    assert "no evaluado TEN: no se entregó HeteroData" in validated.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "valid"
    assert report["summary"]["ERROR"] == 0
    assert set(report["rules"]) == {"INS-06"}
    assert report["evaluated"] == ["INS", "NOD", "EDG", "CON", "OUT", "MET"]


def test_a_node_removed_after_export_blocks_the_graphs(exported: Path, tmp_path: Path) -> None:
    nodes_path = exported / "raw" / "nodes.jsonl"
    lines = nodes_path.read_text(encoding="utf-8").splitlines()
    removed = next(line for line in lines if '"synthetic:metabolite:0001"' in line)
    _rewrite_lines(nodes_path, [line for line in lines if line != removed])
    report_path = tmp_path / "report.json"

    validated = _run(VALIDATE_SCRIPT, "--input", exported, "--report", report_path)

    assert validated.returncode == 1, validated.stdout + validated.stderr
    assert "estado: invalid" in validated.stdout
    assert "BLOQUEADO" in validated.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    # Las aristas del metabolito quedan sin extremo, y counts ya no coincide (nivel dataset).
    assert {"EDG-02", "MET-03"} <= set(report["rules"])
    assert report["dataset_errors"] >= 1
    assert not any(graph["deliverable"] for graph in report["graphs"].values())


def test_non_finite_values_are_reported_instead_of_rejected(exported: Path) -> None:
    nodes_path = exported / "raw" / "nodes.jsonl"
    lines = nodes_path.read_text(encoding="utf-8").splitlines()
    position = next(index for index, line in enumerate(lines) if '"node_type":"taxon"' in line)
    lines[position] = re.sub(r'"abundance":[^,}]+', '"abundance":NaN', lines[position])
    _rewrite_lines(nodes_path, lines)

    validated = _run(VALIDATE_SCRIPT, "--input", exported)

    assert validated.returncode == 1
    assert "NOD-05 (ERROR): 1" in validated.stdout


@pytest.mark.parametrize("damage", ["invalid-json", "missing-file"])
def test_an_unreadable_dataset_exits_with_code_2(exported: Path, damage: str) -> None:
    edges_path = exported / "raw" / "edges.jsonl"
    if damage == "invalid-json":
        edges_path.write_text('{"graph_id": \n', encoding="utf-8")
    else:
        edges_path.unlink()

    validated = _run(VALIDATE_SCRIPT, "--input", exported)

    assert validated.returncode == 2
    assert "No se pudo leer el dataset" in validated.stderr
    assert "edges.jsonl" in validated.stderr


def test_missing_dataset_suggests_how_to_generate_it(tmp_path: Path) -> None:
    validated = _run(VALIDATE_SCRIPT, "--input", tmp_path / "missing")

    assert validated.returncode == 2
    assert "python scripts/generate_synthetic_dataset.py" in validated.stderr


def _python_blocks(markdown: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", markdown, flags=re.DOTALL)


def test_usage_doc_python_snippets_run_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {}
    blocks = _python_blocks(USAGE_DOC.read_text("utf-8"))

    assert len(blocks) >= 4
    for index, block in enumerate(blocks):
        exec(compile(block, f"{USAGE_DOC.name}[python block {index}]", "exec"), namespace)

    assert (tmp_path / "artifacts" / "validation" / "report.json").is_file()
    assert callable(namespace["graphs_for_training"])
