"""Pruebas de la cohorte supervisada de D1 (#138)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from nutrigraphdt.data.cohort import (
    STEP_DEPTH,
    STEP_EXCLUDED,
    STEP_PAIRED,
    CohortConfig,
    CohortConfigError,
    CohortExclusion,
    complete_target_samples,
    describe_cohort,
    get_cohort_config,
    select_cohort,
    ssu_read_depths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("acetate", "propionate", "butyrate")


def _config(**changes: object) -> CohortConfig:
    values: dict[str, object] = {
        "dataset_id": "D1_holofood",
        "version": "test",
        "targets": TARGETS,
        "min_ssu_reads": 1000,
        "exclusions": (CohortExclusion("C", "duplicated_scfa_profile"),),
    }
    values.update(changes)
    return CohortConfig(**values)  # type: ignore[arg-type]


def test_select_cohort_applies_the_three_steps_in_order() -> None:
    complete = {"A", "B", "C", "D", "E"}  # E no tiene metagenoma
    depths = {"A": 2000.0, "B": 999.0, "C": 50.0, "D": 1000.0, "X": 9000.0}  # X sin AGCC

    cohort = select_cohort(complete, depths, _config())

    assert [step.name for step in cohort.steps] == [STEP_PAIRED, STEP_EXCLUDED, STEP_DEPTH]
    assert cohort.steps[0].remaining == ("A", "B", "C", "D")
    assert cohort.steps[1].removed == ("C",)
    # El umbral es inclusivo: 1000 lecturas entran, 999 no.
    assert cohort.steps[2].removed == ("B",)
    assert cohort.sample_ids == frozenset({"A", "D"})
    assert len(cohort) == 2
    assert "A" in cohort and "B" not in cohort


def test_exclusions_absent_from_the_data_are_not_reported_as_removed() -> None:
    cohort = select_cohort({"A"}, {"A": 5000.0}, _config())
    assert cohort.steps[1].removed == ()
    assert cohort.sample_ids == frozenset({"A"})


def test_min_ssu_reads_can_be_replaced_for_a_sensitivity_analysis() -> None:
    config = _config()
    strict = config.with_min_ssu_reads(5000)
    depths = {"A": 2000.0, "B": 6000.0}

    assert select_cohort({"A", "B"}, depths, config).sample_ids == {"A", "B"}
    assert select_cohort({"A", "B"}, depths, strict).sample_ids == {"B"}
    assert config.min_ssu_reads == 1000


def test_summary_records_version_threshold_and_removed_animals() -> None:
    cohort = select_cohort({"A", "B", "C"}, {"A": 2000.0, "B": 10.0, "C": 3000.0}, _config())
    summary = cohort.summary()

    assert summary["version"] == "test"
    assert summary["min_ssu_reads"] == 1000
    assert summary["size"] == 1
    assert [(step["name"], step["count"], step["removed"]) for step in summary["steps"]] == [
        (STEP_PAIRED, 3, []),
        (STEP_EXCLUDED, 2, ["C"]),
        (STEP_DEPTH, 1, ["B"]),
    ]
    assert cohort.to_dict()["sample_ids"] == ["A"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"min_ssu_reads": -1}, "umbrales"),
        ({"min_ssu_reads": True}, "umbrales"),
        ({"sensitivity_min_ssu_reads": (1.5,)}, "umbrales"),
        ({"targets": ()}, "targets"),
        ({"targets": ("acetate", "acetate")}, "targets"),
        ({"exclusions": (CohortExclusion("A", "x"), CohortExclusion("A", "y"))}, "repetidos"),
        ({"exclusions": (CohortExclusion("A", ""),)}, "motivo"),
        ({"exclusions": (CohortExclusion("", "x"),)}, "sample_id"),
        ({"version": ""}, "obligatorios"),
    ],
)
def test_invalid_configurations_are_rejected(changes: dict[str, object], message: str) -> None:
    with pytest.raises(CohortConfigError, match=message):
        _config(**changes)


def test_from_dict_requires_the_mandatory_keys() -> None:
    with pytest.raises(CohortConfigError, match="incompleta"):
        CohortConfig.from_dict({"dataset_id": "D1_holofood", "version": "1"})


def test_official_configuration_lists_the_eight_duplicated_profiles() -> None:
    config = get_cohort_config()

    assert config.dataset_id == "D1_holofood"
    assert config.targets == TARGETS
    assert config.min_ssu_reads == 1000
    assert config.sensitivity_min_ssu_reads == (5000,)
    assert config.matrix == "caecum_content"
    assert len(config.exclusions) == 8
    assert {item.reason for item in config.exclusions} == {"duplicated_scfa_profile"}
    assert "SAMEA112905124" in config.excluded_ids


def test_get_cohort_config_checks_the_dataset_id(tmp_path: Path) -> None:
    data = json.loads((REPO_ROOT / "configs/cohorts/d1_holofood.json").read_text("utf-8"))
    path = tmp_path / "other.json"
    path.write_text(json.dumps({**data, "dataset_id": "otro"}), encoding="utf-8")

    with pytest.raises(CohortConfigError, match="se esperaba"):
        get_cohort_config("D1_holofood", cohort_file=path)
    assert get_cohort_config("otro", cohort_file=path).dataset_id == "otro"


def test_ssu_read_depths_sums_raw_counts_per_animal(tmp_path: Path) -> None:
    path = tmp_path / "abundance.tsv"
    path.write_text(
        "taxon_lineage\tA\tB\nsk__Bacteria\t10\t\nsk__Bacteria;p__Firmicutes\t5\t3\n",
        encoding="utf-8",
    )
    assert ssu_read_depths(path) == {"A": 15.0, "B": 3.0}


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "vacía"),
        ("lineage\tA\nsk__Bacteria\t1\n", "taxon_lineage"),
        ("taxon_lineage\tA\nsk__Bacteria\tx\n", "no numérico"),
        ("taxon_lineage\tA\nsk__Bacteria\t-1\n", "inválido"),
        ("taxon_lineage\tA\nsk__Bacteria\tnan\n", "inválido"),
    ],
)
def test_ssu_read_depths_rejects_malformed_tables(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "abundance.tsv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        ssu_read_depths(path)


def test_complete_target_samples_requires_every_target_finite() -> None:
    records = [{"sample_id": "A", "canonical_id": name, "value": 1.0} for name in TARGETS] + [
        {"sample_id": "B", "canonical_id": "acetate", "value": 1.0},
        {"sample_id": "B", "canonical_id": "propionate", "value": 0.0},
        {"sample_id": "B", "canonical_id": "butyrate", "value": math.nan},
        {"sample_id": "C", "canonical_id": "acetate", "value": 1.0},
        {"sample_id": "C", "canonical_id": "propionate", "value": True},
        {"sample_id": "C", "canonical_id": "isobutyrate", "value": 1.0},
        {"sample_id": "C", "canonical_id": "butyrate", "value": 1.0},
    ]
    assert complete_target_samples(records, TARGETS) == {"A"}


def test_describe_cohort_counts_animals_and_pens_by_diet() -> None:
    cohort = select_cohort(
        {"A", "B", "C", "D"}, {"A": 2000.0, "B": 2000.0, "C": 2000.0, "D": 10.0}, _config()
    )
    metadata = {
        "A": {"diet_treatment_code": "CC", "pen_code": "P1"},
        "B": {"diet_treatment_code": "CC", "pen_code": "P1"},
        "D": {"diet_treatment_code": "CE", "pen_code": "P2"},
    }

    rows = describe_cohort(cohort, metadata)

    assert rows[0]["animals_by_diet"] == {"CC": 2, "CE": 1}
    assert rows[0]["sin_metadatos"] == 1  # C
    assert rows[-1]["animals_by_diet"] == {"CC": 2}
    assert rows[-1]["pens_by_diet"] == {"CC": 1}
