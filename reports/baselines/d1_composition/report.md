# Baselines de D1 con objetivo composicional y validación cruzada por corral (#140)

Generado con `python scripts/compare_baselines_d1_composition.py` en 2826 s, sobre la descarga de D1 del 2026-10-15T05:02:32+00:00.

## Método

- **Cohorte:** 56 animales de la cohorte oficial `1.0.0` (≥ 1000 lecturas SSU): 34 Control, 7 Fitobiótico, 15 Probiótico.
- **Objetivo (D-03, contrato v2 §1, transformación v1.0.0`):** `z_1 = ln(propionato/acetato)`, `z_2 = ln(butirato/acetato)` y `ln T`, con `T = acetato + propionato + n-butirato` calculado por Desarrollo (no el «AGCC totales» del portal). Ningún animal de la cohorte tiene un AGCC igual a cero; si apareciera uno, quedaría sin objetivo composicional, sin pseudoconteo.
- **Validación (D-07, #139):** `StratifiedGroupKFold` agrupado por corral y estratificado por dieta, k = 5, semillas 0 a 9 (plan `configs/splits/d1_holofood_cv.json`, sha256 `a32a191cb6ed…`). Cada celda es la media ± la desviación estándar entre los 50 folds (10 semillas × 5 folds); la dispersión entre semillas está en `metrics.csv` (sufijo `_seed_std`).
- **Ajuste sin fuga:** en cada fold, el escalado y la selección de hiperparámetros (`GroupKFold` interno por corral, 5 folds, grillas de `configs/baselines/`, el mismo criterio `neg_root_mean_squared_error` de A45-2 sobre las tres salidas) se ajustan solo con los animales de entrenamiento del fold.
- **Modelos:** `dummy_mean` (media del entrenamiento), `day_only` (media del entrenamiento del mismo día de muestreo; solo usa el día), `ridge_design` (ridge sobre los factores del diseño: dieta, ensayo, día, sexo y raza en one-hot, 13 columnas) y los baselines de A45-2 (`ridge`, `elasticnet`, `random_forest`, `hist_gradient_boosting`) sobre la tabla completa (1328 columnas: abundancias SSU, dieta y covariables del huésped).

## Advertencias (respuesta de Investigación del 16-10-2026, sección 6; L1 del 25-10-2026)

- **Desbalance 34/15/7 (L1).** La cohorte oficial de 56 animales tiene 34 Control, 15 Probiótico y 7 Fitobiótico (no 37/15/7: es la cohorte de 56, limitación L1 de la respuesta del 25-10-2026). Toda comparación entre tratamientos es **exploratoria**.
- **Dieta confundida con el día de muestreo.** En el día 35 hay 2 Fitobiótico, 25 Control, 3 Probiótico, y el día explica buena parte de la composición; por eso se informan métricas por día y existe `day_only`.
- **Efecto del ensayo.** El ensayo (`trial_code`) aporta 13 puntos de R² a log(propionato/acetato) sin que cambie la dieta (D-03); `ridge_design` lo captura y no separa dieta de ensayo.
- **Folds sin el día 21.** En las semillas 3, 7 y 8 del plan un fold no tiene animales del día 21 (véase `reports/cv/d1_pen_folds.md`); esas celdas se omiten de la agregación y el sufijo `_n` de `metrics.csv` muestra 47 folds en lugar de 50.

## Resultados globales (predicción fuera de fold)

### R² de la fracción

| Modelo | Grupo | Acetato | Propionato | Butirato | Macro |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | Global | -0.24 ± 0.42 | -0.20 ± 0.24 | -0.28 ± 0.57 | -0.24 ± 0.30 |
| `day_only` | Global | 0.25 ± 0.43 | -0.08 ± 0.35 | -0.07 ± 0.46 | 0.04 ± 0.30 |
| `ridge_design` | Global | 0.12 ± 0.50 | 0.17 ± 0.23 | -0.11 ± 0.43 | 0.06 ± 0.29 |
| `ridge` | Global | -0.28 ± 1.30 | -1.27 ± 4.39 | -0.08 ± 0.74 | -0.55 ± 1.99 |
| `elasticnet` | Global | 0.15 ± 0.47 | 0.13 ± 0.31 | -0.06 ± 0.55 | 0.07 ± 0.32 |
| `random_forest` | Global | 0.22 ± 0.38 | 0.20 ± 0.27 | 0.03 ± 0.45 | 0.15 ± 0.27 |
| `hist_gradient_boosting` | Global | 0.02 ± 0.37 | -0.00 ± 0.38 | -0.35 ± 0.65 | -0.11 ± 0.35 |

### MAE de la fracción (puntos porcentuales)

| Modelo | Grupo | Acetato | Propionato | Butirato | Macro |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | Global | 5.55 ± 1.25 | 3.90 ± 1.13 | 4.44 ± 1.07 | 4.63 ± 0.75 |
| `day_only` | Global | 4.18 ± 0.99 | 3.81 ± 0.96 | 4.09 ± 0.89 | 4.03 ± 0.64 |
| `ridge_design` | Global | 4.53 ± 1.16 | 3.23 ± 0.81 | 4.16 ± 1.05 | 3.98 ± 0.72 |
| `ridge` | Global | 5.17 ± 2.00 | 3.99 ± 2.13 | 4.02 ± 1.11 | 4.40 ± 1.54 |
| `elasticnet` | Global | 4.52 ± 1.23 | 3.30 ± 0.87 | 4.04 ± 1.05 | 3.95 ± 0.70 |
| `random_forest` | Global | 4.30 ± 1.18 | 3.25 ± 0.88 | 3.84 ± 0.81 | 3.80 ± 0.71 |
| `hist_gradient_boosting` | Global | 4.76 ± 0.94 | 3.58 ± 1.03 | 4.46 ± 0.95 | 4.27 ± 0.67 |

### log T (total de los tres AGCC, mmol/kg de digesta fresca)

| Modelo | Grupo | R² | MAE |
|---|---|---:|---:|
| `dummy_mean` | Global | -0.32 ± 0.51 | 0.25 ± 0.07 |
| `day_only` | Global | -0.32 ± 0.72 | 0.25 ± 0.06 |
| `ridge_design` | Global | -0.34 ± 0.45 | 0.26 ± 0.08 |
| `ridge` | Global | -0.63 ± 0.94 | 0.27 ± 0.10 |
| `elasticnet` | Global | -0.41 ± 0.79 | 0.25 ± 0.07 |
| `random_forest` | Global | -0.27 ± 0.59 | 0.24 ± 0.07 |
| `hist_gradient_boosting` | Global | -0.84 ± 1.39 | 0.28 ± 0.08 |

### R² de la cantidad reconstruida (mmol/kg)

| Modelo | Grupo | Acetato | Propionato | Butirato | Macro |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | Global | -0.28 ± 0.35 | -0.18 ± 0.18 | -0.32 ± 0.54 | -0.26 ± 0.26 |
| `day_only` | Global | -0.38 ± 0.68 | 0.15 ± 0.28 | -0.01 ± 0.52 | -0.08 ± 0.33 |
| `ridge_design` | Global | -0.47 ± 0.42 | 0.28 ± 0.31 | -0.18 ± 0.49 | -0.12 ± 0.27 |
| `ridge` | Global | -0.60 ± 0.71 | -2.16 ± 7.99 | -0.20 ± 0.60 | -0.99 ± 2.74 |
| `elasticnet` | Global | -0.62 ± 1.59 | 0.21 ± 0.26 | -0.19 ± 0.71 | -0.20 ± 0.74 |
| `random_forest` | Global | -0.31 ± 0.37 | 0.23 ± 0.26 | 0.03 ± 0.52 | -0.02 ± 0.28 |
| `hist_gradient_boosting` | Global | -0.86 ± 0.93 | 0.08 ± 0.37 | -0.23 ± 0.80 | -0.34 ± 0.49 |

### MAE de la cantidad reconstruida (mmol/kg)

| Modelo | Grupo | Acetato | Propionato | Butirato | Macro |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | Global | 13.21 ± 3.16 | 3.54 ± 0.89 | 5.99 ± 1.59 | 7.58 ± 1.42 |
| `day_only` | Global | 14.21 ± 2.70 | 2.98 ± 0.74 | 5.09 ± 1.36 | 7.43 ± 1.06 |
| `ridge_design` | Global | 14.74 ± 3.76 | 2.71 ± 0.61 | 5.68 ± 1.51 | 7.71 ± 1.50 |
| `ridge` | Global | 14.52 ± 3.54 | 3.79 ± 3.25 | 5.57 ± 1.59 | 7.96 ± 2.03 |
| `elasticnet` | Global | 14.22 ± 3.47 | 2.86 ± 0.77 | 5.49 ± 1.59 | 7.52 ± 1.46 |
| `random_forest` | Global | 13.60 ± 3.20 | 2.80 ± 0.75 | 5.11 ± 1.23 | 7.17 ± 1.30 |
| `hist_gradient_boosting` | Global | 15.88 ± 3.74 | 3.00 ± 0.79 | 5.61 ± 1.36 | 8.17 ± 1.49 |

## Resultados por día de muestreo

R² macro de las fracciones y R² de log T por día. Las métricas completas por día están en `metrics.csv` y `fold_metrics.csv`. Dentro de un día la varianza del objetivo es pequeña, así que el denominador del R² tiende a cero y los valores pueden ser muy negativos (día 7 y log T del día 21); la comparación útil entre modelos es la del global y la del MAE por día.

| Modelo | Día | R² macro fracciones | R² log T | folds (n) |
|---|---|---:|---:|---:|
| `dummy_mean` | 7 | -309.84 ± 1476.34 | -1.00 ± 1.53 | 50 |
| `day_only` | 7 | -456.07 ± 2199.08 | -4.42 ± 7.51 | 50 |
| `ridge_design` | 7 | -393.36 ± 1886.94 | -2.05 ± 3.21 | 50 |
| `ridge` | 7 | -286.19 ± 1381.35 | -1.10 ± 2.10 | 50 |
| `elasticnet` | 7 | -299.22 ± 1436.62 | -1.18 ± 1.81 | 50 |
| `random_forest` | 7 | -381.62 ± 1857.66 | -1.50 ± 2.17 | 50 |
| `hist_gradient_boosting` | 7 | -421.79 ± 2106.57 | -2.60 ± 4.04 | 50 |
| `dummy_mean` | 21 | -3.06 ± 9.32 | -354.83 ± 2417.63 | 47 |
| `day_only` | 21 | -3.64 ± 9.05 | -395.88 ± 2684.28 | 47 |
| `ridge_design` | 21 | -2.07 ± 6.71 | -338.98 ± 2293.60 | 47 |
| `ridge` | 21 | -5.48 ± 25.83 | -1451.91 ± 9908.83 | 47 |
| `elasticnet` | 21 | -2.99 ± 10.34 | -473.84 ± 3226.68 | 47 |
| `random_forest` | 21 | -3.01 ± 8.40 | -570.47 ± 3890.37 | 47 |
| `hist_gradient_boosting` | 21 | -4.49 ± 11.35 | -1189.29 ± 8070.59 | 47 |
| `dummy_mean` | 35 | -1.38 ± 0.95 | -1.32 ± 1.94 | 50 |
| `day_only` | 35 | -0.54 ± 0.77 | -0.44 ± 0.63 | 50 |
| `ridge_design` | 35 | -0.62 ± 0.70 | -1.17 ± 1.34 | 50 |
| `ridge` | 35 | -3.02 ± 8.17 | -2.59 ± 4.99 | 50 |
| `elasticnet` | 35 | -0.54 ± 0.66 | -1.27 ± 2.07 | 50 |
| `random_forest` | 35 | -0.38 ± 0.63 | -1.10 ± 1.95 | 50 |
| `hist_gradient_boosting` | 35 | -0.97 ± 1.06 | -1.91 ± 3.59 | 50 |

## Comparación con la Tabla 5 de la respuesta de Investigación (16-10-2026)

La Tabla 5 informa el R² fuera de fold de un ridge sobre los factores del diseño, con el mismo método de validación (StratifiedGroupKFold por corral, k = 5, 10 semillas), sobre su cohorte de 59 animales. Aquí se compara con `ridge_design` sobre la cohorte oficial de 56.

| Objetivo (R² fuera de fold) | Tabla 5, cohorte de 59 | `ridge_design`, cohorte de 56 |
|---|---:|---:|
| Acetato, cantidad | -0.34 | -0.47 ± 0.42 |
| Propionato, cantidad | 0.54 | 0.28 ± 0.31 |
| Butirato, cantidad | 0.14 | -0.18 ± 0.49 |
| Promedio macro, cantidad | 0.11 | -0.12 ± 0.27 |
| Acetato, fracción | 0.32 | 0.12 ± 0.50 |
| Propionato, fracción | 0.40 | 0.17 ± 0.23 |
| Butirato, fracción | 0.10 | -0.11 ± 0.43 |
| Promedio macro, fracción | 0.27 | 0.06 ± 0.29 |
| Total, log T | -0.14 | -0.34 ± 0.45 |

**Causas de las diferencias esperables.** No se espera una igualdad exacta: (1) la Tabla 5 se calculó sobre 59 animales, antes de aplicar a la vez la exclusión de SAMEA112905124 y el umbral de 1000 lecturas (H-01/R-04: la cohorte oficial quedó en 56); (2) la asignación de folds es la de este repositorio (`configs/splits/d1_holofood_cv.json`), porque `d07_corrales.py` de Investigación aún no está versionado (R-06); (3) el alpha del ridge se elige aquí por validación cruzada interna en cada fold (grilla de `configs/baselines/linear.json`), mientras que el procedimiento de selección de la Tabla 5 no está publicado; y (4) el día entra como variable categórica (one-hot). Las cantidades de la Tabla 5 en µmol/g equivalen a mmol/kg (factor 1, V-06) y se comparan con la cantidad reconstruida T × p.

## El día de muestreo frente al diseño completo

Investigación midió que el día aporta 25 de los 47 puntos de R² del diseño en log(propionato/acetato) (D-03, cohorte de 59). En esta corrida, el R² de la fracción de propionato es -0.08 con `day_only` y 0.17 con `ridge_design` (media entre folds, cohorte de 56).

## Preguntas abiertas

- El aporte exacto del día y del ensayo por objetivo quedará cerrado cuando Investigación versione `d03_agcc.py` y `d07_corrales.py` en `docs/research/` (R-06, compromiso del 27-10-2026); entonces la comparación con la Tabla 5 puede hacerse sobre la misma asignación de folds.
- `ridge`, `elasticnet` y los árboles usan la tabla completa (1315 taxones SSU y los factores del diseño); si no superan a `ridge_design`, el microbioma perfilado por SSU no aporta señal fuera del corral para este objetivo (limitación L2: el 55 % de la abundancia queda en nodos residuales).

## Archivos

- `metrics.csv`: agregado por modelo, grupo y métrica (`_mean`, `_std`, `_seed_std`, `_n`).
- `fold_metrics.csv`: una fila por semilla, fold, modelo, grupo y métrica.
- `selections.csv`: hiperparámetros elegidos en cada fold.
- `run.json`: procedencia, configuración y duración.
