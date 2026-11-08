# Comparación de modelos con y sin restricciones

Tabla de métricas para D1 y la cohorte sintética, generada desde los CSV versionados.
Los valores se presentan como media ± desviación estándar entre folds (`_mean` y `_std`);
no se usa `_seed_std`. Las métricas predictivas son macro-promedios (`average`). `FR conjunta`
es la factibilidad conjunta en porcentaje; `VR` y `FR` son porcentajes. `VWM` es
el máximo de `worst_case_magnitude` (columna `max`) y `VMM` es `mean_magnitude`, ambos de
`violations_summary.csv`; VWM representa el peor caso de todos los folds. La tabla no recalcula
violaciones desde predicciones. Las restricciones estructurales se omiten: sus métricas valen 0
por construcción en estos modelos composicionales.

## Resultados principales

| Cohorte | Modelo | Brazo | Grupo | MAE fracciones (pp) | R² fracciones | MAE ln T | MAE reconstruido | VR | VWM (máx.) | FR conjunta | VMM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 HoloFood | day_only | reference | all | 4.0272 ± 0.6354 | 0.0361 ± 0.2980 | 0.2499 ± 0.0579 | 7.4289 ± 1.0561 | — | — | — | — |
| D1 HoloFood | dummy_mean | reference | all | 4.6323 ± 0.7512 | -0.2384 ± 0.3033 | 0.2509 ± 0.0731 | 7.5823 ± 1.4197 | — | — | — | — |
| D1 HoloFood | hetero_gat | free | all | 4.0698 ± 0.7011 | -0.0208 ± 0.3830 | 0.2685 ± 0.0695 | 7.7665 ± 1.3673 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_gat | constrained | all | 4.0698 ± 0.7011 | -0.0208 ± 0.3830 | 0.2685 ± 0.0695 | 7.7665 ± 1.3673 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | free | all | 4.1069 ± 0.7074 | -0.0221 ± 0.3494 | 0.2715 ± 0.0774 | 7.9284 ± 1.4649 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | constrained | all | 4.1069 ± 0.7074 | -0.0221 ± 0.3494 | 0.2715 ± 0.0774 | 7.9284 ± 1.4649 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | free | all | 4.1944 ± 0.7513 | -0.0766 ± 0.4131 | 0.2704 ± 0.0770 | 7.9156 ± 1.4557 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | constrained | all | 4.1944 ± 0.7513 | -0.0766 ± 0.4131 | 0.2704 ± 0.0770 | 7.9156 ± 1.4557 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| cohorte sintética | hetero_gat | free | all | 5.1779 ± 0.6536 | -0.2922 ± 0.3220 | 0.1211 ± 0.0207 | 6.9133 ± 0.7204 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| cohorte sintética | hetero_gat | constrained | all | 5.1779 ± 0.6536 | -0.2922 ± 0.3220 | 0.1211 ± 0.0207 | 6.9133 ± 0.7204 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| cohorte sintética | hetero_sage | free | all | 5.1510 ± 0.6658 | -0.2657 ± 0.2619 | 0.1207 ± 0.0194 | 6.8611 ± 0.7066 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| cohorte sintética | hetero_sage | constrained | all | 5.1510 ± 0.6658 | -0.2657 ± 0.2619 | 0.1207 ± 0.0194 | 6.8611 ± 0.7066 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| cohorte sintética | homo_sage | free | all | 5.1033 ± 0.6486 | -0.2343 ± 0.2833 | 0.1172 ± 0.0200 | 6.7264 ± 0.6776 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| cohorte sintética | homo_sage | constrained | all | 5.1033 ± 0.6486 | -0.2343 ± 0.2833 | 0.1172 ± 0.0200 | 6.7264 ± 0.6776 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |

## D1 por día de muestreo

Desglose de D1 para los días 7, 21 y 35, según el protocolo §6.1.

