"""`scripts/graph_stats.py` sobre los grafos del dataset sintético (A35-4, #31).

Genera los grafos con `generate_synthetic_dataset.py --graphs` y ejecuta el script como proceso
independiente, sin intervención manual, como exige el criterio de aceptación.

Requiere el extra `graph`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch_geometric")

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATE_SCRIPT = REPO_ROOT / "scripts" / "generate_synthetic_dataset.py"
STATS_SCRIPT = REPO_ROOT / "scripts" / "graph_stats.py"


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
def graphs_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("synthetic") / "v1"
    generated = _run(GENERATE_SCRIPT, "--output", output, "--graphs")
    assert generated.returncode == 0, generated.stdout + generated.stderr
    return output / "graphs"


def test_summarizes_every_graph_and_writes_samples(graphs_dir: Path, tmp_path: Path) -> None:
    result = _run(STATS_SCRIPT, "--graphs", graphs_dir, "--output", tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "[synthetic:scenario:basal:0001]" in result.stdout
    assert "[synthetic:scenario:intervened:0001]" in result.stdout
    summary = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))
    by_id = {graph["graph_id"]: graph for graph in summary["graphs"]}
    assert set(by_id) == {"synthetic:scenario:basal:0001", "synthetic:scenario:intervened:0001"}
    for graph in by_id.values():
        assert graph["num_nodes"] == sum(graph["nodes"].values())
        assert graph["num_edges"] == sum(graph["edges"].values())
        assert graph["num_components"] >= 1
    samples = sorted(path.name for path in tmp_path.glob("sample_*.md"))
    assert samples == ["sample_0001.md", "sample_0002.md"]
    assert "```mermaid\nflowchart LR" in (tmp_path / "sample_0001.md").read_text(encoding="utf-8")


def test_single_graph_with_seed_node(graphs_dir: Path, tmp_path: Path) -> None:
    result = _run(
        STATS_SCRIPT,
        "--graphs",
        graphs_dir,
        "--output",
        tmp_path,
        "--graph-id",
        "synthetic:scenario:basal:0001",
        "--seed-node",
        "host:0",
        "--hops",
        "0",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert [path.name for path in tmp_path.glob("sample_*.md")] == ["sample_0001.md"]
    sample = (tmp_path / "sample_0001.md").read_text(encoding="utf-8")
    assert "1 nodos y 0 aristas" in sample


@pytest.mark.parametrize(
    "extra",
    [["--graph-id", "synthetic:missing"], ["--seed-node", "ghost:0"]],
)
def test_invalid_selection_exits_with_code_2(
    graphs_dir: Path, tmp_path: Path, extra: list[str]
) -> None:
    result = _run(STATS_SCRIPT, "--graphs", graphs_dir, "--output", tmp_path, *extra)

    assert result.returncode == 2
    assert not (tmp_path / "stats.json").exists()


def test_missing_graphs_exit_with_code_2(tmp_path: Path) -> None:
    result = _run(STATS_SCRIPT, "--graphs", tmp_path / "missing", "--output", tmp_path / "out")

    assert result.returncode == 2
    assert "generate_synthetic_dataset.py --graphs" in result.stderr
