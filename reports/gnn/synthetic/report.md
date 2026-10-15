# Evaluación de variantes GNN en la cohorte sintética (A45-3)

- **Cohorte:** `synthetic_baseline_cohort` (50 instancias; semillas 1 a 50).
- **Partición:** semilla `42` (30 train, 10 val, 10 test), verificada contra `reports/baselines/run.json`.
- Las corridas y métricas se leen de los directorios de entrenamiento indicados; este script no entrena modelos.

> [!WARNING]
> Esta evaluación es exclusivamente sintética y no mide desempeño predictivo real. En el generador actual, los AGCC no dependen de las entradas; el resultado verifica el flujo de entrenamiento y evaluación, no la capacidad predictiva.
>
> Las diferencias pequeñas frente a `dummy_mean` no son interpretables en este generador y no permiten afirmar que una variante supere al baseline.

## Métricas GNN

| model | split | metric | acetate | propionate | butyrate | average |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
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

## Comparación con `dummy_mean`

Los valores de `dummy_mean` se leen de `reports/baselines/report.csv`; las diferencias no se interpretan como evidencia de superioridad predictiva.

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

