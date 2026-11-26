"""Pipeline sintético completo con la configuración de entrega (A117, #347).

Corre `run_delivery` en un directorio temporal (unos segundos en CPU) y comprueba que reproduce
las corridas congeladas, que cada escenario del catálogo da su estado esperado y que el reporte
cita commit, configuración y entorno. Requiere los extras `graph`, `baselines` y `demo`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")
pytest.importorskip("sklearn")
pytest.importorskip("plotly")

from nutrigraphdt import delivery  # noqa: E402


@pytest.fixture(scope="module")
def record(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return delivery.run_delivery(work_dir=tmp_path_factory.mktemp("delivery"), log=lambda _: None)


def test_pipeline_covers_every_step(record: dict[str, Any]) -> None:
    assert record["data"]["n_animals"] == 20
    assert "ERROR" not in record["data"]["findings"]
    assert record["graph"]["graphs"] == 20 and record["graph"]["node_types"] == 8
    assert set(record["runs"]) == {"synthetic", "synthetic_constrained"}
    assert record["explanation"]["valid_contract"]
    for step in ("datos", "validación", "grafos", "explicación"):
        assert step in record["seconds"]


@pytest.mark.parametrize("run", ["synthetic", "synthetic_constrained"])
def test_runs_reproduce_the_frozen_runs(record: dict[str, Any], run: str) -> None:
    result = record["runs"][run]
    assert result["reproducibility"]["reproduced"], result["reproducibility"]
    assert result["metrics"] == pytest.approx(result["reference_metrics"])
    assert all(s["ok"] for s in result["scenarios"]), result["scenarios"]


def test_constrained_run_uses_the_registered_lambda(record: dict[str, Any]) -> None:
    run = record["runs"]["synthetic_constrained"]
    assert run["constraint_lambda"] == 0.1
    assert run["constraint_terms"] == ["d06.hydrogen.propionate_bound"]


def test_report_cites_commit_config_and_environment(record: dict[str, Any], tmp_path: Path) -> None:
    delivery.write_delivery_report(record, tmp_path)
    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert data["git"]["commit"] and data["config_sha256"]
    assert data["environment"]["torch"]
    assert all(d["explained"] for d in data["deviations"])
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert data["git"]["commit"] in text and "configs/delivery.json" in text
    assert "Datos sintéticos" in text


def test_unreproduced_run_is_an_unexplained_deviation(record: dict[str, Any]) -> None:
    broken = json.loads(json.dumps(record, default=str))
    broken["runs"]["synthetic"]["reproducibility"]["reproduced"] = False
    broken["runs"]["synthetic"]["scenarios"][0]["ok"] = False
    found = delivery.deviations(broken, delivery.previous_synthetic())
    pending = [d for d in found if not d["explained"]]
    assert len(pending) == 2
