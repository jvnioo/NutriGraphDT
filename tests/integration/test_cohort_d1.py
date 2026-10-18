"""La cohorte de D1 sobre el fixture de seis animales y su reporte (#138)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from nutrigraphdt.data.cohort import (
    STEP_DEPTH,
    STEP_EXCLUDED,
    CohortConfig,
    CohortExclusion,
    get_cohort_config,
    load_cohort,
)
from nutrigraphdt.data.config import load_sources

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "report_cohort.py"
FIXTURE_ANIMALS = {
    "SAMEA112904764",  # 8187 lecturas SSU, la menor del fixture
    "SAMEA112904772",
    "SAMEA112904803",
    "SAMEA112904810",
    "SAMEA112904855",
    "SAMEA112904883",
}


def _test_config() -> CohortConfig:
    """Excluye un animal del fixture y pone el umbral sobre el de menor profundidad."""
    official = get_cohort_config()
    return CohortConfig(
        dataset_id=official.dataset_id,
        version="fixture",
        targets=official.targets,
        min_ssu_reads=10000,
        sensitivity_min_ssu_reads=(1000,),
        exclusions=(
            *official.exclusions,
            CohortExclusion("SAMEA112904772", "duplicated_scfa_profile", "solo para la prueba"),
        ),
    )


def test_official_cohort_keeps_the_six_fixture_animals(holofood_fixture_sources: Path) -> None:
    cohort = load_cohort(load_sources(holofood_fixture_sources))

    assert cohort.sample_ids == FIXTURE_ANIMALS
    assert all(step.removed == () for step in cohort.steps)


def test_each_step_removes_its_animals(holofood_fixture_sources: Path) -> None:
    cohort = load_cohort(load_sources(holofood_fixture_sources), _test_config())

    steps = {step.name: step for step in cohort.steps}
    assert steps[STEP_EXCLUDED].removed == ("SAMEA112904772",)
    assert steps[STEP_DEPTH].removed == ("SAMEA112904764",)
    assert cohort.sample_ids == FIXTURE_ANIMALS - {"SAMEA112904772", "SAMEA112904764"}
    assert cohort.read_depths["SAMEA112904764"] == 8187.0


def test_report_script_writes_official_and_sensitivity_tables(
    holofood_fixture_sources: Path, tmp_path: Path
) -> None:
    config_path = tmp_path / "cohort.json"
    config = _test_config()
    config_path.write_text(
        json.dumps(
            {
                "dataset_id": config.dataset_id,
                "version": config.version,
                "targets": list(config.targets),
                "min_ssu_reads": config.min_ssu_reads,
                "sensitivity_min_ssu_reads": list(config.sensitivity_min_ssu_reads),
                "exclusions": [
                    {"sample_id": item.sample_id, "reason": item.reason, "note": item.note}
                    for item in config.exclusions
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sources",
            str(holofood_fixture_sources),
            "--cohort-config",
            str(config_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads((output / "d1_holofood.json").read_text(encoding="utf-8"))
    official, sensitivity = report["analyses"]
    assert (official["min_ssu_reads"], official["official"], official["size"]) == (10000, True, 4)
    assert (sensitivity["min_ssu_reads"], sensitivity["size"]) == (1000, 5)
    assert [step["count"] for step in official["steps"]] == [6, 5, 4]
    assert official["steps"][0]["animals_by_diet"] == {"CC": 2, "CE": 2, "CO": 2}
    markdown = (output / "d1_holofood.md").read_text(encoding="utf-8")
    assert "## Umbral de 10000 lecturas SSU (oficial): 4 animales" in markdown
    assert "## Umbral de 1000 lecturas SSU (sensibilidad): 5 animales" in markdown


def test_report_script_fails_cleanly_without_data(tmp_path: Path) -> None:
    registry = json.loads((REPO_ROOT / "configs" / "sources.json").read_text(encoding="utf-8"))
    registry["sources"]["D1_holofood"]["path_or_url"] = str(tmp_path / "missing.tsv")
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps(registry), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--sources", str(sources), "--output", str(tmp_path / "o")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        check=False,
    )

    assert completed.returncode == 2
    assert "No se pudo reportar la cohorte" in completed.stderr
    assert not (tmp_path / "o").exists()
