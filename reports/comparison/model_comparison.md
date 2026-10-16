# Comparación GNN frente a baselines (A45-6)

Generado con `python scripts/compare_models.py` a partir de `reports/baselines/` y `reports/gnn/`; no entrena modelos. Métricas en las unidades de la fuente; `negative_pct` es el % de predicciones negativas. La interpretación y sus advertencias están en `docs/models/gnn-evaluation.md`.

## Criterio de salida de F4

Una GNN iguala o supera un baseline si su RMSE promedio de `test` es menor o igual.

| Dataset | ¿Se cumple? | Mejor GNN | Mejor baseline | GNN que igualan o superan a… |
| :--- | :---: | :--- | :--- | :--- |
| Cohorte sintética | sí | `hetero_sage` | `dummy_mean` | las 3 GNN a los 5 baselines |
| D1 HoloFood | sí | `hetero_sage` | `ridge` | las 3 GNN a los 5 baselines |

- Cohorte sintética: los AGCC no dependen de las entradas, así que el criterio solo verifica el procedimiento, no capacidad predictiva.

## Cohorte sintética

- `dataset_id`: `synthetic_baseline_cohort`; muestras con los tres AGCC por subconjunto: train 30, val 10, test 10.
- Partición: creada en memoria con la semilla de `reports/baselines/run.json`, SHA-256 `dab88b885512…`.
- Verificado con los `run.json`: `hetero_gat`, `hetero_sage`, `homo_sage` (commit `51ed4e17c01c17a8ce65ee1a26c9b776626ab24c`).

### Resumen (promedio de los tres AGCC)

| Familia | Modelo | RMSE val | RMSE test | MAE val | MAE test | R² val | R² test |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | `dummy_mean` | 8.3610 | 7.2502 | 7.5050 | 6.2485 | -0.0501 | -0.1804 |
| baseline | `ridge` | 8.3715 | 7.2610 | 7.5049 | 6.2431 | -0.0515 | -0.1842 |
| baseline | `elasticnet` | 8.3610 | 7.2502 | 7.5050 | 6.2485 | -0.0501 | -0.1804 |
| baseline | `random_forest` | 8.7605 | 7.3331 | 7.8706 | 6.3666 | -0.1308 | -0.2026 |
| baseline | `hist_gradient_boosting` | 10.3729 | 8.6579 | 9.5900 | 7.6145 | -0.6167 | -0.8970 |
| gnn | `homo_sage` | 8.2671 | 7.1414 | 7.4719 | 6.2535 | -0.0239 | -0.1509 |
| gnn | `hetero_sage` | 8.2730 | 7.0606 | 7.4505 | 6.1496 | -0.0252 | -0.1734 |
| gnn | `hetero_gat` | 8.2047 | 7.1665 | 7.2499 | 6.2345 | -0.0058 | -0.1445 |

### Detalle por AGCC

