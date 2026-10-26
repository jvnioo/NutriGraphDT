# Baselines de D1 con objetivo composicional y CV por corral (#140)

La respuesta de Investigación del 16-10-2026 (Tabla 7) fija como compromiso de Desarrollo
repetir los baselines de A45-2 con el **objetivo composicional** de D-03 bajo la
**validación cruzada por corral** de D-07 (#139), y agregar un baseline que use **solo el día
de muestreo**. Este documento describe el protocolo; el reporte generado vive en
[`reports/baselines/d1_composition/`](../../reports/baselines/d1_composition/).

Código: `nutrigraphdt.models.compositional_baselines`. Script:
`scripts/compare_baselines_d1_composition.py`. Requiere el extra `baselines` y la descarga de
D1 (`scripts/fetch_holofood.py`).

```bash
python scripts/compare_baselines_d1_composition.py
```

Un solo comando regenera el reporte desde la descarga registrada en `configs/sources.json`;
no descarga ni modifica `data/raw/`.

## Objetivo y métricas

El objetivo es el de D-03 (contrato v2, sección 1; #146): `z_1 = ln(propionato/acetato)`,
`z_2 = ln(butirato/acetato)` y `ln T`, con `T = acetato + propionato + n-butirato` calculado
por Desarrollo. La transformación es la de `nutrigraphdt.models.composition`, la misma que usa
la GNN. Las métricas son las de D-03 (`evaluate_composition`): R² y MAE de cada fracción en
puntos porcentuales y su promedio macro, R² y MAE de `ln T`, y R² y MAE de las cantidades
reconstruidas `T × p` en mmol/kg, todo global y **por día de muestreo**, con media y dispersión
entre folds y semillas (`aggregate_fold_reports`).

Ninguna log-razón admite ceros: un animal con un AGCC igual a cero queda sin objetivo
composicional y `prepare_compositional_data` rechaza la tabla en lugar de inventar un
pseudoconteo. En la cohorte oficial no hay ceros (VR-3 de la respuesta del 25-10-2026).

## Modelos

| Modelo | Entrada | Ajuste |
|---|---|---|
| `dummy_mean` | — | media del entrenamiento del fold |
| `day_only` | solo `host:sampling_day` | media del entrenamiento del mismo día (media global si el día no aparece) |
| `ridge_design` | factores del diseño: dieta, ensayo, día, sexo y raza (one-hot) | ridge + `StandardScaler`, alpha por CV interna |
| `ridge`, `elasticnet` | tabla completa (A40-3, con las covariables de #147) | como en A45-2 |
| `random_forest`, `hist_gradient_boosting` | tabla completa | como en A45-2 |

- `day_only` es el piso que fija la edad del animal: sin él no se puede saber si un modelo
  aprende algo más que el día (el día aporta 25 de los 47 puntos de R² del diseño en
  log(propionato/acetato), D-03).
- `ridge_design` reproduce el modelo de la **Tabla 5** de la respuesta de Investigación (ridge
  sobre los factores del diseño), lo que permite comparar cifras y acotar cuánto explica el
  diseño sin el microbioma. Sus columnas son las de `DESIGN_FEATURE_BASES`.

## Protocolo sin fuga

1. La tabla de atributos se limita a la cohorte oficial de 56 animales
   (`configs/cohorts/d1_holofood.json`, #138).
2. El plan de folds es el versionado en `configs/splits/d1_holofood_cv.json` (#139):
   `StratifiedGroupKFold` por corral, estratificado por dieta, k = 5, semillas 0 a 9. El
   script falla si los animales del plan no coinciden con la cohorte.
3. En cada fold, todo lo que se ajusta (escalado, hiperparámetros, modelo) se ajusta solo con
   los animales de entrenamiento del fold. La selección usa un `GroupKFold` interno agrupado
   por corral (`--inner-folds`, 5 por defecto), con las grillas de `configs/baselines/` y el
   mismo criterio de A45-2 (`neg_root_mean_squared_error` sobre las tres salidas). Es una
   decisión de implementación: A45-2 usaba un `GroupKFold` con un grupo por corral sobre la
   partición fija de A45-1, que aquí no se usa.
4. Los folds se pueden evaluar en paralelo (`--n-jobs`, por defecto todos los núcleos); el
   resultado es idéntico al de la ejecución serial porque cada fold es determinista.

Las filas del reporte llevan `split = "cv"`: son predicciones **fuera de fold**, sin relación
con la partición fija de A45-1 (conservada para reproducir las corridas de A45).

## Advertencias que acompañan al reporte

- **Desbalance 34/15/7 (L1).** La cohorte oficial de 56 animales tiene 34 Control, 15
  Probiótico y 7 Fitobiótico (no 37/15/7, que era la cohorte de 59). Toda comparación entre
  tratamientos es exploratoria.
- **Dieta confundida con el día de muestreo** y **efecto del ensayo** en la composición
  (sección 6 de la respuesta del 16-10-2026).
- **Folds sin el día 21** en las semillas 3, 7 y 8 del plan (véase
  [cross-validation.md](cross-validation.md)): esas celdas se omiten de la agregación y el
  sufijo `_n` de `metrics.csv` muestra 47 folds en lugar de 50.

## Comparación con la Tabla 5

La Tabla 5 informa el R² fuera de fold del ridge de Investigación sobre los factores del
diseño, con el mismo método de validación, sobre su cohorte de 59 animales. El reporte la
compara con `ridge_design` (constante `INVESTIGATION_TABLE5` del módulo, columna «Cohorte
(59)»). No se espera igualdad exacta: la cohorte oficial quedó en 56 (H-01/R-04), la
asignación de folds es la de este repositorio hasta que Investigación versione
`d07_corrales.py` (R-06), el alpha se elige por CV interna (el procedimiento de la Tabla 5 no
está publicado) y el día entra como categórica. Las cantidades en µmol/g equivalen a mmol/kg
(factor 1, V-06) y se comparan con la cantidad reconstruida `T × p`.

## Archivos del reporte

- `report.md`: método, advertencias, tablas globales y por día, comparación con la Tabla 5 y
  preguntas abiertas.
- `metrics.csv`: agregado por modelo, grupo y métrica (`_mean`, `_std`, `_seed_std`, `_n`).
- `fold_metrics.csv`: una fila por semilla, fold, modelo, grupo y métrica.
- `selections.csv`: hiperparámetros elegidos por la selección interna de cada fold.
- `run.json`: procedencia (fuentes, plan, manifiesto de la descarga), configuración, versión
  de la transformación y duración.
