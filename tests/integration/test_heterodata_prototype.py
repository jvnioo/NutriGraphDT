"""Flujo completo del prototipo `HeteroData` (A35-1, #28).

Genera el dataset con `scripts/generate_synthetic_dataset.py --graphs` como proceso independiente,
carga los `.pt` y los registros desde disco y los valida con todas las reglas de integridad. También
ejecuta, en orden, los bloques Python de `docs/graph/heterodata-prototype.md`.

Requiere el extra `graph`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch_geometric")

from nutrigraphdt.graph.heterodata import MANIFEST_FILE, load_graphs  # noqa: E402
from nutrigraphdt.graph.validation import read_raw_dataset, validate_graph  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATE_SCRIPT = REPO_ROOT / "scripts" / "generate_synthetic_dataset.py"
PROTOTYPE_DOC = REPO_ROOT / "docs" / "graph" / "heterodata-prototype.md"


def _run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def test_generate_with_graphs_exports_valid_graphs(tmp_path: Path) -> None:
    output = tmp_path / "v1"

    generated = _run(GENERATE_SCRIPT, "--output", output, "--graphs")

    assert generated.returncode == 0, generated.stdout + generated.stderr
    assert "salidas: 6" in generated.stdout
    assert "Grafos HeteroData guardados" in generated.stdout
    assert "validación: valid  ERROR=0" in generated.stdout
    manifest = json.loads((output / "graphs" / MANIFEST_FILE).read_text(encoding="utf-8"))
    assert [entry["file"] for entry in manifest["graphs"]] == ["graph_0001.pt", "graph_0002.pt"]

    records = read_raw_dataset(output)
    graphs = load_graphs(output / "graphs")
    report = validate_graph(records, heterodata=graphs)

    assert report.is_valid
    assert "TEN" in report.evaluated and not report.not_evaluated
    assert report.deliverable_graph_ids == tuple(sorted(graphs))
    assert records.metadata["target_schema"]["metabolite"]["measured_or_predicted"] == "synthetic"


def test_generate_with_graphs_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "v1"
    assert _run(GENERATE_SCRIPT, "--output", output, "--graphs").returncode == 0

    repeated = _run(GENERATE_SCRIPT, "--output", output, "--graphs")

    assert repeated.returncode != 0
    assert "--overwrite" in repeated.stderr
    assert _run(GENERATE_SCRIPT, "--output", output, "--graphs", "--overwrite").returncode == 0


def _python_blocks(markdown: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", markdown, flags=re.DOTALL)


def test_prototype_doc_python_snippets_run_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {}
    blocks = _python_blocks(PROTOTYPE_DOC.read_text("utf-8"))

    assert len(blocks) >= 2
    for index, block in enumerate(blocks):
        exec(compile(block, f"{PROTOTYPE_DOC.name}[python block {index}]", "exec"), namespace)

    assert (tmp_path / "artifacts" / "synthetic" / "prototype" / "graphs" / MANIFEST_FILE).is_file()
