"""Corridas pequeñas de demostración para la plataforma y sus pruebas (A81-P2, #288).

`train_fixture_run` entrena un fold con los grafos que arma una `ScenarioBase` (los mismos que el
motor usa para predecir) y lo guarda con `save_compositional_run`. Lo usa
`scripts/build_api_fixtures.py` para regenerar `tests/fixtures/api/frozen_runs/`. Son corridas de
**demostración**: pocas épocas y pocos animales, sin valor científico.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from nutrigraphdt.api.engine import REPO_ROOT, ScenarioBase


def _repo_relative(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(REPO_ROOT):
        return resolved.relative_to(REPO_ROOT).as_posix()
    return resolved.as_posix()


def train_fixture_run(
    base: ScenarioBase,
    *,
    test_ids: Sequence[str],
    pens: Mapping[str, str],
    diets: Mapping[str, str],
    days: Mapping[str, str],
    output_dir: str | Path,
    training_config: str | Path = REPO_ROOT / "configs" / "training" / "api_fixture.json",
    model_config: str | Path = REPO_ROOT / "configs" / "models" / "homo_sage.yaml",
    inner_folds: int = 5,
) -> Path:
    """Entrena un fold (`test_ids` contra el resto) y deja la corrida en `output_dir`.

    `output_dir` se reemplaza: la corrida queda directamente en él, sin el subdirectorio con
    marca de tiempo de `save_compositional_run`.
    """
    import tempfile

    from nutrigraphdt.models.gnn import load_model_config
    from nutrigraphdt.models.gnn.base import GraphMetadata
    from nutrigraphdt.models.gnn.batching import align_graph_types
    from nutrigraphdt.models.training import load_training_config
    from nutrigraphdt.models.training.compositional import run_compositional_fold
    from nutrigraphdt.models.training.compositional_tracking import plan_content_sha256

    graphs = {sample_id: base.graph(sample_id) for sample_id in base.sample_ids}
    align_graph_types(list(graphs.values()), inplace=True)
    test = sorted(test_ids)
    train = [s for s in sorted(graphs) if s not in set(test)]
    plan: dict[str, Any] = {
        "version": "api-fixture-1",
        "dataset_id": base.dataset_id,
        "folds": [{"fold": 0, "train": train, "test": test}],
    }
    target = Path(output_dir)
    # La configuración compartida no sabe qué conjunto ni qué partición usa cada corrida: se
    # registran los de esta, para que `run.json` no declare los de otra.
    config = load_training_config(Path(training_config)).model_copy(
        update={
            "dataset_id": base.dataset_id,
            "split_file": _repo_relative(target / "plan.json"),
        }
    )
    with tempfile.TemporaryDirectory() as tmp:
        evaluation = run_compositional_fold(
            seed=0,
            fold=0,
            model_name="homo_sage",
            edges_arm="with_inferred",
            train_ids=train,
            test_ids=test,
            graphs=graphs,
            pens=pens,
            diets=diets,
            days=days,
            model_config=load_model_config(Path(model_config)),
            metadata=GraphMetadata.from_graphs(list(graphs.values())),
            config=config,
            inner_folds=inner_folds,
            runs_dir=Path(tmp) / "runs",
            run_context={
                "dataset_id": base.dataset_id,
                "plan": {
                    "file": None,
                    "sha256": plan_content_sha256(plan),
                    "version": plan["version"],
                    "k": 1,
                },
                "cohort": {"n_animals": len(graphs), "synthetic": base.is_synthetic},
                "source": {"generator": "nutrigraphdt.api.fixtures.train_fixture_run"},
                "repo_root": REPO_ROOT,
            },
        )
        assert evaluation.run_dir is not None
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(evaluation.run_dir, target)
    (target / "plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return target


__all__ = ["train_fixture_run"]
