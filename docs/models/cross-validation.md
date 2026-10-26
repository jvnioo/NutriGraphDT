# Validación cruzada por corral de D1 (D-07, #139)

La respuesta de Investigación del 16-10-2026 (sección 4.7, D-07) fija la **evaluación principal
de D1**: validación cruzada agrupada por corral (`pen_code`) y estratificada por dieta
(`StratifiedGroupKFold`), con **k = 5** y **al menos 10 semillas**, informando media y
dispersión. La respuesta del 25-10-2026 (R-04) confirma la cohorte oficial de 56 animales
(umbral de 1000 lecturas SSU) y pide rehacer la tabla de folds sobre ella; el umbral de 5000
queda como análisis de sensibilidad.

Código: `nutrigraphdt.models.cross_validation`. Script: `scripts/create_cv_folds.py`. Requiere
el extra `baselines` (scikit-learn).

## Método

- `make_pen_folds(animales, k=5, seeds=range(10))` usa
  `sklearn.model_selection.StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=semilla)`
  sobre los animales ordenados por `sample_id`, con `pen_code` como grupo y la dieta
  (`diet_treatment_code`) como estrato. El resultado no depende del orden de entrada.
- Rechaza `k` mayor que los corrales de la dieta con menos corrales (`max_folds`; 6 para `CE`
  en la cohorte de 56, 5 con el umbral de 5000), menos de 10 semillas, semillas repetidas,
  `sample_id` repetidos y corrales con más de una dieta.
- `check_plan` verifica, para cada semilla, que **las tres dietas estén en todos los folds** y
  que **ningún corral esté en más de un fold**. `make_pen_folds` falla si no se cumple.

Se descartan, como indica D-07, dejar un corral fuera por fold (16 de 32 folds tendrían un solo
animal) y dejar un ensayo fuera (el ensayo CC no tiene Probiótico).

## Asignación versionada

`PenFoldPlan` guarda `assignments[semilla][sample_id] = fold`, con el método, `k`, las semillas
y la cohorte (versión de la configuración, umbral y tamaño). `scripts/create_cv_folds.py` la
escribe en `configs/splits/d1_holofood_cv.json` (siempre con fines de línea LF).

```bash
python scripts/fetch_holofood.py                     # si falta la descarga de D1
python scripts/create_cv_folds.py                    # cohorte oficial, semillas 0 a 9
python scripts/create_cv_folds.py --seeds 100 --report-only            # comparación con D-07
python scripts/create_cv_folds.py --min-ssu-reads 5000 --report-only   # sensibilidad
```

## Tabla de folds

`fold_table` describe cada fold de cada semilla: animales, corrales, animales y corrales por
dieta, días de muestreo presentes y **días faltantes**. La dieta está confundida con el día de
muestreo (en el día 35 casi todos los animales son Control), así que algunos folds quedan sin
algún día; D-07 lo encontró en 40 de 100 semillas sobre la cohorte de 59. `summarize_fold_table`
resume los rangos y las semillas afectadas. El script escribe la tabla en
`reports/cv/d1_pen_folds.md` y `.json`, junto a los valores de Investigación:

| Indicador | Investigación (cohorte de 59) |
|---|---|
| Animales por fold | 11 a 13 |
| Corrales por fold | 5 a 8 |
| Dietas | las tres en todos los folds |
| Semillas con algún fold sin un día | 40 de 100 |

La comparación exacta, fold por fold, requiere `d07_corrales.py`, que Investigación subirá a
`docs/research/` (R-06).

## Entrenar y evaluar por fold

`run_cross_validation(plan, runner)` llama a `runner(semilla, fold, train_ids, test_ids)` en
cada fold de cada semilla. El `runner` entrena desde cero con `train_ids` (escalado e
hiperparámetros ajustados solo con ellos) y devuelve un `EvaluationReport` sobre `test_ids`:
`evaluate_predictions` para los baselines o `evaluate_composition` (#146) para el objetivo
composicional, que agrega las métricas por día de muestreo en la columna `group`.

`aggregate_fold_reports` agrupa por modelo, subconjunto, grupo y métrica, y escribe cuatro filas
por combinación:

| Sufijo | Contenido |
|---|---|
| `_mean` | media entre todos los folds de todas las semillas |
| `_std` | desviación estándar muestral entre todos los folds de todas las semillas |
| `_seed_std` | desviación estándar muestral entre las medias por semilla |
| `_n` | número de folds con valor |

Las celdas `nan` (por ejemplo, un día ausente en un fold) se omiten de esa celda.

## `test` fijo

**Decisión pendiente del sublíder de Desarrollo.** Investigación no exige un `test` fijo además
de la validación cruzada. Hasta que se decida, la partición 2.0.0 (`d1_holofood.json`) se
conserva sin cambios para reproducir las corridas de A45, y la validación cruzada es la
evaluación principal de las comparaciones nuevas (#140, #142).
