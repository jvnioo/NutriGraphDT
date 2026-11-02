"""Reproducción independiente de una corrida composicional (A68-P4, #182).

Entrena y guarda un fold de una cohorte sintética de 20 animales (sin datos reales) con la
pérdida compuesta, lo reproduce desde su `run.json` y el plan versionado, y comprueba que la
comparación da `ok` en el mismo equipo, también con el plan en CRLF (#133). Un plan con otro
contenido se rechaza antes de entrenar. Requiere los extras `graph` y `baselines`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")

from nutrigraphdt.constraints import D06_PROPIONATE_BOUND_NAME, constraint_catalog  # noqa: E402
from nutrigraphdt.models.gnn import load_model_config  # noqa: E402
from nutrigraphdt.models.training import load_training_config  # noqa: E402
from nutrigraphdt.models.training.compositional import run_compositional_fold  # noqa: E402
from nutrigraphdt.models.training.compositional_tracking import (  # noqa: E402
    plan_content_sha256,
)
from nutrigraphdt.models.training.cv_inputs import (  # noqa: E402
    load_synthetic_cv_inputs,
    synthetic_cv_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "reproduce_compositional_run.py"


@pytest.fixture(scope="module")
def saved_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    tmp = tmp_path_factory.mktemp("original")
    plan_path = tmp / "plan.json"
    synthetic_cv_plan(n_animals=20, first_seed=1).save(plan_path)
    inputs = load_synthetic_cv_inputs(plan_path)
    train_ids, test_ids = inputs.plan.folds(0)[1]
    config = load_training_config(
        REPO_ROOT / "configs" / "training" / "test_constrained_cycle.json"
    )
    evaluation = run_compositional_fold(
        seed=0,
        fold=1,
        model_name="homo_sage",
        edges_arm="constrained",
        train_ids=train_ids,
        test_ids=test_ids,
        graphs=inputs.graphs,
        pens=inputs.pens,
        diets=inputs.diets,
        days=inputs.days,
        model_config=load_model_config(REPO_ROOT / "configs" / "models" / "homo_sage.yaml"),
        metadata=inputs.metadata,
        config=config,
        monitor_constraints=(constraint_catalog()[D06_PROPIONATE_BOUND_NAME],),
        runs_dir=tmp / "runs",
        run_context={
            "dataset_id": inputs.dataset_id,
            "plan": {
                "file": "plan.json",
                "sha256": plan_content_sha256(json.loads(plan_path.read_text(encoding="utf-8"))),
                "version": inputs.plan.version,
                "k": inputs.plan.k,
            },
            "cohort": dict(inputs.cohort),
        },
    )
    assert evaluation.run_dir is not None
    return evaluation.run_dir, plan_path


def _reproduce(run_dir: Path, plan: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(run_dir),
            "--plan",
            str(plan),
            "--output",
            str(output),
            "--runs-dir",
            str(output / "runs"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        cwd=REPO_ROOT,
        check=False,
    )


def test_same_machine_reproduction_passes_every_check(
    saved_run: tuple[Path, Path], tmp_path: Path
) -> None:
    run_dir, plan = saved_run
    completed = _reproduce(run_dir, plan, tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads((tmp_path / f"{run_dir.name}.json").read_text(encoding="utf-8"))
    statuses = {check["name"]: check["status"] for check in report["checks"]}
    assert set(statuses.values()) == {"ok"}
    assert {
        "Plan de folds (SHA-256 canónico, #133)",
        "Predicciones `(z_1, z_2, ln T)` del test",
        "Violaciones: conteos por época, subconjunto y restricción",
        "Recarga del checkpoint original",
    } <= set(statuses)
    markdown = (tmp_path / f"{run_dir.name}.md").read_text(encoding="utf-8")
    assert "(A68-P4, #182)" in markdown
    assert "**Se reproduce**" in markdown


def test_crlf_plan_gives_the_same_canonical_hash(
    saved_run: tuple[Path, Path], tmp_path: Path
) -> None:
    run_dir, plan = saved_run
    crlf = tmp_path / "plan_crlf.json"
    crlf.write_bytes(plan.read_bytes().replace(b"\n", b"\r\n"))
    assert crlf.read_bytes() != plan.read_bytes()
    completed = _reproduce(run_dir, crlf, tmp_path / "out")
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_a_different_plan_is_rejected_before_training(
    saved_run: tuple[Path, Path], tmp_path: Path
) -> None:
    run_dir, plan = saved_run
    other = tmp_path / "other.json"
    synthetic_cv_plan(n_animals=20, first_seed=2).save(other)
    completed = _reproduce(run_dir, other, tmp_path / "out")
    assert completed.returncode == 2
    assert "no es el registrado" in completed.stderr