| model | split | metric | acetate | propionate | butyrate | average |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| dummy_mean | val | mae | 10.9942 | 6.3741 | 5.1467 | 7.5050 |
| dummy_mean | val | rmse | 12.3330 | 6.9640 | 5.7860 | 8.3610 |
| dummy_mean | val | r2 | -0.0000 | -0.0491 | -0.1012 | -0.0501 |
| dummy_mean | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| dummy_mean | test | mae | 11.8474 | 3.5237 | 3.3743 | 6.2485 |
| dummy_mean | test | rmse | 13.6319 | 4.0276 | 4.0912 | 7.2502 |
| dummy_mean | test | r2 | -0.4160 | -0.0001 | -0.1250 | -0.1804 |
| dummy_mean | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ridge | val | mae | 11.0000 | 6.3580 | 5.1567 | 7.5049 |
| ridge | val | rmse | 12.3683 | 6.9639 | 5.7824 | 8.3715 |
| ridge | val | r2 | -0.0057 | -0.0491 | -0.0998 | -0.0515 |
| ridge | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ridge | test | mae | 11.8278 | 3.5539 | 3.3476 | 6.2431 |
| ridge | test | rmse | 13.6472 | 4.0510 | 4.0849 | 7.2610 |
| ridge | test | r2 | -0.4192 | -0.0117 | -0.1215 | -0.1842 |
| ridge | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| elasticnet | val | mae | 10.9942 | 6.3741 | 5.1467 | 7.5050 |
| elasticnet | val | rmse | 12.3330 | 6.9640 | 5.7860 | 8.3610 |
| elasticnet | val | r2 | -0.0000 | -0.0491 | -0.1012 | -0.0501 |
| elasticnet | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| elasticnet | test | mae | 11.8474 | 3.5237 | 3.3743 | 6.2485 |
| elasticnet | test | rmse | 13.6319 | 4.0276 | 4.0912 | 7.2502 |
| elasticnet | test | r2 | -0.4160 | -0.0001 | -0.1250 | -0.1804 |
| elasticnet | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| random_forest | val | mae | 11.8406 | 6.5619 | 5.2091 | 7.8706 |
| random_forest | val | rmse | 13.2779 | 7.1448 | 5.8589 | 8.7605 |
| random_forest | val | r2 | -0.1591 | -0.1043 | -0.1291 | -0.1308 |
| random_forest | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| random_forest | test | mae | 12.2042 | 3.5403 | 3.3553 | 6.3666 |
| random_forest | test | rmse | 13.8571 | 3.9323 | 4.2097 | 7.3331 |
| random_forest | test | r2 | -0.4632 | 0.0467 | -0.1911 | -0.2026 |
| random_forest | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hist_gradient_boosting | val | mae | 13.6590 | 8.8713 | 6.2396 | 9.5900 |
| hist_gradient_boosting | val | rmse | 15.1567 | 9.1084 | 6.8536 | 10.3729 |
| hist_gradient_boosting | val | r2 | -0.5103 | -0.7947 | -0.5451 | -0.6167 |
| hist_gradient_boosting | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hist_gradient_boosting | test | mae | 13.4268 | 4.6662 | 4.7504 | 7.6145 |
| hist_gradient_boosting | test | rmse | 14.8185 | 5.4650 | 5.6903 | 8.6579 |
| hist_gradient_boosting | test | r2 | -0.6733 | -0.8413 | -1.1763 | -0.8970 |
| hist_gradient_boosting | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| homo_sage | val | mae | 10.9878 | 6.3700 | 5.0579 | 7.4719 |
| homo_sage | val | rmse | 12.2130 | 6.9450 | 5.6433 | 8.2671 |
| homo_sage | val | r2 | 0.0194 | -0.0434 | -0.0475 | -0.0239 |
| homo_sage | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| homo_sage | test | mae | 11.7855 | 3.6713 | 3.3039 | 6.2535 |
| homo_sage | test | rmse | 13.3598 | 4.1056 | 3.9587 | 7.1414 |
| homo_sage | test | r2 | -0.3601 | -0.0392 | -0.0533 | -0.1509 |
| homo_sage | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_sage | val | mae | 11.0518 | 6.1899 | 5.1098 | 7.4505 |
| hetero_sage | val | rmse | 12.2566 | 6.8566 | 5.7058 | 8.2730 |
| hetero_sage | val | r2 | 0.0123 | -0.0170 | -0.0709 | -0.0252 |
| hetero_sage | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_sage | test | mae | 11.2993 | 3.8854 | 3.2640 | 6.1496 |
| hetero_sage | test | rmse | 12.7641 | 4.4257 | 3.9919 | 7.0606 |
| hetero_sage | test | r2 | -0.2415 | -0.2076 | -0.0711 | -0.1734 |
| hetero_sage | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_gat | val | mae | 10.5742 | 6.2924 | 4.8833 | 7.2499 |
| hetero_gat | val | rmse | 12.1288 | 6.9919 | 5.4934 | 8.2047 |
| hetero_gat | val | r2 | 0.0328 | -0.0575 | 0.0074 | -0.0058 |
| hetero_gat | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_gat | test | mae | 11.8402 | 3.6051 | 3.2583 | 6.2345 |
| hetero_gat | test | rmse | 13.5488 | 4.0244 | 3.9264 | 7.1665 |
| hetero_gat | test | r2 | -0.3988 | 0.0015 | -0.0362 | -0.1445 |
| hetero_gat | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## D1 HoloFood

