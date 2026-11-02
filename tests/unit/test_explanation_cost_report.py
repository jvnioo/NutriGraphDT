"""Informe de `scripts/estimate_explanation_cost.py` (C-05, #241), sin medir."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "estimate_explanation_cost.py"


def test_report_extrapolates_per_process() -> None:
    spec = importlib.util.spec_from_file_location("estimate_explanation_cost", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = {
        "command": "python scripts/estimate_explanation_cost.py",
        "cpu": "CPU",
        "cpu_count": 4,
        "torch": "2",
        "torch_threads": 2,
        "sample_id": "S1",
        "dataset_id": "D1_holofood",
        "graph_nodes": {"host": 1},
        "animals": 56,
        "plan_seeds": 10,
        "explained_outputs": 2,
        "explainer_seeds": 5,
        "executions_per_variant": 5600,
        "repeats": 3,
        "cases": [
            {
                "variant": "hetero_sage",
                "epochs": 100,
                "seconds_per_execution": 0.9,
                "seconds_min": 0.8,
                "seconds_max": 1.0,
                "hours_one_process": 1.4,
            }
        ],
    }
    text = module.to_markdown(result)
    assert "**5600**" in text
    assert "| `hetero_sage` | 100 | 0.900 (0.800–1.000) | 1.40 | 0.70 |" in text
    assert "Horas, 2 procesos" in text
