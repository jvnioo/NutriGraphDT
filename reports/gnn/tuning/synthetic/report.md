# Búsqueda de hiperparámetros y variabilidad por semilla: synthetic (A45-5)

- **Variante de la grilla:** `hetero_gat`.
- **Semilla de la grilla:** 42.
- **Criterio:** menor RMSE promedio de `val`; empate, modelo más chico. `test` no interviene: `grid.csv` y `selection.json` solo tienen métricas de `val`.

## Grilla (RMSE promedio de val)

| hidden_channels | num_layers | RMSE val | |
| ---: | ---: | ---: | :--- |
| 32 | 1 | 8.2158 | |
| 32 | 2 | 8.1991 | |
| 32 | 3 | 8.3076 | |
| 64 | 1 | 8.2820 | |
| 64 | 2 | 8.2047 | |
| 64 | 3 | 8.6122 | |
| 128 | 1 | 8.0882 | **elegida** |
| 128 | 2 | 8.2099 | |
| 128 | 3 | 8.2145 | |

## Media ± desviación estándar por semilla (RMSE promedio)

| Variante | Configuración | hidden × capas | rmse val | rmse test | Semillas |
| :--- | :--- | :---: | :---: | :---: | ---: |
| homo_sage | inicial | 64 × 2 | 8.2232 ± 0.1164 | 7.0587 ± 0.1180 | 5 |
| hetero_sage | inicial | 64 × 2 | 8.2282 ± 0.0618 | 7.0281 ± 0.1815 | 5 |
| hetero_gat | inicial | 64 × 2 | 8.2852 ± 0.1266 | 7.0540 ± 0.2066 | 5 |
| hetero_gat | elegida | 128 × 1 | 8.1907 ± 0.0886 | 7.0173 ± 0.1070 | 5 |

MAE y R² están en `summary.csv`; cada corrida, en `seeds.csv` y `runs/`.