- `dataset_id`: `D1_holofood`; muestras con los tres AGCC por subconjunto: train 31, val 7, test 21.
- Partición: `configs/splits/d1_holofood.json`, SHA-256 `b6dd7d157d34…`.
- Verificado con los `run.json`: `hetero_gat`, `hetero_sage`, `homo_sage` (commit `037e44a097535a70c0b64aec11c83bd35bfb9ba0`).

### Resumen (promedio de los tres AGCC)

| Familia | Modelo | RMSE val | RMSE test | MAE val | MAE test | R² val | R² test |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | `dummy_mean` | 10.9311 | 9.7534 | 8.9840 | 7.1686 | -0.5612 | -0.0361 |
| baseline | `ridge` | 10.5696 | 9.0134 | 8.6994 | 6.8209 | -0.0747 | 0.1793 |
| baseline | `elasticnet` | 11.7079 | 10.9969 | 9.6162 | 7.7642 | -0.3704 | -0.2342 |
| baseline | `random_forest` | 11.8594 | 9.5595 | 9.8161 | 7.2836 | -0.5706 | 0.0685 |
| baseline | `hist_gradient_boosting` | 13.4953 | 10.0078 | 11.8852 | 7.7156 | -1.2834 | 0.0159 |
| gnn | `homo_sage` | 9.5211 | 8.7961 | 7.5567 | 6.6197 | 0.0176 | 0.2166 |
| gnn | `hetero_sage` | 9.6100 | 8.7518 | 7.6642 | 6.6115 | -0.0192 | 0.2235 |
| gnn | `hetero_gat` | 9.6096 | 8.8329 | 7.7011 | 6.6214 | -0.0304 | 0.2070 |

### Detalle por AGCC

