"""Pruebas de las transformaciones de la fuente D1 (HoloFood) sin acceso a red.

Las fichas imitan la estructura de `https://www.holofooddata.org/api/samples/{acc}` y
`/api/animals/{acc}`; los valores son ilustrativos.
"""

from __future__ import annotations

from typing import Any

import pytest

from nutrigraphdt.data.acquisition.holofood import (
    METADATA_COLUMNS,
    SCFA_MARKERS,
    RunLink,
    abundance_table,
    animal_metadata_row,
    body_site,
    caecal_run_links,
    merge_by_animal,
    parse_mgnify_taxonomy,
    rows_table,
    scfa_row,
)


def _marker(marker_type: str, name: str, value: str, units: str | None = None) -> dict[str, Any]:
    return {"marker": {"name": name, "type": marker_type}, "measurement": value, "units": units}


def _scfa_sample(site: str = "caecum content", **overrides: str) -> dict[str, Any]:
    values = {"Acetic acid": "51.58", "Propionic acid": "2.29", "n-Butyric acid": "13.47"}
    values.update(overrides)
    metadata = [_marker("FATTY ACIDS", k, v, "umol/g digesta") for k, v in values.items()]
    metadata += [
        _marker("FATTY ACIDS", "Acetic:totalFA ratio", "0.79"),
        _marker("FATTY ACIDS", "Total SCFAs", "79.78", "umol/g digesta"),
        _marker("SAMPLE", "Body site", site),
    ]
    return {"accession": "SAMEA1", "animal": "SAMEA9", "structured_metadata": metadata}


def test_body_site_is_read_from_the_sample_marker() -> None:
    assert body_site(_scfa_sample("Caecum Content")) == "caecum content"
    assert body_site({"structured_metadata": []}) is None


def test_scfa_row_keeps_individual_concentrations_only() -> None:
    row = scfa_row(_scfa_sample())
    assert list(row) == list(SCFA_MARKERS)
    assert row["Acetic acid"] == "51.58"
    assert row["n-Butyric acid"] == "13.47"
    assert row["D-Lactate"] == ""
    assert "Total SCFAs" not in row
    assert "Acetic:totalFA ratio" not in row


def test_scfa_row_rejects_an_unexpected_unit() -> None:
    sample = _scfa_sample()
    sample["structured_metadata"][0]["units"] = "mM"
    with pytest.raises(ValueError, match="umol/g digesta"):
        scfa_row(sample)


def _animal(*extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "accession": "SAMEA9",
        "structured_metadata": [
            _marker("SAMPLE", "Animal code", "CA01.07"),
            _marker("SAMPLE", "Sex", "Male"),
            _marker("SAMPLE", "Breed", "Cobb"),
            _marker("SAMPLE", "Sampling time", "Day 21"),
            _marker("SAMPLE", "Chicken body weight", "920.8", "g"),
            _marker("TREATMENT", "Treatment code", "CC"),
            _marker("TREATMENT", "Treatment name", "Control"),
            _marker("TRIAL", "Trial code", "CA"),
            _marker("PEN", "Pen code", "CA01"),
            _marker("PEN", "Average body weight at day 35", "2542.32", "g"),
            *extra,
        ],
    }


def test_animal_metadata_row_maps_individual_markers() -> None:
    row = animal_metadata_row(_animal())
    assert list(row) == list(METADATA_COLUMNS)
    assert row == {
        "sample_id": "SAMEA9",
        "animal_code": "CA01.07",
        "trial_code": "CA",
        "pen_code": "CA01",
        "diet_treatment_code": "CC",
        "diet_treatment_name": "Control",
        "sex": "male",
        "breed": "Cobb",
        "sampling_day": "21",
        "body_weight_g": "920.8",
    }


def test_pen_level_markers_never_become_individual_phenotypes() -> None:
    row = animal_metadata_row(_animal(_marker("PEN", "Chicken body weight", "9999", "g")))
    assert row["body_weight_g"] == "920.8"


def test_animal_weight_in_another_unit_is_rejected() -> None:
    animal = _animal()
    animal["structured_metadata"][4]["units"] = "kg"
    with pytest.raises(ValueError, match="kg"):
        animal_metadata_row(animal)


MGNIFY = (
    "#SampleID\tERR1\tERR2\tERZ3\n"
    "sk__Bacteria;p__Firmicutes\t10\t0\t4\n"
    "sk__Bacteria;p__Bacteroidetes\t0\t5\t1\n"
)


def test_parse_mgnify_taxonomy_keeps_nonzero_counts_per_column() -> None:
    columns, counts = parse_mgnify_taxonomy(MGNIFY)
    assert columns == ["ERR1", "ERR2", "ERZ3"]
    assert counts["ERR1"] == {"sk__Bacteria;p__Firmicutes": 10.0}
    assert counts["ERR2"] == {"sk__Bacteria;p__Bacteroidetes": 5.0}


@pytest.mark.parametrize(
    "text",
    ["taxon\tERR1\nsk__Bacteria\t1\n", "#SampleID\tERR1\nsk__Bacteria\t1\t2\n"],
)
def test_parse_mgnify_taxonomy_rejects_malformed_tables(text: str) -> None:
    with pytest.raises(ValueError):
        parse_mgnify_taxonomy(text)


def test_caecal_run_links_keep_read_runs_of_caecal_content() -> None:
    samples = {
        "S1": {"title": "CA01.07F1a", "animal": "A1"},
        "S2": {"title": "CA01.08C1a", "animal": "A2"},
        "S3": {"title": "CA01.09F1a", "animal": "A3"},
    }
    runs = [
        {"run_accession": "ERR2", "sample_accession": "S1"},
        {"run_accession": "ERR1", "sample_accession": "S1"},
        {"run_accession": "ERR3", "sample_accession": "S2"},  # íleon: fuera
        {"run_accession": "ERZ4", "sample_accession": "S3"},  # ensamblaje: fuera
        {"run_accession": "ERR5", "sample_accession": "S9"},  # sin muestra en el portal
        {"run_accession": "ERR6", "sample_accession": "S3"},  # sin tabla de MGnify
    ]
    run_to_study = {"ERR1": "M1", "ERR2": "M1", "ERR3": "M1", "ERZ4": "M1", "ERR5": "M1"}
    links = caecal_run_links(runs, samples, run_to_study)
    assert [link.run_accession for link in links] == ["ERR1", "ERR2"]
    assert {link.animal_accession for link in links} == {"A1"}


def test_merge_by_animal_sums_resequenced_runs() -> None:
    tables = {"M1": {"ERR1": {"t1": 2.0}, "ERR2": {"t1": 3.0, "t2": 1.0}}}
    links = [
        RunLink("ERR1", "S1", "A1", "CA01.07F1a", "M1"),
        RunLink("ERR2", "S1", "A1", "CA01.07F1a", "M1"),
    ]
    assert merge_by_animal(tables, links) == {"A1": {"t1": 5.0, "t2": 1.0}}


def test_abundance_table_is_sorted_and_zero_filled() -> None:
    text = abundance_table({"A2": {"t2": 1.0}, "A1": {"t1": 2.5}})
    assert text == "taxon_lineage\tA1\tA2\nt1\t2.5\t0\nt2\t0\t1\n"


def test_rows_table_writes_columns_in_the_given_order() -> None:
    text = rows_table(["b", "a"], [{"a": "1", "b": "2"}, {"a": "3"}])
    assert text == "b\ta\n2\t1\n\t3\n"
