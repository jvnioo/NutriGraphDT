# Evaluación de variantes GNN en D1 HoloFood (A45-4)

- **Dataset:** `D1_holofood`.
- **Partición:** `configs/splits/d1_holofood.json`, versión `2.0.0`, SHA-256 `b6dd7d157d347456213b0b5cafc7e05ceee194ba1b0927420d0d189272285750`; verificada en las tres corridas contra la configuración indicada.
- El reporte consolida corridas existentes; no entrena modelos. Los valores de `dummy_mean` proceden de `reports/baselines/d1/report.csv`.

## Métricas GNN

| model | split | metric | acetate | propionate | butyrate | average |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
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

## Comparación con `dummy_mean`

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

## Conteos por subconjunto

| Subconjunto | Con tres AGCC | Recibidos | Entregables | Con algún AGCC |
| :--- | ---: | ---: | ---: | ---: |
| train | 31 | 105 | 105 | 31 |
| val | 7 | 33 | 33 | 7 |
| test | 21 | 47 | 47 | 21 |

## Duración y trazabilidad de las corridas

La duración se reporta en segundos y corresponde al dispositivo indicado para cada corrida.

| Variante | Dispositivo | Duración (s) | Commit | Dirty |
| :--- | :--- | ---: | :--- | :--- |
| homo_sage | cpu | 52.14 | `037e44a097535a70c0b64aec11c83bd35bfb9ba0` | no |
| hetero_sage | cpu | 38.52 | `037e44a097535a70c0b64aec11c83bd35bfb9ba0` | no |
| hetero_gat | cpu | 52.64 | `037e44a097535a70c0b64aec11c83bd35bfb9ba0` | no |

## Advertencias

- D1 no incluye el tratamiento dietario en las entradas de la GNN; los baselines sí usan esa información, por lo que la comparación debe considerar esta diferencia.
- En D1 los taxones están aislados y las variantes no aprovechan diferencias estructurales de sus convoluciones; el dataset no permite medirlas.
- `val` contiene solo 7 animales con los tres AGCC, por lo que las métricas de validación tienen una muestra pequeña.