| model | split | metric | acetate | propionate | butyrate | average |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| dummy_mean | val | mae | 16.1485 | 3.2902 | 7.5133 | 8.9840 |
| dummy_mean | val | rmse | 20.3398 | 3.8461 | 8.6075 | 10.9311 |
| dummy_mean | val | r2 | -0.0271 | -1.5178 | -0.1388 | -0.5612 |
| dummy_mean | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| dummy_mean | test | mae | 12.0030 | 3.6098 | 5.8931 | 7.1686 |
| dummy_mean | test | rmse | 16.8148 | 4.4768 | 7.9686 | 9.7534 |
| dummy_mean | test | r2 | -0.0272 | -0.0301 | -0.0510 | -0.0361 |
| dummy_mean | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ridge | val | mae | 16.5913 | 2.2066 | 7.3003 | 8.6994 |
| ridge | val | rmse | 20.8487 | 2.5115 | 8.3486 | 10.5696 |
| ridge | val | r2 | -0.0792 | -0.0736 | -0.0713 | -0.0747 |
| ridge | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ridge | test | mae | 12.2032 | 2.8559 | 5.4036 | 6.8209 |
| ridge | test | rmse | 16.4455 | 3.6260 | 6.9686 | 9.0134 |
| ridge | test | r2 | 0.0175 | 0.3243 | 0.1963 | 0.1793 |
| ridge | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| elasticnet | val | mae | 18.7278 | 2.8834 | 7.2375 | 9.6162 |
| elasticnet | val | rmse | 23.2630 | 3.0384 | 8.8224 | 11.7079 |
| elasticnet | val | r2 | -0.3436 | -0.5713 | -0.1964 | -0.3704 |
| elasticnet | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| elasticnet | test | mae | 14.0615 | 3.2936 | 5.9373 | 7.7642 |
| elasticnet | test | rmse | 20.7324 | 4.9419 | 7.3163 | 10.9969 |
| elasticnet | test | r2 | -0.5616 | -0.2552 | 0.1141 | -0.2342 |
| elasticnet | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| random_forest | val | mae | 18.7026 | 3.3582 | 7.3877 | 9.8161 |
| random_forest | val | rmse | 23.4788 | 3.6277 | 8.4718 | 11.8594 |
| random_forest | val | r2 | -0.3686 | -1.2399 | -0.1032 | -0.5706 |
| random_forest | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| random_forest | test | mae | 13.0776 | 3.1661 | 5.6072 | 7.2836 |
| random_forest | test | rmse | 17.3840 | 3.9616 | 7.3328 | 9.5595 |
| random_forest | test | r2 | -0.0979 | 0.1934 | 0.1100 | 0.0685 |
| random_forest | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hist_gradient_boosting | val | mae | 24.3101 | 4.4781 | 6.8675 | 11.8852 |
| hist_gradient_boosting | val | rmse | 27.9572 | 4.8497 | 7.6790 | 13.4953 |
| hist_gradient_boosting | val | r2 | -0.9405 | -3.0032 | 0.0936 | -1.2834 |
| hist_gradient_boosting | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hist_gradient_boosting | test | mae | 15.2165 | 2.8520 | 5.0783 | 7.7156 |
| hist_gradient_boosting | test | rmse | 19.0686 | 4.0451 | 6.9098 | 10.0078 |
| hist_gradient_boosting | test | r2 | -0.3210 | 0.1590 | 0.2098 | 0.0159 |
| hist_gradient_boosting | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| homo_sage | val | mae | 14.2110 | 2.1093 | 6.3497 | 7.5567 |
| homo_sage | val | rmse | 18.6041 | 2.7525 | 7.2067 | 9.5211 |
| homo_sage | val | r2 | 0.1407 | -0.2896 | 0.2017 | 0.0176 |
| homo_sage | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| homo_sage | test | mae | 11.9695 | 2.9124 | 4.9771 | 6.6197 |
| homo_sage | test | rmse | 16.0984 | 3.6120 | 6.6779 | 8.7961 |
| homo_sage | test | r2 | 0.0585 | 0.3295 | 0.2619 | 0.2166 |
| homo_sage | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_sage | val | mae | 14.3904 | 2.2937 | 6.3086 | 7.6642 |
| hetero_sage | val | rmse | 18.8383 | 2.8632 | 7.1285 | 9.6100 |
| hetero_sage | val | r2 | 0.1189 | -0.3953 | 0.2189 | -0.0192 |
| hetero_sage | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_sage | test | mae | 11.9877 | 2.9707 | 4.8762 | 6.6115 |
| hetero_sage | test | rmse | 16.0306 | 3.6219 | 6.6028 | 8.7518 |
| hetero_sage | test | r2 | 0.0664 | 0.3258 | 0.2784 | 0.2235 |
| hetero_sage | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_gat | val | mae | 14.2870 | 2.3422 | 6.4741 | 7.7011 |
| hetero_gat | val | rmse | 18.6703 | 2.8794 | 7.2791 | 9.6096 |
| hetero_gat | val | r2 | 0.1346 | -0.4112 | 0.1856 | -0.0304 |
| hetero_gat | val | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hetero_gat | test | mae | 11.9501 | 2.9722 | 4.9420 | 6.6214 |
| hetero_gat | test | rmse | 16.1440 | 3.6716 | 6.6830 | 8.8329 |
| hetero_gat | test | r2 | 0.0532 | 0.3072 | 0.2608 | 0.2070 |
| hetero_gat | test | negative_pct | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
