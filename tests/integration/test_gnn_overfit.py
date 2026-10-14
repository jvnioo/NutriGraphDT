"""Prueba de cordura de las GNN: sobreajuste a un lote sintético pequeño (A41-7, #83).

Ejecuta `scripts/overfit_gnn.py` como proceso independiente con un lote y un número de épocas
reducidos, y prueba por separado la preparación del lote. Requiere el extra `graph`.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.models.gnn.sanity import (  # noqa: E402
    prepare_overfit_batch,
    synthetic_graphs,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "overfit_gnn.py"
VARIANTS = ("homo_sage", "hetero_sage", "hetero_gat")
THRESHOLD = 1e-2


def test_every_variant_overfits_a_small_synthetic_batch(tmp_path: Path) -> None:
    output = tmp_path / "overfit"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--n-graphs",
            "4",
            "--epochs",
            "200",
            "--threshold",
            str(THRESHOLD),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert set(summary["variants"]) == set(VARIANTS)
    for name, result in summary["variants"].items():
        assert result["overfit"], name
        assert result["final_loss"] < THRESHOLD
        assert result["initial_loss"] > 100 * result["final_loss"]

    with (output / "losses.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 200
    assert set(rows[0]) == {"epoch", *VARIANTS}
    assert (output / "curves.md").read_text(encoding="utf-8").count("xychart-beta") == 3


class TestPrepareOverfitBatch:
    def test_standardizes_target_and_features_without_mutating(self) -> None:
        graphs = synthetic_graphs(4)
        original = [graph["taxon"].x.clone() for graph in graphs]
        data = prepare_overfit_batch(graphs)

        assert all(torch.equal(g["taxon"].x, x) for g, x in zip(graphs, original, strict=True))
        assert data.target.shape == (4, 3)
        assert bool(data.mask.all())
        assert torch.allclose(data.target.mean(dim=0), torch.zeros(3), atol=1e-5)
        assert torch.allclose(data.target.std(dim=0, unbiased=False), torch.ones(3), atol=1e-5)
        taxon = data.batch["taxon"]
        observed = ~taxon.missing_mask
        assert torch.allclose(taxon.x[observed].mean(), torch.tensor(0.0), atol=1e-4)
        assert data.graph_ids == tuple(f"synthetic:graph:{seed:04d}" for seed in range(1, 5))

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(ValueError):
            prepare_overfit_batch([])
        with pytest.raises(ValueError):
            synthetic_graphs(0)
