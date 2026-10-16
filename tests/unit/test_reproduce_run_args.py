"""Argumentos de reentrenamiento de `scripts/reproduce_run.py` con la cohorte de D1 (#108, #138).

No entrena: solo comprueba qué se le pasa a `train_gnn.py`. No requiere PyTorch.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from nutrigraphdt.models.training.reproducibility import ReproductionError

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reproduce_run.py"


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reproduce_run", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _info(source: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": "20261020-000000_homo_sage_s42", "variant": "homo_sage", "source": source}


def test_synthetic_run_passes_cohort_parameters(script: ModuleType) -> None:
    source = {"dataset": "synthetic", "n_samples": 50, "first_seed": 1, "split_seed": 42}
    argv = script.train_arguments(_info(source), Path("t.json"), Path("m.yaml"))
    assert argv[argv.index("--n-samples") + 1] == "50"
    assert "--sources" not in argv
    assert "--min-ssu-reads" not in argv


def test_d1_run_reuses_the_recorded_cohort_threshold(script: ModuleType) -> None:
    cohort = {"dataset_id": "D1", "version": "1.0.0", "min_ssu_reads": 1000, "size": 56}
    source = {"dataset": "d1", "graphs": "artifacts/graphs/D1_holofood", "cohort": cohort}
    argv = script.train_arguments(
        _info(source), Path("t.json"), Path("m.yaml"), Path("fuentes.json")
    )
    assert argv[argv.index("--min-ssu-reads") + 1] == "1000"
    assert argv[argv.index("--sources") + 1] == "fuentes.json"


def test_d1_run_before_the_cohort_cannot_be_retrained(script: ModuleType) -> None:
    source = {"dataset": "d1", "graphs": "artifacts/graphs/D1_holofood"}
    with pytest.raises(ReproductionError, match="#138"):
        script.train_arguments(_info(source), Path("t.json"), Path("m.yaml"))
