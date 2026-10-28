# GNN de D1 con objetivo composicional y validación cruzada por corral (#142)

Generado con `python scripts/evaluate_gnn_d1_composition.py` en 11793 s.

## Método

- **Cohorte:** 56 animales de la cohorte oficial (versión 1.0.0, ≥ 1000 lecturas SSU) con los tres AGCC y su grafo entregable.
- **Objetivo (D-03, contrato v2 §1, transformación v1.0.0`):** la cabeza de tres salidas predice `(z_1, z_2, ln T)` = (ln(propionato/acetato), ln(butirato/acetato), ln T); la pérdida es el MSE estandarizado (media y desviación del train del fold) sobre los animales con objetivo válido, sin pseudoconteo.
- **Validación (D-07, #139):** plan `configs/splits/d1_holofood_cv.json` (k = 5, semillas 0 a 9; sha256 `a32a191cb6ed…`). Cada celda es la media ± la desviación estándar entre los folds evaluados; la dispersión entre semillas está en `metrics.csv` (sufijo `_seed_std`).
- **Sin fuga:** en cada fold, el escalado de features y del objetivo se ajusta solo con el train del fold y la detención temprana usa un **val interno** del train del fold, agrupado por corral y estratificado por dieta (un quinto de los corrales; semilla derivada de la del fold, base 42000). El test del fold solo se evalúa al final.
- **Selección de hiperparámetros (A45-5 repetida bajo CV):** la grilla [32, 64, 128] × [1, 2, 3] de `hidden_channels` × `num_layers` se evaluó solo con animales de entrenamiento de los folds de las semillas [0, 1] (val interno por corral; `selection.csv` y `selection.json`). Configuraciones elegidas: `hetero_gat` 128×2, `hetero_sage` 128×3, `homo_sage` 128×2.
- **Entrenamiento:** lr 0.001, weight_decay 0.0001, batch 16, máx. 200 épocas, paciencia 20, dispositivo `cpu`.

## Criterio de salida de F4

El criterio de F4 pide que una GNN iguale o supere al menos un baseline, ahora con el objetivo composicional (D-03) y la validación cruzada por corral (D-07). Se evalúa con el **R² macro de las fracciones, global**, media ± desviación estándar entre los folds y semillas (las mismas 50 particiones para todos los modelos, así que las diferencias son pareadas).

- Mejor GNN: `homo_sage` con 0.07 ± 0.31.
- `day_only`: 0.04 ± 0.30. La mejor GNN iguala o supera a `day_only` (diferencia 0.03; la dispersión combinada de las medias es 0.43).
- Mejor baseline: `random_forest` con 0.15 ± 0.27. **Criterio de F4: no se cumple** (`homo_sage` 0.07 ± 0.31 frente a 0.15 ± 0.27; una diferencia menor que la dispersión entre folds no es concluyente).

## Resultados globales (predicción fuera de fold)

### R² de la fracción

| Modelo | Acetato | Propionato | Butirato | Macro |
|---|---:|---:|---:|---:|
| `homo_sage` | 0.14 ± 0.54 | 0.16 ± 0.35 | -0.09 ± 0.44 | 0.07 ± 0.31 |
| `hetero_sage` | 0.12 ± 0.50 | 0.14 ± 0.31 | -0.13 ± 0.40 | 0.04 ± 0.27 |
| `hetero_gat` | 0.11 ± 0.54 | 0.18 ± 0.31 | -0.11 ± 0.42 | 0.06 ± 0.33 |
| `dummy_mean` (baseline #140) | -0.24 ± 0.42 | -0.20 ± 0.24 | -0.28 ± 0.57 | -0.24 ± 0.30 |
| `day_only` (baseline #140) | 0.25 ± 0.43 | -0.08 ± 0.35 | -0.07 ± 0.46 | 0.04 ± 0.30 |
| `ridge_design` (baseline #140) | 0.12 ± 0.50 | 0.17 ± 0.23 | -0.11 ± 0.43 | 0.06 ± 0.29 |
| `ridge` (baseline #140) | -0.28 ± 1.30 | -1.27 ± 4.39 | -0.08 ± 0.74 | -0.55 ± 1.99 |
| `elasticnet` (baseline #140) | 0.15 ± 0.47 | 0.13 ± 0.31 | -0.06 ± 0.55 | 0.07 ± 0.32 |
| `random_forest` (baseline #140) | 0.22 ± 0.38 | 0.20 ± 0.27 | 0.03 ± 0.45 | 0.15 ± 0.27 |
| `hist_gradient_boosting` (baseline #140) | 0.02 ± 0.37 | -0.00 ± 0.38 | -0.35 ± 0.65 | -0.11 ± 0.35 |

### MAE de la fracción (puntos porcentuales)

| Modelo | Acetato | Propionato | Butirato | Macro |
|---|---:|---:|---:|---:|
| `homo_sage` | 4.41 ± 1.13 | 3.19 ± 0.82 | 4.07 ± 0.94 | 3.89 ± 0.66 |
| `hetero_sage` | 4.48 ± 1.13 | 3.23 ± 0.81 | 4.12 ± 0.92 | 3.94 ± 0.66 |
| `hetero_gat` | 4.52 ± 1.11 | 3.18 ± 0.83 | 4.13 ± 1.03 | 3.95 ± 0.68 |
| `dummy_mean` (baseline #140) | 5.55 ± 1.25 | 3.90 ± 1.13 | 4.44 ± 1.07 | 4.63 ± 0.75 |
| `day_only` (baseline #140) | 4.18 ± 0.99 | 3.81 ± 0.96 | 4.09 ± 0.89 | 4.03 ± 0.64 |
| `ridge_design` (baseline #140) | 4.53 ± 1.16 | 3.23 ± 0.81 | 4.16 ± 1.05 | 3.98 ± 0.72 |
| `ridge` (baseline #140) | 5.17 ± 2.00 | 3.99 ± 2.13 | 4.02 ± 1.11 | 4.40 ± 1.54 |
| `elasticnet` (baseline #140) | 4.52 ± 1.23 | 3.30 ± 0.87 | 4.04 ± 1.05 | 3.95 ± 0.70 |
| `random_forest` (baseline #140) | 4.30 ± 1.18 | 3.25 ± 0.88 | 3.84 ± 0.81 | 3.80 ± 0.71 |
| `hist_gradient_boosting` (baseline #140) | 4.76 ± 0.94 | 3.58 ± 1.03 | 4.46 ± 0.95 | 4.27 ± 0.67 |

### log T (total de los tres AGCC)

| Modelo | R² | MAE |
|---|---:|---:|
| `homo_sage` | -0.35 ± 0.61 | 0.26 ± 0.07 |
| `hetero_sage` | -0.38 ± 0.54 | 0.27 ± 0.07 |
| `hetero_gat` | -0.38 ± 0.71 | 0.26 ± 0.07 |
| `dummy_mean` (baseline #140) | -0.32 ± 0.51 | 0.25 ± 0.07 |
| `day_only` (baseline #140) | -0.32 ± 0.72 | 0.25 ± 0.06 |
| `ridge_design` (baseline #140) | -0.34 ± 0.45 | 0.26 ± 0.08 |
| `ridge` (baseline #140) | -0.63 ± 0.94 | 0.27 ± 0.10 |
| `elasticnet` (baseline #140) | -0.41 ± 0.79 | 0.25 ± 0.07 |
| `random_forest` (baseline #140) | -0.27 ± 0.59 | 0.24 ± 0.07 |
| `hist_gradient_boosting` (baseline #140) | -0.84 ± 1.39 | 0.28 ± 0.08 |

### R² de la cantidad reconstruida (mmol/kg)

| Modelo | Acetato | Propionato | Butirato | Macro |
|---|---:|---:|---:|---:|
| `homo_sage` | -0.43 ± 0.45 | 0.24 ± 0.51 | -0.17 ± 0.54 | -0.12 ± 0.32 |
| `hetero_sage` | -0.49 ± 0.49 | 0.26 ± 0.38 | -0.26 ± 0.70 | -0.17 ± 0.35 |
| `hetero_gat` | -0.42 ± 0.46 | 0.26 ± 0.35 | -0.20 ± 0.53 | -0.12 ± 0.30 |
| `dummy_mean` (baseline #140) | -0.28 ± 0.35 | -0.18 ± 0.18 | -0.32 ± 0.54 | -0.26 ± 0.26 |
| `day_only` (baseline #140) | -0.38 ± 0.68 | 0.15 ± 0.28 | -0.01 ± 0.52 | -0.08 ± 0.33 |
| `ridge_design` (baseline #140) | -0.47 ± 0.42 | 0.28 ± 0.31 | -0.18 ± 0.49 | -0.12 ± 0.27 |
| `ridge` (baseline #140) | -0.60 ± 0.71 | -2.16 ± 7.99 | -0.20 ± 0.60 | -0.99 ± 2.74 |
| `elasticnet` (baseline #140) | -0.62 ± 1.59 | 0.21 ± 0.26 | -0.19 ± 0.71 | -0.20 ± 0.74 |
| `random_forest` (baseline #140) | -0.31 ± 0.37 | 0.23 ± 0.26 | 0.03 ± 0.52 | -0.02 ± 0.28 |
| `hist_gradient_boosting` (baseline #140) | -0.86 ± 0.93 | 0.08 ± 0.37 | -0.23 ± 0.80 | -0.34 ± 0.49 |

### MAE de la cantidad reconstruida (mmol/kg)

| Modelo | Acetato | Propionato | Butirato | Macro |
|---|---:|---:|---:|---:|
| `homo_sage` | 14.89 ± 3.81 | 2.63 ± 0.72 | 5.55 ± 1.24 | 7.69 ± 1.46 |
| `hetero_sage` | 15.18 ± 3.75 | 2.66 ± 0.73 | 5.66 ± 1.27 | 7.83 ± 1.42 |
| `hetero_gat` | 14.87 ± 3.68 | 2.66 ± 0.65 | 5.65 ± 1.35 | 7.73 ± 1.41 |
| `dummy_mean` (baseline #140) | 13.21 ± 3.16 | 3.54 ± 0.89 | 5.99 ± 1.59 | 7.58 ± 1.42 |
| `day_only` (baseline #140) | 14.21 ± 2.70 | 2.98 ± 0.74 | 5.09 ± 1.36 | 7.43 ± 1.06 |
| `ridge_design` (baseline #140) | 14.74 ± 3.76 | 2.71 ± 0.61 | 5.68 ± 1.51 | 7.71 ± 1.50 |
| `ridge` (baseline #140) | 14.52 ± 3.54 | 3.79 ± 3.25 | 5.57 ± 1.59 | 7.96 ± 2.03 |
| `elasticnet` (baseline #140) | 14.22 ± 3.47 | 2.86 ± 0.77 | 5.49 ± 1.59 | 7.52 ± 1.46 |
| `random_forest` (baseline #140) | 13.60 ± 3.20 | 2.80 ± 0.75 | 5.11 ± 1.23 | 7.17 ± 1.30 |
| `hist_gradient_boosting` (baseline #140) | 15.88 ± 3.74 | 3.00 ± 0.79 | 5.61 ± 1.36 | 8.17 ± 1.49 |

## Resultados por día de muestreo

R² macro de las fracciones y R² de log T por día (media ± std entre folds). Dentro de un día la varianza del objetivo es pequeña y el R² puede ser muy negativo; la comparación útil es la del global y la del MAE por día (`metrics.csv`).

| Modelo | Día | R² macro fracciones | R² log T |
|---|---|---:|---:|
| `homo_sage` | 7 | -516.34 ± 2509.92 | -3.56 ± 7.67 |
| `hetero_sage` | 7 | -406.50 ± 1965.34 | -3.58 ± 7.92 |
| `hetero_gat` | 7 | -506.88 ± 2467.74 | -3.86 ± 8.32 |
| `homo_sage` | 21 | -2.70 ± 9.03 | -415.40 ± 2803.29 |
| `hetero_sage` | 21 | -3.11 ± 10.16 | -281.50 ± 1889.54 |
| `hetero_gat` | 21 | -2.80 ± 8.33 | -938.58 ± 6387.64 |
| `homo_sage` | 35 | -0.53 ± 0.76 | -0.89 ± 1.08 |
| `hetero_sage` | 35 | -0.63 ± 1.00 | -1.03 ± 1.59 |
| `hetero_gat` | 35 | -0.58 ± 0.79 | -0.94 ± 1.36 |

## Ablación de aristas `inferred` (V-01, respuesta 3)

**Los grafos actuales de D1 no tienen ninguna arista `inferred`** (solo `metabolite → measured_in → host`, observada; los enlaces taxón–función–metabolito están pendientes, S-04). Por eso los brazos `with_inferred` y `without_inferred` son idénticos y el segundo no se repitió: la ablación queda implementada en `drop_inferred_edges` y verificada en tests, pero su efecto solo podrá medirse cuando el grafo incluya aristas inferidas.

## Advertencias y limitaciones

- **Taxones aislados (S-04 pendiente).** Sin nodos de función ni aristas que los conecten, los 1315 taxones de cada grafo no reciben mensajes: la GNN solo puede usarlos por la lectura media, igual que un baseline tabular. La ventaja estructural de la GNN queda sin probar hasta cerrar S-04 (limitación L2/L3).
- **Desbalance 34/15/7 (L1).** Toda comparación entre tratamientos es exploratoria.
- **Dieta confundida con el día de muestreo** y **efecto del ensayo** (`trial_code`, que entra como covariable del huésped desde #147, sección 6 de la respuesta): ver `reports/baselines/d1_composition/report.md`.
- **Folds sin el día 21.** En las semillas 3, 7 y 8 un fold no tiene animales del día 21; esas celdas se omiten de la agregación (`_n` en `metrics.csv`).
- La incertidumbre informada es la dispersión entre folds y semillas del plan; la semilla de entrenamiento de la GNN es una por fold (derivada), así que el ruido de optimización no se marginaliza como en A45-5.

## Archivos

- `metrics.csv`: agregado por variante, brazo, grupo y métrica (`_mean`, `_std`, `_seed_std`, `_n`).
- `fold_metrics.csv`: una fila por semilla, fold, variante, brazo, grupo y métrica.
- `predictions.csv`: salida `(z_1, z_2, ln T)` por animal de test.
- `folds.csv`: diagnóstico por fold (mejor época, épocas, tamaños, errores).
- `selection.csv` / `selection.json`: grilla de A45-5 bajo CV y elección por variante.
- `run.json`: procedencia, configuración y duración.
