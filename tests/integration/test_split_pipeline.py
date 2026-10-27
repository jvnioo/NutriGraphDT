"""Prueba de integración de la partición train/val/test con los grafos reales de HoloFood (A40-1).

Comprueba que una partición de `get_split()` se integra directamente con el flujo de construcción
de grafos heterogéneos de la actividad 39 (`build_hetero_graph`), permitiendo filtrar las
instancias de grafos en train, val y test sin pérdida ni duplicación. Usa la partición del
fixture de seis animales (`tests/fixtures/holofood/split.json`), no la canónica de D1.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from nutrigraphdt.data.config import load_sources  # noqa: E402
from nutrigraphdt.data.integration import attach_sample_context  # noqa: E402
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader  # noqa: E402
from nutrigraphdt.data.pipeline import DataPipeline  # noqa: E402
from nutrigraphdt.data.split import get_split  # noqa: E402
from nutrigraphdt.graph.builder import build_hetero_graph  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "holofood"
SOURCES = load_sources(REPO_ROOT / "configs" / "sources.json")


def _source(source_id: str, file_name: str):  # type: ignore[no-untyped-def]
    return dataclasses.replace(SOURCES[source_id], path_or_url=str(FIXTURES / file_name))


def test_split_partitions_built_hetero_graphs_without_leakage() -> None:
    """Verifica que el split particione los grafos construidos de la act. 39 sin fuga."""
    # 1. Construir los grafos de la fuente D1 HoloFood
    abundance = _source("D1_holofood", "abundance_ssu_caecum.tsv")
    tables = DataPipeline({"D1_holofood": abundance}).run(["D1_holofood"]).dataset
    tables, _ = attach_sample_context(
        tables,
        metadata=MetadataLoader(_source("D1_holofood_metadata", "metadata.tsv")).load(),
        metabolites=MetaboliteLoader(
            _source("D1_holofood_scfa_content", "scfa_caecum_content.tsv")
        ).load(),
    )
    built = build_hetero_graph(tables)
    graphs = built.graphs
    assert len(graphs) == 6

    # 2. Obtener la partición canónica versionada
    split = get_split(split_file=FIXTURES / "split.json")

    # 3. Filtrar los grafos usando split.filter
    train_graphs, val_graphs, test_graphs = split.filter(graphs)

    assert len(train_graphs) == len(split.train)
    assert len(val_graphs) == len(split.val)
    assert len(test_graphs) == len(split.test)
    assert len(train_graphs) + len(val_graphs) + len(test_graphs) == 6

    # 4. Asegurar que las claves de los grafos son estrictamente disjuntas
    train_keys = set(train_graphs.keys())
    val_keys = set(val_graphs.keys())
    test_keys = set(test_graphs.keys())

    assert train_keys.isdisjoint(val_keys)
    assert train_keys.isdisjoint(test_keys)
    assert val_keys.isdisjoint(test_keys)
    assert train_keys | val_keys | test_keys == set(graphs.keys())

    # 5. Cada grafo contiene los nodos taxon y host esperados
    for g in train_graphs.values():
        # Contrato v2 §6 (#150): p__Actinobacteria y c__Actinobacteria ya no colisionan,
        # pasando de 439 a 440 nodos taxonómicos distintos.
        assert g["taxon"].num_nodes == 440
        assert g["host"].num_nodes == 1