| Cohorte | Modelo | Brazo | Grupo | MAE fracciones (pp) | R² fracciones | MAE ln T | MAE reconstruido | VR | VWM (máx.) | FR conjunta | VMM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 HoloFood | day_only | reference | 7 | 4.2948 ± 1.5008 | -456.0677 ± 2199.0835 | 0.3570 ± 0.1425 | 7.6574 ± 1.9372 | — | — | — | — |
| D1 HoloFood | dummy_mean | reference | 7 | 4.5892 ± 0.9811 | -309.8376 ± 1476.3445 | 0.3123 ± 0.2272 | 7.2071 ± 3.2799 | — | — | — | — |
| D1 HoloFood | hetero_gat | free | 7 | 4.5811 ± 1.3506 | -453.2866 ± 2191.1240 | 0.3469 ± 0.1793 | 7.6463 ± 2.4917 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_gat | constrained | 7 | 4.5811 ± 1.3506 | -453.2866 ± 2191.1240 | 0.3469 ± 0.1793 | 7.6463 ± 2.4917 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | free | 7 | 4.5804 ± 1.2775 | -445.5911 ± 2152.7083 | 0.3447 ± 0.1970 | 7.6407 ± 2.9219 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | constrained | 7 | 4.5804 ± 1.2775 | -445.5911 ± 2152.7083 | 0.3447 ± 0.1970 | 7.6407 ± 2.9219 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | free | 7 | 4.6945 ± 1.3943 | -552.6302 ± 2668.4762 | 0.3483 ± 0.1909 | 7.7317 ± 2.7372 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | constrained | 7 | 4.6945 ± 1.3943 | -552.6302 ± 2668.4762 | 0.3483 ± 0.1909 | 7.7317 ± 2.7372 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | day_only | reference | 21 | 3.6578 ± 0.6782 | -3.6351 ± 9.0525 | 0.1593 ± 0.0838 | 5.6401 ± 2.3940 | — | — | — | — |
| D1 HoloFood | dummy_mean | reference | 21 | 3.8334 ± 1.3152 | -3.0601 ± 9.3223 | 0.1383 ± 0.0824 | 5.4261 ± 2.2676 | — | — | — | — |
| D1 HoloFood | hetero_gat | free | 21 | 3.1993 ± 1.1541 | -2.5062 ± 6.2418 | 0.1545 ± 0.0990 | 5.3889 ± 2.3916 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_gat | constrained | 21 | 3.1993 ± 1.1541 | -2.5062 ± 6.2418 | 0.1545 ± 0.0990 | 5.3889 ± 2.3916 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | free | 21 | 3.4305 ± 1.1531 | -2.6182 ± 6.1861 | 0.1634 ± 0.1060 | 5.6371 ± 2.5581 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | constrained | 21 | 3.4305 ± 1.1531 | -2.6182 ± 6.1861 | 0.1634 ± 0.1060 | 5.6371 ± 2.5581 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | free | 21 | 3.3790 ± 1.0959 | -2.5821 ± 6.0625 | 0.1554 ± 0.1029 | 5.4724 ± 2.5498 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | constrained | 21 | 3.3790 ± 1.0959 | -2.5821 ± 6.0625 | 0.1554 ± 0.1029 | 5.4724 ± 2.5498 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | day_only | reference | 35 | 4.0639 ± 0.8355 | -0.5441 ± 0.7745 | 0.2035 ± 0.0832 | 7.5834 ± 1.9855 | — | — | — | — |
| D1 HoloFood | dummy_mean | reference | 35 | 4.9241 ± 0.9925 | -1.3779 ± 0.9541 | 0.2359 ± 0.0772 | 8.1891 ± 1.9420 | — | — | — | — |
| D1 HoloFood | hetero_gat | free | 35 | 4.0295 ± 0.8478 | -0.7267 ± 1.0032 | 0.2448 ± 0.0926 | 8.2519 ± 2.2114 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_gat | constrained | 35 | 4.0295 ± 0.8478 | -0.7267 ± 1.0032 | 0.2448 ± 0.0926 | 8.2519 ± 2.2114 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | free | 35 | 4.0256 ± 0.8533 | -0.7157 ± 0.9939 | 0.2458 ± 0.0924 | 8.4486 ± 2.1062 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | hetero_sage | constrained | 35 | 4.0256 ± 0.8533 | -0.7157 ± 0.9939 | 0.2458 ± 0.0924 | 8.4486 ± 2.1062 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | free | 35 | 4.1431 ± 0.8679 | -0.7859 ± 0.9915 | 0.2493 ± 0.0885 | 8.5038 ± 2.1033 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |
| D1 HoloFood | homo_sage | constrained | 35 | 4.1431 ± 0.8679 | -0.7859 ± 0.9915 | 0.2493 ± 0.0885 | 8.5038 ± 2.1033 | 0.0000 ± 0.0000% | 0.0 | 100.0000 ± 0.0000% | 0.0000 ± 0.0000 |

Advertencia: el R² por día no es interpretable porque cada fold tiene pocos animales por día y
muy poca varianza en el objetivo. Esto produce valores extremos (por ejemplo, el día 7); se
conservan sin modificación, pero no deben interpretarse como capacidad predictiva por día.

## Referencias

Las referencias `dummy_mean` y `day_only` proceden de
`reports/baselines/d1_composition/metrics.csv`;
se incluyen solo para D1. Comparables con D1: `day_only`, `dummy_mean`. Hash canónico verificado: `ea329b6a9d91d0a240844765fb6884b360e56528633cbac2c9da62e809ecc8c5`. La cohorte sintética no tiene referencias baseline:
**no aplica**; no se han fabricado valores.

## Lectura

D-06 §6 preveía que el efecto solo podía observarse en la cohorte sintética o en predicciones
fuera de rango. Según los datos:

D1: los brazos son idénticos y VR = 0.
Cohorte sintética: los brazos son idénticos y VR = 0.

La restricción no se activó en ninguno de los dos conjuntos, así que esta comparación no la pone a prueba. En D1, «Factibilidad sin costo» significa que no costó nada porque no hizo nada.
Esta comparación no aporta evidencia de beneficio bioquímico. La cohorte marcada como `synthetic`
es sintética y se interpreta por separado de D1. Las métricas son descriptivas y no sustituyen
la inferencia pareada de A73-P3.
