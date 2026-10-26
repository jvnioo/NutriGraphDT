"""Covariables del huésped del contrato de datos v2 §3 (#147).

Recorre el fixture real de D1 (`tests/fixtures/holofood/`): metadatos → `host_covariates` de la
instancia → nodo `host` → columnas one-hot de `x` y tabla de atributos de los baselines.
Comprueba que `pen_code` y `body_weight_g` nunca entran a `x` ni a la tabla, y que un valor
fuera del vocabulario se informa. Requiere el extra `graph`.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.covariates import (  # noqa: E402
    HOST_COVARIATES_BY_NAME,
    INPUT_COVARIATES,
    covariate_vocabularies,
)
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.data.schema import (  # noqa: E402
    NormalizedInstanceRecord,
    NormalizedTabularDataset,
)
from nutrigraphdt.data.split import get_split  # noqa: E402
from nutrigraphdt.graph.builder import build_hetero_graph, records_from_tables  # noqa: E402
from nutrigraphdt.graph.heterodata import derive_schema  # noqa: E402
from nutrigraphdt.graph.validation import find_node_findings  # noqa: E402
from nutrigraphdt.models.tabular import build_tabular_dataset  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")

FIXTURE_COVARIATES = {
    # Fila de tests/fixtures/holofood/metadata.tsv (pen_code CA21, día 7).
    "SAMEA112904764": {
        "trial_code": "CA",
        "pen_code": "CA21",
        "sampling_day": 7,
        "sex": "male",
        "breed": "Ross",
    }
}


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


def _tables() -> NormalizedTabularDataset:
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    return tables


@pytest.fixture(scope="module")
def tables() -> NormalizedTabularDataset:
    return _tables()


def _with_covariate(
    tables: NormalizedTabularDataset, sample_id: str, **changes: object
) -> NormalizedTabularDataset:
    instances = [
        dataclasses.replace(i, host_covariates={**i.host_covariates, **changes})
        if i.sample_id == sample_id
        else i
        for i in tables.instances
    ]
    return dataclasses.replace(tables, instances=instances)


def test_instances_carry_typed_contract_covariates(tables: NormalizedTabularDataset) -> None:
    by_sample = {i.sample_id: i for i in tables.instances}
    for sample_id, expected in FIXTURE_COVARIATES.items():
        assert by_sample[sample_id].host_covariates == expected
    for instance in tables.instances:
        assert set(instance.host_covariates) == {
            "trial_code",
            "pen_code",
            "sampling_day",
            "sex",
            "breed",
        }
        assert isinstance(instance.host_covariates["sampling_day"], int)


def test_host_node_declares_covariates_and_body_weight(tables: NormalizedTabularDataset) -> None:
    records = records_from_tables(tables)
    host = next(
        n
        for n in records.nodes
        if n["node_type"] == "host" and n["node_id"] == "SAMEA112904764:host"
    )
    covariates = host["attributes"]["covariates"]
    assert covariates == {**FIXTURE_COVARIATES["SAMEA112904764"], "body_weight_g": 187.6}
    assert records.metadata["vocabularies"] == covariate_vocabularies()


def test_pen_code_and_body_weight_never_enter_x(tables: NormalizedTabularDataset) -> None:
    built = build_hetero_graph(tables)
    columns = built.records.metadata["node_feature_schema"]["host"]
    names = [column["name"] for column in columns]
    assert not [n for n in names if "pen_code" in n or "body_weight" in n]
    expected = [
        f"covariates.{c.name}={category}" for c in INPUT_COVARIATES for category in c.vocabulary
    ]
    assert names == expected
    assert {column["encoding"] for column in columns} == {"one_hot"}

    data = built.graphs["D1_holofood:SAMEA112904764"]
    row = dict(zip(names, data["host"].x[0].tolist(), strict=True))
    assert not bool(data["host"].missing_mask.any())
    hot = sorted(name for name, value in row.items() if value == 1.0)
    assert hot == [
        "covariates.breed=Ross",
        "covariates.sampling_day=7",
        "covariates.sex=male",
        "covariates.trial_code=CA",
    ]


def test_missing_or_unknown_covariate_is_masked(tables: NormalizedTabularDataset) -> None:
    changed = _with_covariate(tables, "SAMEA112904764", sex=None, breed="Hubbard")
    built = build_hetero_graph(changed)
    names = [c["name"] for c in built.records.metadata["node_feature_schema"]["host"]]
    data = built.graphs["D1_holofood:SAMEA112904764"]
    masked = {n for n, m in zip(names, data["host"].missing_mask[0].tolist(), strict=True) if m}
    assert masked == {
        "covariates.sex=female",
        "covariates.sex=male",
        "covariates.breed=Ross",
        "covariates.breed=Cobb",
    }
    host = next(
        n
        for n in built.records.nodes
        if n["node_type"] == "host" and n["node_id"] == "SAMEA112904764:host"
    )
    assert host["missing_mask"]["covariates.sex"] is True


def test_out_of_vocabulary_value_is_reported(tables: NormalizedTabularDataset) -> None:
    records = records_from_tables(_with_covariate(tables, "SAMEA112904764", sampling_day=14))
    findings = find_node_findings(records.instances, records.nodes, metadata=records.metadata)
    nod11 = [f for f in findings if f.rule_id == "NOD-11"]
    assert [f.location.get("attribute") for f in nod11] == ["covariates.sampling_day"]
    assert nod11[0].graph_id == "D1_holofood:SAMEA112904764"


def test_integration_reports_out_of_vocabulary_metadata() -> None:
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    base = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    payload = MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load()
    raw = [
        {**r, "value": "Hubbard"}
        if r["sample_id"] == "SAMEA112904764" and r["field"] == "breed"
        else r
        for r in payload.raw_data
    ]
    _, report = attach_sample_context(base, metadata=dataclasses.replace(payload, raw_data=raw))
    assert report.out_of_vocabulary == (("SAMEA112904764", "breed", "Hubbard"),)


def test_baseline_table_has_input_covariates_but_not_pen_or_weight(
    tables: NormalizedTabularDataset,
) -> None:
    tabular = build_tabular_dataset(tables, split=get_split(split_file=FIXTURES / "split.json"))
    host = {n for n in tabular.feature_names if n.startswith("host:")}
    assert host == {"host:trial_code", "host:sampling_day", "host:sex", "host:breed"}
    sample = next(s for s in tabular.samples if s.sample_id == "SAMEA112904764")
    assert sample.features["host:sampling_day"] == "7"
    columns, _ = tabular.to_numeric_matrix(one_hot=True)
    assert not [c for c in columns if "pen_code" in c or "body_weight" in c]


def test_synthetic_encoding_is_unchanged() -> None:
    from nutrigraphdt.data.synthetic import generate_synthetic_dataset

    dataset = generate_synthetic_dataset()
    schema = derive_schema(dataset.nodes, dataset.edges, dataset.outputs)
    names = [column.name for column in schema.node["host"]]
    assert names == ["covariates.age_days (d)", "covariates.body_weight_g (g)"]
    assert "vocabularies" not in dataset.metadata or not any(
        key.startswith("covariates.") for key in dataset.metadata.get("vocabularies", {})
    )


def test_instance_covariates_round_trip_through_tsv(
    tables: NormalizedTabularDataset, tmp_path: Path
) -> None:
    instance = next(i for i in tables.instances if i.sample_id == "SAMEA112904764")
    paths = NormalizedTabularDataset(instances=[instance]).export_tables(tmp_path)
    import csv

    with paths["instances"].open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle, delimiter="\t"))
    assert NormalizedInstanceRecord.from_dict({**row, "is_synthetic": False}) == instance


def test_covariate_normalization_and_vocabulary() -> None:
    day = HOST_COVARIATES_BY_NAME["sampling_day"]
    assert day.normalize(35.0) == 35
    assert day.normalize("21") == 21
    assert day.normalize("") is None
    with pytest.raises(ValueError, match="entero"):
        day.normalize(7.5)
    assert day.in_vocabulary(7) and not day.in_vocabulary(14)
    trial = HOST_COVARIATES_BY_NAME["trial_code"]
    assert trial.normalize(" CB ") == "CB"
    assert HOST_COVARIATES_BY_NAME["pen_code"].in_vocabulary("ZZ99")  # sin vocabulario cerrado
