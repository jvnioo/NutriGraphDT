# Validación de integridad del grafo: guía de uso

- **Tarea:** VG-07 — Integrar el validador al pipeline y generar reportes (#17).
- **Reglas:** [`graph-integrity-rules.md`](graph-integrity-rules.md), versión `1.2.0`.

Esta guía explica cómo validar un dataset y sus grafos antes de entregarlos a un modelo, cómo
leer el reporte y qué significa cada severidad. Las reglas, sus severidades y sus excepciones
están en la especificación; aquí solo se describe su uso.

> **Alcance.** La validación es **estructural**: comprueba que el grafo cumple el contrato y es
> consumible por un modelo. No afirma validez biológica, causalidad ni calidad de la evidencia.
> Un grafo sin errores no es una representación confirmada del organismo.

## Qué se valida

| Familia | Qué comprueba | Se evalúa sobre |
|---|---|---|
| `INS` | Instancias, y escenarios basal/intervención comparables. | `instances.jsonl`, `nodes.jsonl` |
| `NOD` | Tipos, identificadores y atributos de los nodos. | `nodes.jsonl` |
| `EDG` | Tuplas permitidas, extremos, evidencia y atributos de las aristas. | `edges.jsonl` |
| `CON` | Nodos aislados y componentes desconectados. Nunca es `ERROR`. | nodos y aristas |
| `OUT` | Salidas y targets. | `outputs.jsonl` y `data.output_records` |
| `MET` | Campos mínimos y coherencia de `metadata.json` con los archivos. | `metadata.json` |
| `TEN` | Dimensiones, tipos e índices de los tensores. | `HeteroData` (extra `graph`) |

## Efecto de cada severidad

| Severidad | ¿Se entrega el grafo al modelo? | Qué hacer |
|---|---|---|
| `ERROR` | **No.** Un error de nivel dataset (`graph_id = null`, por ejemplo MET-03) retiene **todos** los grafos. | Corregir el origen del defecto y regenerar. |
| `ADVERTENCIA` | Sí. | Revisarla. Queda en el reporte para revisión humana. |
| `INFO` | Sí. | Nada: registra una excepción admitida (por ejemplo, un aditivo de control aislado). |

Las reglas de tensores solo se evalúan en grafos sin `ERROR` de registro, porque convertir
registros inválidos produciría tensores sin significado. El reporte indica en `not_evaluated`
qué no se evaluó y por qué: un reporte sin hallazgos solo cubre lo evaluado.

## Desde la línea de comandos

Después de exportar un dataset (ver la [guía del dataset sintético](synthetic-dataset-usage.md)):

```bash
python scripts/generate_synthetic_dataset.py --graphs
python scripts/validate_graph.py --graphs
python scripts/validate_graph.py --input artifacts/synthetic/v1 --graphs --report artifacts/validation/report.json
```

El script imprime el estado, las familias evaluadas, los conteos por severidad, qué instancias
son entregables, las reglas con hallazgos y los primeros errores. Con `--report` escribe el
reporte completo en JSON. Con `--graphs`, carga también los `HeteroData` del prototipo
([A35-1](heterodata-prototype.md); por defecto, `<input>/graphs`) con la carga segura y evalúa
las reglas `TEN`. Requiere el extra `graph`.

| Código de salida | Significado |
|---|---|
| `0` | Sin hallazgos `ERROR`. Puede haber advertencias. |
| `1` | Hay hallazgos `ERROR`; los grafos afectados no deben entregarse al modelo. |
| `2` | El dataset o los grafos no se pudieron leer (falta un archivo, una línea no es JSON, un `.pt` es rechazado por la carga segura o los grafos son de otro dataset). |

El script lee los archivos **sin** rechazar el primer defecto, a diferencia de `load_dataset`,
para informar todos los hallazgos. Sin `--graphs`, las reglas `TEN` no se evalúan y el reporte
lo indica en `not_evaluated`.

## Desde Python

`validate_graph` es la interfaz común. Recibe un `SyntheticDataset`, un `RawDataset` leído con
`read_raw_dataset` o cualquier objeto con `metadata`, `instances`, `nodes`, `edges` y `outputs`:

```python
from nutrigraphdt.data.synthetic import export_dataset, generate_scenario_dataset
from nutrigraphdt.graph.validation import read_raw_dataset, validate_graph

export_dataset(generate_scenario_dataset(), "artifacts/synthetic/v1", overwrite=True)
report = validate_graph(read_raw_dataset("artifacts/synthetic/v1"))

print(report.is_valid)  # True: los escenarios por defecto no producen hallazgos
print(report.deliverable_graph_ids)
for finding in report.warnings[:3]:
    print(finding.rule_id, finding.message)
```

Cada hallazgo (`Finding`) tiene `rule_id`, `severity`, `graph_id`, `location`, `expected`,
`observed` y `message`, como define la especificación. `report.to_dict()` devuelve una
estructura estable y compatible con JSON:

```python
import json
from pathlib import Path

summary = report.to_dict()
print(summary["status"], summary["summary"], summary["not_evaluated"])
Path("artifacts/validation").mkdir(parents=True, exist_ok=True)
Path("artifacts/validation/report.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
```

| Campo de `to_dict()` | Contenido |
|---|---|
| `report_format`, `rules_version`, `schema_version` | Versiones del reporte, de las reglas y del contrato de datos. |
| `scope` | Recordatorio de que la validación es estructural. |
| `status` | `valid` si no hay ningún `ERROR`; `invalid` si hay alguno. |
| `summary`, `dataset_errors` | Conteo por severidad y número de errores de nivel dataset. |
| `graphs` | Por instancia: si es entregable y sus conteos por severidad. |
| `rules` | Por regla: severidad y número de hallazgos. |
| `evaluated`, `not_evaluated` | Familias evaluadas y, por familia o instancia, qué no se evaluó y por qué. |
| `findings` | Todos los hallazgos: primero los de nivel dataset y luego por instancia y regla. |

Para exigir que un conjunto de grafos sea entregable, `require_deliverable` lanza
`GraphIntegrityError` con los grafos bloqueados y sus errores:

```python
from nutrigraphdt.graph.validation import GraphIntegrityError, require_deliverable

try:
    require_deliverable(report)
except GraphIntegrityError as error:
    print(error.graph_ids, error)
```

## Antes del modelo

El punto del pipeline previo al modelo es `prepare_graphs_for_model`. Recibe los registros y los
`HeteroData` construidos (uno por `graph_id`), valida todo y devuelve **solo** los grafos
entregables, junto con el reporte. Requiere el extra `graph` (ver
[`development.md`](development.md#optional-graph-extra-pytorch-and-pytorch-geometric)).

```python
from nutrigraphdt.graph.validation import prepare_graphs_for_model


def graphs_for_training(dataset, heterodata):
    """`heterodata`: {graph_id: HeteroData}, p. ej. de `build_synthetic_graphs` (A35-1)."""
    delivered, report = prepare_graphs_for_model(dataset, heterodata)
    for graph_id in report.blocked_graph_ids:
        print(f"{graph_id} retenido:", [f.rule_id for f in report.blocking_findings(graph_id)])
    return delivered
```

El constructor debe declarar las columnas de `x` y `edge_attr` en `node_feature_schema` y
`edge_feature_schema` como listas ordenadas (ver los criterios de VG-05 en la especificación) y
terminar con `data.validate(raise_on_error=True)`, como exige DS-01.

## Validadores individuales

Cada familia también se puede ejecutar por separado. Todas las funciones devuelven una lista de
`Finding` y no modifican los registros:

| Función | Reglas |
|---|---|
| `find_node_findings(instances, nodes, metadata=...)` | NOD-01 a NOD-12, INS-01 a INS-04 |
| `find_edge_findings(nodes, edges, metadata=...)` | EDG-01 a EDG-13 |
| `find_connectivity_findings(nodes, edges, metadata=...)` | CON-01 a CON-04 |
| `find_scenario_findings(instances, nodes, edges)` | INS-05 a INS-07 |
| `find_output_findings(outputs, nodes, instances)` | OUT-01 a OUT-04 |
| `find_metadata_findings(metadata, instances, nodes, edges, outputs)` | MET-01 a MET-03 |
| `tensors.find_tensor_findings(data, instance=..., nodes=..., edges=..., metadata=...)` | TEN-01 a TEN-13 |

## Limitaciones

- **Tensores.** Los únicos `HeteroData` reales son los del prototipo sintético (A35-1), con una
  codificación provisional. El constructor definitivo es A39-1 (#35).
- **Escenarios sintéticos.** Desde la corrección de #46, los escenarios basal e intervenido
  difieren solo en `crude_protein` y no producen advertencias INS-06 ni INS-07 (ver la
  [guía del dataset](synthetic-dataset-usage.md#limitaciones)).
- **Variable intervenida.** INS-06 reconoce la variable declarada en `diet_treatment` solo con la
  convención del exportador (`etiqueta:variable=valor`), hasta que exista un mecanismo formal
  (§6.1-ii del Esquema General).
- **Reglas provisionales.** Varias reglas dependen de decisiones pendientes de Investigación y
  se marcan (P) en la especificación.
