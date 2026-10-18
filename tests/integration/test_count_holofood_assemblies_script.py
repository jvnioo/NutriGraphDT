"""Reporte de `scripts/count_holofood_assemblies.py` (#141), sin red.

Prueba `build_report` y `to_markdown` con animales construidos a mano; la descarga y la caché
las cubre `fetch_holofood.py`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from nutrigraphdt.data.acquisition.holofood import AssemblyAnimal

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _script():  # type: ignore[no-untyped-def]
    sys.path.insert(0, str(SCRIPTS))  # el script importa fetch_holofood, su vecino
    try:
        spec = importlib.util.spec_from_file_location(
            "count_holofood_assemblies", SCRIPTS / "count_holofood_assemblies.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def _animal(name: str, counts: float, **flags: object) -> AssemblyAnimal:
    values: dict[str, object] = {
        "animal_accession": name,
        "ssu_counts": counts,
        "has_read_profile": False,
        "has_scfa": True,
        "excluded": False,
        "raw_runs": ("ERR1",),
    }
    values.update(flags)
    return AssemblyAnimal(**values)  # type: ignore[arg-type]


def test_report_counts_each_step_and_breaks_down_the_animals_that_would_add() -> None:
    script = _script()
    animals = [
        _animal("A1", 120.0),
        _animal("A2", 1500.0, raw_runs=()),
        _animal("A3", 80.0, has_read_profile=True),
        _animal("A4", 90.0, has_scfa=False),
        _animal("A5", 95.0, excluded=True),
    ]
    metadata = {
        "A1": {
            "diet_treatment_code": "CE",
            "pen_code": "P1",
            "sampling_day": "21",
            "trial_code": "CA",
        },
        "A2": {
            "diet_treatment_code": "CC",
            "pen_code": "P2",
            "sampling_day": "7",
            "trial_code": "CC",
        },
    }

    report = script.build_report(
        animals,
        metadata,
        min_ssu_reads=1000,
        assembly_columns=9,
        exclusions_source="`configs/cohorts/d1_holofood.json`",
        retrieved_at="2026-10-15",
    )

    assert report["steps"] == {
        "animals_with_caecal_assembly": 5,
        "also_with_read_profile": 1,
        "assembly_only": 4,
        "assembly_only_with_scfa": 3,
        "would_add": 2,
        "would_add_reaching_min_ssu": 1,
        "would_add_with_raw_reads": 1,
    }
    assert report["would_add_by"]["animals_by_diet"] == {"CC": 1, "CE": 1}
    assert report["would_add_by"]["animals_by_day"] == {"7": 1, "21": 1}
    assert [row["sample_id"] for row in report["would_add"]] == ["A1", "A2"]

    markdown = script.to_markdown(report)
    assert "| … sin perfiles de AGCC repetidos: **sumarían** | **2** |" in markdown
    assert "| Animales por tratamiento | 1 / 0 / 1 |" in markdown
