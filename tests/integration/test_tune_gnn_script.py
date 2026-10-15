"""Prueba de integración de `scripts/tune_gnn.py` (A45-5, #105).

Corre una grilla mínima (2 × 1) con 2 semillas y 1 o 2 épocas, en un proceso independiente, y
verifica los archivos:

- con una cohorte sintética pequeña (requiere además scikit-learn, como `train_gnn.py`);
- con los grafos del fixture de HoloFood guardados como los deja `build_graph.py`, sin
  scikit-learn.

Requiere el extra `graph`.
"""

from __future__ import annotations

import csv
import dataclasses
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("yaml")

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.graph.builder import build_hetero_graph  # noqa: E402
from nutrigraphdt.graph.heterodata import save_graphs  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "tune_gnn.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
needs_sklearn = pytest.mark.skipif(
    importlib.util.find_spec("sklearn") is None,
    reason="La cohorte sintética se arma con el módulo de baselines, que requiere scikit-learn.",
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def tuned(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    if importlib.util.find_spec("sklearn") is None:
        pytest.skip("La cohorte sintética se arma con el módulo de baselines (scikit-learn).")
    root = tmp_path_factory.mktemp("tune")
    paths = {
        "runs": root / "runs",
        "output": root / "report",
        "selected": root / "configs" / "selected.yaml",
    }
    completed = _run(
        "--model",
        "homo_sage",
        "--dataset",
        "synthetic",
        "--n-samples",
        "12",
        "--hidden",
        "32",
        "64",
        "--layers",
        "1",
        "--seeds",
        "3",
        "4",
        "--max-epochs",
        "2",
        "--only-model",
        "--runs-dir",
        str(paths["runs"]),
        "--output",
        str(paths["output"]),
        "--selected-config",
        str(paths["selected"]),
    )
    assert completed.returncode == 0, completed.stderr
    return paths


def test_grid_has_only_val_and_selection_is_its_minimum(tuned: dict[str, Path]) -> None:
    grid = _rows(tuned["output"] / "grid.csv")
    assert [(row["hidden_channels"], row["num_layers"], row["seed"]) for row in grid] == [
        ("32", "1", "3"),
        ("64", "1", "3"),
    ]
    assert not [name for name in grid[0] if name.startswith("test")]

    selection = json.loads((tuned["output"] / "selection.json").read_text(encoding="utf-8"))
    assert selection["dataset"] == "synthetic"
    assert selection["selection"]["split"] == "val"
    assert selection["selection"]["test_used"] is False
    best = min(grid, key=lambda row: float(row["val_rmse"]))
    assert selection["selected"]["run_id"] == best["run_id"]


def test_selected_configuration_is_a_valid_model_yaml(tuned: dict[str, Path]) -> None:
    selection = json.loads((tuned["output"] / "selection.json").read_text(encoding="utf-8"))
    config = load_model_config(tuned["selected"])
    assert config.model_dump() == selection["selected"]["model_config"]
    assert tuned["selected"].read_text(encoding="utf-8").startswith("# Configuración elegida")


def test_seed_runs_and_summary(tuned: dict[str, Path]) -> None:
    seeds = _rows(tuned["output"] / "seeds.csv")
    assert {(row["configuration"], row["seed"]) for row in seeds} == {
        ("inicial", "3"),
        ("inicial", "4"),
        ("elegida", "3"),
        ("elegida", "4"),
    }
    assert all(row["test_rmse"] for row in seeds)
    summary = _rows(tuned["output"] / "summary.csv")
    assert {row["n"] for row in summary} == {"2"}
    report = (tuned["output"] / "report.md").read_text(encoding="utf-8")
    assert "±" in report and "**elegida**" in report


def test_every_run_json_is_copied_and_traceable(tuned: dict[str, Path]) -> None:
    rows = _rows(tuned["output"] / "grid.csv") + _rows(tuned["output"] / "seeds.csv")
    run_ids = {row["run_id"] for row in rows}
    copies = {
        path.relative_to(tuned["output"] / "run_records").with_suffix("").as_posix()
        for path in (tuned["output"] / "run_records").rglob("*.json")
    }
    assert copies == run_ids
    for row in rows:
        run_id = row["run_id"]
        info = json.loads((tuned["output"] / "run_records" / f"{run_id}.json").read_text("utf-8"))
        assert info["variant"] == "homo_sage"
        assert info["seed"] == int(row["seed"])
        assert info["model_config"]["hidden_channels"] == int(row["hidden_channels"])
        assert info["split"]["counts"]["test"] > 0
        assert (tuned["runs"] / "synthetic" / run_id / "checkpoint.pt").is_file()


def test_seed_override_is_rejected(tmp_path: Path) -> None:
    completed = _run("--model", "homo_sage", "--dataset", "synthetic", "--seed", "1")
    assert completed.returncode == 2
    assert "--seeds" in completed.stderr


@needs_sklearn
def test_invalid_grid_value_exits_with_input_error(tmp_path: Path) -> None:
    completed = _run(
        "--model",
        "hetero_gat",
        "--dataset",
        "synthetic",
        "--n-samples",
        "12",
        "--hidden",
        "30",
        "--layers",
        "1",
        "--seeds",
        "1",
        "--max-epochs",
        "1",
        "--only-model",
        "--runs-dir",
        str(tmp_path / "runs"),
        "--output",
        str(tmp_path / "out"),
        "--selected-config",
        str(tmp_path / "sel.yaml"),
    )
    assert completed.returncode == 2
    assert "divisible" in completed.stderr


def _save_fixture_graphs(directory: Path) -> None:
    """Grafos del fixture de HoloFood con el formato de `build_graph.py --save-graphs`."""
    sources = load_sources(REPO_ROOT / "configs" / "sources.json")

    def source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
        return dataclasses.replace(sources[source_id], path_or_url=str(FIXTURES / file_name))

    tables = (
        DataPipeline({"D1_holofood": source("D1_holofood", "abundance_ssu_caecum.tsv")})
        .run(["D1_holofood"])
        .dataset
    )
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    graphs = build_hetero_graph(tables).graphs
    save_graphs(graphs, directory / "graphs")
    status = {graph_id: {"deliverable": True} for graph_id in graphs}
    (directory / "report.json").write_text(
        json.dumps({"validation": {"graphs": status}}), encoding="utf-8"
    )


def test_d1_fixture_without_scikit_learn(tmp_path: Path) -> None:
    graphs_dir = tmp_path / "graphs_d1"
    _save_fixture_graphs(graphs_dir)
    # Un módulo `sklearn` que falla al importarse simula un equipo sin scikit-learn.
    blocker = tmp_path / "blocker"
    (blocker / "sklearn").mkdir(parents=True)
    (blocker / "sklearn" / "__init__.py").write_text(
        'raise ImportError("scikit-learn no disponible")\n', encoding="utf-8"
    )
    output = tmp_path / "report"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--model",
            "homo_sage",
            "--dataset",
            "d1",
            "--graphs-dir",
            str(graphs_dir),
            "--split-file",
            str(FIXTURES / "split.json"),
            "--hidden",
            "32",
            "64",
            "--layers",
            "1",
            "--seeds",
            "5",
            "6",
            "--max-epochs",
            "1",
            "--patience",
            "1",
            "--only-model",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--output",
            str(output),
            "--selected-config",
            str(tmp_path / "selected.yaml"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": os.pathsep.join(
                [str(blocker), *filter(None, [os.environ.get("PYTHONPATH")])]
            ),
        },
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    assert selection["dataset"] == "d1"
    assert len(selection["candidates"]) == 2
    run_info = json.loads(
        next((output / "run_records").rglob("*.json")).read_text(encoding="utf-8")
    )
    assert run_info["split"]["file"].endswith("split.json")
    assert run_info["source"]["dataset"] == "d1"


def test_run_records_are_not_ignored_by_git(tuned: dict[str, Path]) -> None:
    # `.gitignore` ignora toda carpeta `runs/`; las copias de run.json deben poder versionarse.
    if shutil.which("git") is None or not (REPO_ROOT / ".git").exists():
        pytest.skip("Sin Git o fuera de un repositorio.")
    copy = next((tuned["output"] / "run_records").rglob("*.json"))
    relative = copy.relative_to(tuned["output"])
    candidate = Path("reports") / "gnn" / "tuning" / "synthetic" / relative
    completed = subprocess.run(
        ["git", "check-ignore", "-q", candidate.as_posix()],
        cwd=REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 1, f"{candidate} queda ignorado por .gitignore"
