# Reporte de validación del prototipo sintético

- **Tarea:** A35-2 — Validar la integridad del prototipo sintético (#29).
- **Validación inicial:** 2026-09-29.
- **Actualización:** 2026-10-06, tras corregir la comparabilidad de escenarios en #46.
- **Grafo validado:** prototipo `HeteroData` de A35-1 (#28), construido desde el dataset de
  escenarios de referencia (DS-04/DS-05).
- **Reglas:** [`graph-integrity-rules.md`](graph-integrity-rules.md), versión `1.2.0`.
- **Entorno de esta actualización:** Python 3.14.5, torch 2.14.1+cpu y torch-geometric 2.8.0.post1.

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
| ADVERTENCIA | 0 |
| INFO | 0 |
| Grafos entregables | 2 de 2 |

| Grafo | Nodos | Aristas | Targets AGCC | ERROR | ADVERTENCIA | Entregable |
|---|---|---|---|---|---|---|
| `synthetic:scenario:basal:0001` | 32 | 78 | 3 | 0 | 0 | sí |
| `synthetic:scenario:intervened:0001` | 32 | 78 | 3 | 0 | 0 | sí |

| Regla | Severidad | Hallazgos |
|---|---|---|

Ninguna regla produce hallazgos. En particular, INS-06 no detecta diferencias de valores de
nodos fuera de la intervención e INS-07 no detecta diferencias de aristas entre escenarios.

**Tensores.** Las reglas TEN-01 a TEN-13 no producen hallazgos, y `HeteroData.validate()`
devuelve `True` en ambos grafos: los almacenes contienen exactamente los nodos registrados, y el
significado de cada arista sobrevive a la conversión. Cada grafo tiene los ocho tipos de nodo y
las once relaciones. Anchos de `x` (codificación `prototype-0.1`): `diet` 6, `additive` 1,
`substrate` 1, `taxon` 1, `function` 2, `metabolite` 0, `host` 2 y `phenotype` 0. `y` de
`metabolite` tiene forma `[5, 1]`, con 3 filas objetivo (acetato, propionato y butirato). Las
reglas NOD, EDG (incluida EDG-13), CON, OUT y MET tampoco producen hallazgos; OUT se evalúa
sobre `outputs.jsonl` y sobre `data.output_records`.

## Comparación basal/intervenido

La validación inicial (2026-09-29) reportó 38 advertencias en el escenario intervenido (INS-06:
29; INS-07: 9), porque el generador sembraba valores y aristas con el `graph_id` de cada
escenario. Ese hallazgo motivó la issue #46; esta sección refleja el estado tras la corrección.

El escenario intervenido copia los nodos y las aristas basales y reasigna su `graph_id`; cada
registro conserva así el identificador de su escenario. Fuera de esos identificadores, solo
cambia el valor de `crude_protein` en la composición de la dieta: `215.0` a `270.0 g/kg`.
Los escenarios conservan 32 nodos, 78 aristas y 3 targets por grafo.

| Target sintético | Valor basal | Valor intervenido | Unidad |
|---|---:|---:|---|
| Acetato | 65,070 | 65,070 | mmol/kg |
| Propionato | 22,358 | 22,358 | mmol/kg |
| Butirato | 14,649 | 14,649 | mmol/kg |

Los targets AGCC son idénticos porque el generador sintético no modela ni predice ningún efecto
de la intervención de proteína cruda sobre los metabolitos. Esta igualdad es una consecuencia
de copiar los datos basales, no evidencia de que la intervención carezca de efecto biológico.
No debe interpretarse como un resultado fisiológico ni causal.

## Conclusión

El prototipo de A35-1 es **estructuralmente íntegro y entregable** según las reglas `1.2.0` (sus reglas para datos sintéticos no cambian desde `1.1.0`):
ningún error ni advertencia en registros o tensores. Los dos escenarios por defecto son
comparables como entradas sintéticas porque difieren únicamente en `crude_protein`. La
comparación no representa una simulación de respuesta biológica: no se ha modelado ningún efecto
de la intervención sobre sustratos, taxones o metabolitos.
