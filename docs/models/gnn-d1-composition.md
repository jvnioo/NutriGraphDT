# GNN de D1 con objetivo composicional y CV por corral (#142)

La respuesta de Investigación del 16-10-2026 (D-03 y D-07) reemplaza el marco con el que se
evaluaron las GNN en A45-4 a A45-6 (#104 a #106: partición 2.0.0, `test` fijo de 21 animales,
objetivo en concentración). Este documento describe la reevaluación: la cabeza y la pérdida
composicionales, la detención temprana interna a cada fold, la repetición de la búsqueda de
A45-5 (#105) bajo validación cruzada y la ablación de aristas `inferred` (V-01, respuesta 3).
El reporte generado vive en [`reports/gnn/d1_composition/`](../../reports/gnn/d1_composition/);
la comparación de referencia es la de los baselines composicionales (#140,
[`reports/baselines/d1_composition/`](../../reports/baselines/d1_composition/)).

Código: `nutrigraphdt.models.training.compositional`. Script:
`scripts/evaluate_gnn_d1_composition.py`. Requiere los extras `graph` y `baselines` y los
grafos guardados de D1 (`scripts/build_graph.py --save-graphs`).

```bash
python scripts/build_graph.py --save-graphs --overwrite   # si no están guardados
python scripts/evaluate_gnn_d1_composition.py
```

## Cabeza y pérdida composicionales

La arquitectura no cambia: la cabeza lineal de tres salidas (`ScfaRegressionHead`) pasa a
predecir el objetivo del contrato v2, sección 1 (#146): `z_1 = ln(propionato/acetato)`,
`z_2 = ln(butirato/acetato)` y `ln T`. `CompositionalTargetTransform` deriva el objetivo de
`y_graph` con `compositional_graph_target` (sin pseudoconteo: un animal con un AGCC ausente, no
finito o ≤ 0 no tiene objetivo) y lo estandariza con un `TargetScaler` ajustado **solo con el
train del fold**. La pérdida es el MSE estandarizado sobre los animales con objetivo válido
(`masked_mse_loss` con la máscara de validez `[B, 1]` replicada a las tres salidas). La
evaluación invierte la estandarización y aplica `evaluate_composition` (métricas de D-03,
globales y por día de muestreo).

## Protocolo sin fuga

1. Grafos entregables de la cohorte oficial de 56 animales (`configs/cohorts/d1_holofood.json`)
   con los tres AGCC medidos.
2. Plan de folds versionado en `configs/splits/d1_holofood_cv.json` (#139):
   `StratifiedGroupKFold` por corral, estratificado por dieta, k = 5, semillas 0 a 9 (50 folds).
3. En cada fold, todo lo que se ajusta a los datos (escalado de features y del objetivo, pesos)
   usa solo el train del fold. La **detención temprana** usa un **val interno** del train del
   fold: `split_inner_validation` aparta un quinto de los corrales con
   `StratifiedGroupKFold` (grupo corral, estrato dieta) y una semilla derivada de la del fold
   (`--train-seed-base`, por defecto 42000: `base + semilla_plan × 100 + fold`). El test del
   fold solo se evalúa al final, con los pesos de la mejor época en el val interno.
4. La **selección de hiperparámetros** (la grilla de A45-5: `hidden_channels` ∈ {32, 64, 128} ×
   `num_layers` ∈ {1, 2, 3}) tampoco lee ningún test: cada combinación se entrena en los folds
   de las `--selection-seeds` primeras semillas del plan y se puntúa con la pérdida en el val
   interno del train de cada fold; se elige el mínimo por variante (empate: menor capacidad).
   Queda registrada en `selection.csv` y `selection.json` (`test_used: false`).

Los dos criterios de aceptación del Issue se cumplen por construcción: ningún animal del test
de un fold interviene en el escalado, la detención temprana ni la selección, y el criterio de
F4 se declara con la incertidumbre entre folds y semillas y frente a `day_only`.

## Ablación de aristas `inferred`

`drop_inferred_edges` elimina de cada grafo las aristas con `evidence_status == "inferred"`
(filtrando `edge_index` y los atributos de evidencia) y el script repite la evaluación con el
brazo `without_inferred`. **En los grafos actuales de D1 no hay ninguna arista `inferred`**:
la única relación es `metabolite → measured_in → host` (observada); los enlaces
taxón–función–metabolito están pendientes (S-04). Por eso, cuando el conteo de aristas
inferidas es cero, el script no repite el brazo (sería el mismo grafo) y el reporte declara la
ablación como sin efecto medible todavía.

## Limitaciones declaradas

- **Taxones aislados (S-04 pendiente).** Sin nodos de función ni aristas que los conecten, los
  1315 taxones no reciben mensajes; la GNN solo los usa por la lectura media, como un baseline
  tabular. La ventaja estructural queda sin probar (limitaciones L2 y L3).
- **Efecto del ensayo.** `trial_code` entra como covariable del huésped desde #147 (sección 6
  de la respuesta); la dieta está confundida con el día de muestreo (ver el reporte de #140).
- La incertidumbre es la dispersión entre folds y semillas del plan; la semilla de
  entrenamiento es una por fold (derivada), así que el ruido de optimización no se marginaliza
  como en A45-5.

## Salidas

`report.md` (declaración de F4, tablas globales y por día, ablación), `metrics.csv` (agregado
`_mean`, `_std`, `_seed_std`, `_n`), `fold_metrics.csv`, `predictions.csv`, `folds.csv`
(diagnóstico por fold), `selection.csv` / `selection.json` y `run.json`. Los archivos por fold
se escriben de forma incremental: una corrida interrumpida deja resultados parciales usables.
