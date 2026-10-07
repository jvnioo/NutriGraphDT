"""Comprueba que el diccionario del grafo refleje el esquema estructural en código."""

from __future__ import annotations

import re
from pathlib import Path

from nutrigraphdt.graph.schema import ALLOWED_RELATIONS, GRAPH_SCHEMA_VERSION, NODE_TYPES

ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = ROOT / "docs" / "graph-data-dictionary.md"
NODE_TABLE_HEADING = "## Tipos de nodo y atributos"
SOURCE_TABLE_HEADING = "## Fuentes de datos asignadas por tipo de nodo"
RELATION_TABLE_HEADING = "## Relaciones y atributos de arista"
DIAGRAM_HEADING = "## Diagrama del esquema"
ARROW_BY_STATUS = {
    "approved_structure": "==>",
    "provisional": "-->",
    "hypothetical": "-.->",
}
EXPECTED_SOURCES = {
    "diet": (
        "Principal: metadatos de D1 (HoloFood Data Portal). Complementaria: "
        "Feedtables y FooDB para traducir dietas a metabolitos."
    ),
    "additive": "sin fuente asignada por Investigación",
    "substrate": "sin fuente asignada por Investigación",
    "taxon": (
        "Principal: D1 (HoloFood Data Portal) y D2 (PRJNA902117 (SRA) + modelos en GitHub). "
        "Complementaria: catálogos D5 (colección de Feng et al., 2021), D6 "
        "(catálogo de Gilroy et al., 2021) y D7 (MGnify chicken-gut v1.0.1)."
    ),
    "function": (
        "Principal: anotación con KEGG, MetaCyc y CAZy. Complementaria: modelos de D2 y D3 "
        "(Zenodo 6083555)."
    ),
    "metabolite": (
        "Principal: D1 (HoloFood Data Portal) y D4 (MTBLS560, MetaboLights). "
        "Complementaria: D13 (MTBLS13078, MetaboLights)."
    ),
    "host": "sin fuente asignada por Investigación",
    "phenotype": (
        "Principal: D1 (HoloFood Data Portal) y D4 (MTBLS560, MetaboLights). "
        "Complementaria: D3 (Zenodo 6083555)."
    ),
}


def _section(document: str, heading: str) -> str:
    heading_pattern = re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE)
    match = heading_pattern.search(document)
    assert match is not None, f"Falta el encabezado {heading!r}"

    next_heading = re.search(r"^#{1,2} .+$", document[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(document)
    return document[match.end() : end]


def _table_rows(document: str, heading: str) -> list[list[str]]:
    section = _section(document, heading)
    lines = section.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip().startswith("|")), None)
    assert start is not None, f"No se encontró una tabla bajo {heading!r}"

    rows: list[list[str]] = []
    for line in lines[start:]:
        if not line.strip().startswith("|"):
            if rows:
                break
            continue
        cells = [cell.strip().replace("`", "") for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)

    assert rows, f"La tabla bajo {heading!r} está vacía"
    return rows


def _diagram(document: str) -> str:
    section = _section(document, DIAGRAM_HEADING)
    match = re.search(r"```mermaid\s*\n(.*?)```", section, re.DOTALL)
    assert match is not None, "No se encontró el bloque Mermaid bajo su encabezado"
    return match.group(1)


def test_node_attribute_table_matches_graph_schema() -> None:
    document = DOCUMENT.read_text(encoding="utf-8")
    rows = _table_rows(document, NODE_TABLE_HEADING)
    assert rows[0] == [
        "Tipo de nodo",
        "Identificador",
        "Atributo",
        "Tipo de dato",
        "Unidad / campo de unidad",
        "Estado",
    ]

    expected = {
        (
            node.spanish_name,
            node.identifier,
            attribute_name,
            attribute.data_type,
            attribute.unit_field or "—",
            attribute.structural_status,
        )
        for node in NODE_TYPES.values()
        for attribute_name, attribute in node.attributes.items()
    }
    assert {tuple(row) for row in rows[1:]} == expected


def test_data_source_table_covers_nodes_and_marks_unassigned_sources() -> None:
    document = DOCUMENT.read_text(encoding="utf-8")
    rows = _table_rows(document, SOURCE_TABLE_HEADING)
    assert rows[0] == [
        "Tipo de nodo (spanish_name)",
        "Identificador",
        "Fuentes según Tabla 5",
    ]

    sources = {row[1]: (row[0], row[2]) for row in rows[1:]}
    assert set(sources) == set(NODE_TYPES)
    for identifier, node in NODE_TYPES.items():
        assert sources[identifier][0] == node.spanish_name

    assert sources == {
        identifier: (NODE_TYPES[identifier].spanish_name, source)
        for identifier, source in EXPECTED_SOURCES.items()
    }


def test_relation_table_matches_graph_schema() -> None:
    document = DOCUMENT.read_text(encoding="utf-8")
    rows = _table_rows(document, RELATION_TABLE_HEADING)
    assert rows[0] == [
        "Tripleta (origen, relación, destino)",
        "Semántica",
        "Atributos obligatorios",
        "Estado estructural",
    ]

    actual = {tuple(row) for row in rows[1:]}
    expected = set()
    for edge_type, relation in ALLOWED_RELATIONS.items():
        attributes = "—"
        if relation.required_attributes:
            attributes = "; ".join(
                f"{name}: {spec.data_type}"
                + (f" (unidad en {spec.unit_field})" if spec.unit_field else "")
                for name, spec in relation.required_attributes.items()
            )
        triplet = f"({edge_type[0]}, {edge_type[1]}, {edge_type[2]})"
        expected.add((triplet, relation.semantics, attributes, relation.structural_status))

    assert actual == expected


def test_mermaid_nodes_and_edge_arrows_match_graph_schema() -> None:
    document = DOCUMENT.read_text(encoding="utf-8")
    assert f'`GRAPH_SCHEMA_VERSION = "{GRAPH_SCHEMA_VERSION}"`' in document
    assert "provisional" in document
    assert "no reemplaza la validación de Investigación" in document
    diagram = _diagram(document)

    actual_nodes = {
        identifier: label
        for identifier, label in re.findall(r'^\s*(\w+)\["([^"]+)"\]\s*$', diagram, re.MULTILINE)
    }
    assert actual_nodes == {
        identifier: node.spanish_name for identifier, node in NODE_TYPES.items()
    }

    actual_edges = set(
        re.findall(
            r"^\s*(\w+)\s+(==>|-->|-\.->)\|([^|]+)\|\s+(\w+)\s*$",
            diagram,
            re.MULTILINE,
        )
    )
    expected_edges = {
        (
            edge_type[0],
            ARROW_BY_STATUS[relation.structural_status],
            f"{edge_type[1]}/{relation.structural_status}",
            edge_type[2],
        )
        for edge_type, relation in ALLOWED_RELATIONS.items()
    }
    assert actual_edges == expected_edges
