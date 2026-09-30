# Reporte de validación del prototipo sintético

- **Tarea:** A35-2 — Validar la integridad del prototipo sintético (#29).
- **Fecha:** 2026-09-29.
- **Grafo validado:** prototipo `HeteroData` de A35-1 (#28), construido desde el dataset de
  escenarios de referencia (DS-04/DS-05).
- **Reglas:** [`graph-integrity-rules.md`](graph-integrity-rules.md), versión `1.1.0`.
- **Entorno:** torch 2.13.0 (CPU) y torch-geometric 2.8.0.

> **Alcance.** Es una validación **estructural**: comprueba que el grafo cumple el contrato y
> es consumible por un modelo. No afirma validez biológica. Todos los datos son sintéticos.

## Cómo reproducirlo

```bash
python scripts/generate_synthetic_dataset.py --graphs --overwrite
python scripts/validate_graph.py --graphs --report artifacts/validation/prototype.json
```

El primer comando genera los escenarios basal e intervenido, sus targets AGCC y sus dos grafos
(`artifacts/synthetic/v1/graphs/`). El segundo carga los grafos con la carga segura y ejecuta
**todas** las reglas: registros (INS, NOD, EDG, CON, OUT, MET) y tensores (TEN).
`tests/integration/test_prototype_validation_report.py` repite esta validación y comprueba que
las cifras de este documento coinciden con el resultado actual.

## Resultado

| Indicador | Valor |
|---|---|
| Estado | valid |
| Familias evaluadas | INS, NOD, EDG, CON, OUT, MET, TEN |
| Familias no evaluadas | ninguna |
| ERROR | 0 |
| ADVERTENCIA | 38 |
| INFO | 0 |
| Grafos entregables | 2 de 2 |

| Grafo | Nodos | Aristas | Targets AGCC | ERROR | ADVERTENCIA | Entregable |
|---|---|---|---|---|---|---|
| `synthetic:scenario:basal:0001` | 32 | 78 | 3 | 0 | 0 | sí |
| `synthetic:scenario:intervened:0001` | 32 | 65 | 3 | 0 | 38 | sí |

| Regla | Severidad | Hallazgos |
|---|---|---|
| INS-06 | ADVERTENCIA | 29 |
| INS-07 | ADVERTENCIA | 9 |

**Tensores.** Las reglas TEN-01 a TEN-13 no producen hallazgos, y `HeteroData.validate()`
devuelve `True` en ambos grafos: los almacenes contienen exactamente los nodos registrados, y el
significado de cada arista sobrevive a la conversión. Cada grafo tiene los ocho tipos de nodo y
las once relaciones. Anchos de `x` (codificación `prototype-0.1`): `diet` 6, `additive` 1,
`substrate` 1, `taxon` 1, `function` 2, `metabolite` 0, `host` 2 y `phenotype` 0. `y` de
`metabolite` tiene forma `[5, 1]`, con 3 filas objetivo (acetato, propionato y butirato). Las
reglas NOD, EDG (incluida EDG-13), CON, OUT y MET tampoco producen hallazgos; OUT se evalúa
sobre `outputs.jsonl` y sobre `data.output_records`.

## Hallazgos

**No hay hallazgos críticos** (ningún `ERROR`), así que el criterio de aceptación de A35-2 se
cumple sin issues de corrección obligatorias. Las 38 advertencias están todas en el escenario
intervenido y muestran que no es comparable con el basal.

**INS-06: 29 valores** difieren del basal fuera de la variable declarada (`crude_protein`, que se
excluye correctamente).

| Tipo | Atributo | Nodos con valor distinto |
|---|---|---|
| `taxon` | `abundance` | 10 |
| `function` | `annotation_value` | 7 |
| `metabolite` | `concentration` | 5 |
| `substrate` | `quantity` | 4 |
| `phenotype` | `value` | 2 |
| `host` | `covariates` | 1 |

**INS-07: 9 relaciones** tienen aristas distintas. Solo 19 aristas son comunes a ambos
escenarios.

| Relación | Solo en basal | Solo en intervención |
|---|---|---|
| `diet -provides-> substrate` | 1 | 0 |
| `additive -modulates-> taxon` | 2 | 2 |
| `additive -modulates-> function` | 1 | 1 |
| `substrate -available_to-> taxon` | 7 | 7 |
| `taxon -has_capacity-> function` | 23 | 16 |
| `taxon -interacts_with-> taxon` | 7 | 8 |
| `function -cross_feeds-> function` | 3 | 4 |
| `function -produces-> metabolite` | 13 | 6 |
| `metabolite -associated_with-> phenotype` | 2 | 2 |

VG-01 anticipa ambas advertencias: el generador siembra valores y aristas con el `graph_id` de
cada escenario. Pero el módulo de escenarios de DS-04 **declara** que el escenario intervenido
mantiene constantes todos los demás nodos, así que los datos contradicen su propia
especificación. Con una consecuencia concreta: los **targets AGCC difieren entre escenarios solo
por la semilla** (acetato 65,070 → 56,264 `mmol/kg`, sintético), y un modelo vería un "efecto" de
la proteína cruda que nadie programó. Aunque no es un hallazgo crítico según el criterio de
A35-2, se abrió la issue de corrección **#46**, porque afecta directamente la comparación de
escenarios.

## Conclusión

El prototipo de A35-1 es **estructuralmente íntegro y entregable** según las reglas `1.1.0`:
ningún error en registros ni en tensores. Las advertencias no bloquean la entrega, pero muestran
que los escenarios sintéticos no son comparables mientras no se corrija #46. Hasta entonces, no
se deben interpretar las diferencias entre escenarios, incluidas las de los targets.
