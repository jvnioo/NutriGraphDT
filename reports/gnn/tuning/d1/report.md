# Búsqueda de hiperparámetros y variabilidad por semilla: d1 (A45-5)

- **Variante de la grilla:** `homo_sage`.
- **Semilla de la grilla:** 42.
- **Criterio:** menor RMSE promedio de `val`; empate, modelo más chico. `test` no interviene: `grid.csv` y `selection.json` solo tienen métricas de `val`.

## Grilla (RMSE promedio de val)

| hidden_channels | num_layers | RMSE val | |
| ---: | ---: | ---: | :--- |
| 32 | 1 | 9.6546 | |
| 32 | 2 | 9.6124 | |
| 32 | 3 | 9.6143 | |
| 64 | 1 | 9.5027 | |
| 64 | 2 | 9.5211 | |
| 64 | 3 | 9.3440 | |
| 128 | 1 | 9.4329 | |
| 128 | 2 | 9.4034 | |
| 128 | 3 | 9.3113 | **elegida** |

## Media ± desviación estándar por semilla (RMSE promedio)

| Variante | Configuración | hidden × capas | rmse val | rmse test | Semillas |
| :--- | :--- | :---: | :---: | :---: | ---: |
| homo_sage | inicial | 64 × 2 | 9.4864 ± 0.1000 | 8.7503 ± 0.0608 | 5 |
| hetero_sage | inicial | 64 × 2 | 9.5315 ± 0.1042 | 8.7600 ± 0.0245 | 5 |
| hetero_gat | inicial | 64 × 2 | 9.5336 ± 0.1039 | 8.7749 ± 0.0660 | 5 |
| homo_sage | elegida | 128 × 3 | 9.3587 ± 0.0650 | 8.7798 ± 0.0887 | 5 |

MAE y R² están en `summary.csv`; cada corrida, en `seeds.csv` y `run_records/`.
