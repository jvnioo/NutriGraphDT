# Tabla comparativa consolidada de baselines en D1 HoloFood (A45-2)

- **Cohorte:** D1 HoloFood, 59 animales con los tres AGCC.
- **Partición (A45-1):** 31 train, 7 val, 21 test.
- **Grupos de CV:** `pen_code`; 17 corrales en train.
- **Validación cruzada:** 17 folds agrupados sobre train.
- **Verificación target GNN:** las muestras y valores de los tres AGCC coinciden con `add_graph_target` (detalle en `run.json`).
- **Hiperparámetros elegidos:**
  - `dummy_mean`: sin hiperparámetros (predice la media de train).
  - `ridge`: {'model__alpha': 1000.0}.
  - `elasticnet`: {'model__alpha': 1.0, 'model__l1_ratio': 0.5}.
  - `random_forest`: {'max_depth': 6, 'min_samples_leaf': 1, 'n_estimators': 300}.
  - `hist_gradient_boosting`: {'estimator__learning_rate': 0.1, 'estimator__max_depth': None, 'estimator__max_iter': 100, 'estimator__min_samples_leaf': 5}.

### Promedio macro de los tres AGCC (acetato, propionato, butirato)

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 8.9840 | 10.9311 | -0.5612 | 0.0% |
| `dummy_mean` | test | 7.1686 | 9.7534 | -0.0361 | 0.0% |
| `ridge` | val | 8.6994 | 10.5696 | -0.0747 | 0.0% |
| `ridge` | test | 6.8209 | 9.0134 | 0.1793 | 0.0% |
| `elasticnet` | val | 9.6162 | 11.7079 | -0.3704 | 0.0% |
| `elasticnet` | test | 7.7642 | 10.9969 | -0.2342 | 0.0% |
| `random_forest` | val | 9.8161 | 11.8594 | -0.5706 | 0.0% |
| `random_forest` | test | 7.2836 | 9.5595 | 0.0685 | 0.0% |
| `hist_gradient_boosting` | val | 11.8852 | 13.4953 | -1.2834 | 0.0% |
| `hist_gradient_boosting` | test | 7.7156 | 10.0078 | 0.0159 | 0.0% |

### Detalle por objetivo: Acetate

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 16.1485 | 20.3398 | -0.0271 | 0.0% |
| `dummy_mean` | test | 12.0030 | 16.8148 | -0.0272 | 0.0% |
| `ridge` | val | 16.5913 | 20.8487 | -0.0792 | 0.0% |
| `ridge` | test | 12.2032 | 16.4455 | 0.0175 | 0.0% |
| `elasticnet` | val | 18.7278 | 23.2630 | -0.3436 | 0.0% |
| `elasticnet` | test | 14.0615 | 20.7324 | -0.5616 | 0.0% |
| `random_forest` | val | 18.7026 | 23.4788 | -0.3686 | 0.0% |
| `random_forest` | test | 13.0776 | 17.3840 | -0.0979 | 0.0% |
| `hist_gradient_boosting` | val | 24.3101 | 27.9572 | -0.9405 | 0.0% |
| `hist_gradient_boosting` | test | 15.2165 | 19.0686 | -0.3210 | 0.0% |

### Detalle por objetivo: Propionate

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 3.2902 | 3.8461 | -1.5178 | 0.0% |
| `dummy_mean` | test | 3.6098 | 4.4768 | -0.0301 | 0.0% |
| `ridge` | val | 2.2066 | 2.5115 | -0.0736 | 0.0% |
| `ridge` | test | 2.8559 | 3.6260 | 0.3243 | 0.0% |
| `elasticnet` | val | 2.8834 | 3.0384 | -0.5713 | 0.0% |
| `elasticnet` | test | 3.2936 | 4.9419 | -0.2552 | 0.0% |
| `random_forest` | val | 3.3582 | 3.6277 | -1.2399 | 0.0% |
| `random_forest` | test | 3.1661 | 3.9616 | 0.1934 | 0.0% |
| `hist_gradient_boosting` | val | 4.4781 | 4.8497 | -3.0032 | 0.0% |
| `hist_gradient_boosting` | test | 2.8520 | 4.0451 | 0.1590 | 0.0% |

### Detalle por objetivo: Butyrate

| Modelo | Split | MAE | RMSE | R² | % Neg |
|---|---|---:|---:|---:|---:|
| `dummy_mean` | val | 7.5133 | 8.6075 | -0.1388 | 0.0% |
| `dummy_mean` | test | 5.8931 | 7.9686 | -0.0510 | 0.0% |
| `ridge` | val | 7.3003 | 8.3486 | -0.0713 | 0.0% |
| `ridge` | test | 5.4036 | 6.9686 | 0.1963 | 0.0% |
| `elasticnet` | val | 7.2375 | 8.8224 | -0.1964 | 0.0% |
| `elasticnet` | test | 5.9373 | 7.3163 | 0.1141 | 0.0% |
| `random_forest` | val | 7.3877 | 8.4718 | -0.1032 | 0.0% |
| `random_forest` | test | 5.6072 | 7.3328 | 0.1100 | 0.0% |
| `hist_gradient_boosting` | val | 6.8675 | 7.6790 | 0.0936 | 0.0% |
| `hist_gradient_boosting` | test | 5.0783 | 6.9098 | 0.2098 | 0.0% |
