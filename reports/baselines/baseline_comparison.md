# Tabla comparativa consolidada de baselines (A40-6)

- **Cohorte:** `synthetic_baseline_cohort` (50 instancias sintéticas, semillas 1 a 50).
- **Partición (A40-1):** semilla `42` (30 train, 10 val, 10 test).
- **Atributos (A40-3):** 24 columnas tabulares sin fuga.
- **Validación cruzada:** 5 folds agrupados sobre train.

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
