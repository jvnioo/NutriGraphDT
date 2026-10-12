# Tabla comparativa consolidada de baselines (A40-6)

- **Cohorte:** `synthetic_baseline_cohort` (50 instancias sintéticas, semillas 1 a 50).
- **Partición (A40-1):** semilla `42` (30 train, 10 val, 10 test).
- **Atributos (A40-3):** 24 columnas tabulares sin fuga.
- **Validación cruzada:** 5 folds agrupados sobre train.
- **Hiperparámetros elegidos:**
  - `dummy_mean`: sin hiperparámetros (predice la media de train).
  - `ridge`: {'model__alpha': 1000.0} (borde superior de la grilla, alpha = 1000.0).
  - `elasticnet`: {'model__alpha': 10.0, 'model__l1_ratio': 0.9} (anula coeficientes, idéntico a dummy_mean).
  - `random_forest`: {'max_depth': None, 'min_samples_leaf': 5, 'n_estimators': 300}.
  - `hist_gradient_boosting`: {'estimator__learning_rate': 0.05, 'estimator__max_depth': 3, 'estimator__max_iter': 100, 'estimator__min_samples_leaf': 2}.

> [!WARNING]
> **Advertencia metodológica para el Informe de Avance 2 (Célula de Documentación)**:
> Esta tabla es **exclusivamente sintética** (la partición de D1 en `configs/splits/d1_holofood.json` cubre por ahora solo el fixture de 6 animales) y **no mide desempeño predictivo real ni constituye un piso empírico para la GNN**.
>
> En el generador sintético actual, las concentraciones de AGCC no dependen de los 24 atributos tabulares. Por ello, ningún baseline supera a la media ($R^2$ macro en test negativo en todos los modelos: -0.18 en `dummy_mean`, -0.90 en `hist_gradient_boosting`), `elasticnet` anula todos los coeficientes reproduciendo a `dummy_mean`, y `ridge` queda en el límite superior de la grilla (alpha = 1000.0).
>
> El valor de esta tabla radica únicamente en demostrar y verificar que el flujo de entrenamiento, partición sin fuga, validación cruzada y extracción de métricas opera de manera reproducible.

### Promedio macro de los tres AGCC (acetato, propionato, butirato)

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 7.5050 | 8.3610 | -0.0501 | 0.0% |
| `dummy_mean` | test | 6.2485 | 7.2502 | -0.1804 | 0.0% |
| `ridge` | val | 7.5049 | 8.3715 | -0.0515 | 0.0% |
| `ridge` | test | 6.2431 | 7.2610 | -0.1842 | 0.0% |
| `elasticnet` | val | 7.5050 | 8.3610 | -0.0501 | 0.0% |
| `elasticnet` | test | 6.2485 | 7.2502 | -0.1804 | 0.0% |
| `random_forest` | val | 7.8706 | 8.7605 | -0.1308 | 0.0% |
| `random_forest` | test | 6.3666 | 7.3331 | -0.2026 | 0.0% |
| `hist_gradient_boosting` | val | 9.5900 | 10.3729 | -0.6167 | 0.0% |
| `hist_gradient_boosting` | test | 7.6145 | 8.6579 | -0.8970 | 0.0% |

### Detalle por objetivo: Acetate

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 10.9942 | 12.3330 | -0.0000 | 0.0% |
| `dummy_mean` | test | 11.8474 | 13.6319 | -0.4160 | 0.0% |
| `ridge` | val | 11.0000 | 12.3683 | -0.0057 | 0.0% |
| `ridge` | test | 11.8278 | 13.6472 | -0.4192 | 0.0% |
| `elasticnet` | val | 10.9942 | 12.3330 | -0.0000 | 0.0% |
| `elasticnet` | test | 11.8474 | 13.6319 | -0.4160 | 0.0% |
| `random_forest` | val | 11.8406 | 13.2779 | -0.1591 | 0.0% |
| `random_forest` | test | 12.2042 | 13.8571 | -0.4632 | 0.0% |
| `hist_gradient_boosting` | val | 13.6590 | 15.1567 | -0.5103 | 0.0% |
| `hist_gradient_boosting` | test | 13.4268 | 14.8185 | -0.6733 | 0.0% |

### Detalle por objetivo: Propionate

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 6.3741 | 6.9640 | -0.0491 | 0.0% |
| `dummy_mean` | test | 3.5237 | 4.0276 | -0.0001 | 0.0% |
| `ridge` | val | 6.3580 | 6.9639 | -0.0491 | 0.0% |
| `ridge` | test | 3.5539 | 4.0510 | -0.0117 | 0.0% |
| `elasticnet` | val | 6.3741 | 6.9640 | -0.0491 | 0.0% |
| `elasticnet` | test | 3.5237 | 4.0276 | -0.0001 | 0.0% |
| `random_forest` | val | 6.5619 | 7.1448 | -0.1043 | 0.0% |
| `random_forest` | test | 3.5403 | 3.9323 | 0.0467 | 0.0% |
| `hist_gradient_boosting` | val | 8.8713 | 9.1084 | -0.7947 | 0.0% |
| `hist_gradient_boosting` | test | 4.6662 | 5.4650 | -0.8413 | 0.0% |

### Detalle por objetivo: Butyrate

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 5.1467 | 5.7860 | -0.1012 | 0.0% |
| `dummy_mean` | test | 3.3743 | 4.0912 | -0.1250 | 0.0% |
| `ridge` | val | 5.1567 | 5.7824 | -0.0998 | 0.0% |
| `ridge` | test | 3.3476 | 4.0849 | -0.1215 | 0.0% |
| `elasticnet` | val | 5.1467 | 5.7860 | -0.1012 | 0.0% |
| `elasticnet` | test | 3.3743 | 4.0912 | -0.1250 | 0.0% |
| `random_forest` | val | 5.2091 | 5.8589 | -0.1291 | 0.0% |
| `random_forest` | test | 3.3553 | 4.2097 | -0.1911 | 0.0% |
| `hist_gradient_boosting` | val | 6.2396 | 6.8536 | -0.5451 | 0.0% |
| `hist_gradient_boosting` | test | 4.7504 | 5.6903 | -1.1763 | 0.0% |
