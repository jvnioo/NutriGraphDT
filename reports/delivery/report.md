# Validación del sistema completo con la configuración de entrega (A117, #347)

> **Datos sintéticos.** El pipeline corre sobre la cohorte sintética. Los targets no dependen de la dieta ni del aditivo (DS-01): este reporte muestra que el flujo funciona y se reproduce, no efectos biológicos. D1 no es referencia del sistema completo (#296).

- **Commit:** `81bf6dff4b4ccf74690b1de34e0e247ff2125898`
- **Fecha:** 2026-11-25T21:57:36-0300
- **Comando:** `python scripts/run_delivery.py`
- **Configuración:** `configs/delivery.json` (SHA-256 `30c6ff2f65936093…`)
- **Entorno:** python 3.13.17, platform Windows-11-10.0.26300-SP0, torch 2.15.0+cpu, torch_geometric 2.8.1, sklearn 1.9.1, pydantic 2.14.4, streamlit 1.67.0

## 1. Pasos y tiempos

| Paso | Segundos |
|---|---:|
| datos | 0.01 |
| validación | 0.02 |
| base | 3.16 |
| grafos | 0.05 |
| entrenamiento synthetic | 0.97 |
| simulación synthetic | 0.36 |
| entrenamiento synthetic_constrained | 0.99 |
| simulación synthetic_constrained | 0.35 |
| explicación | 0.15 |

## 2. Datos y grafo

- Cohorte `synthetic_cohort`: 20 animales, 640 nodos y 1602 aristas.
- `validate_graph`: WARNING: 3.
- 20 grafos `HeteroData`; entre todos tienen 8 tipos de nodo y 11 relaciones (sin contar las inversas).

## 3. Corridas, reproducibilidad y escenarios

| Corrida | λ | Restricciones | Animales (train/val/test) | Reproduce la congelada | Escenarios con el estado esperado |
|---|---:|---|---|---|---|
| `synthetic` | 0 | — | 12/4/4 | sí (máx. 0.0e+00) | 6 de 6 |
| `synthetic_constrained` | 0.1 | d06.hydrogen.propionate_bound | 12/4/4 | sí (máx. 0.0e+00) | 6 de 6 |

Explicación: `crude-protein-270`, salida `log_total`, con `synthetic`; cumple el contrato y asigna importancia a 32 nodos (0.13 s).

## 4. Métricas frente a las corridas sintéticas previas (A117-P2)

| Fuente | Animales | Diseño | MAE fracciones (pp) | R² fracciones | MAE ln T | MAE reconstruido |
|---|---:|---|---:|---:|---:|---:|
| Entrega `synthetic` | 20 | 1 fold, test de 4 | 6.2093 | -0.1433 | 0.1101 | 6.5285 |
| Entrega `synthetic_constrained` | 20 | 1 fold, test de 4 | 6.2093 | -0.1433 | 0.1101 | 6.5285 |
| A68-P2 (#185), brazo free | 60 | CV 10 semillas × 5 folds, hasta 200 épocas | 5.1033 | -0.2343 | 0.1172 | 6.7264 |
| A68-P2 (#185), brazo constrained | 60 | CV 10 semillas × 5 folds, hasta 200 épocas | 5.1033 | -0.2343 | 0.1172 | 6.7264 |
| A45-3 (#103) | 50 | partición única 30/10/10, objetivo de concentraciones (antes del contrato v2) | — | — | — | 6.2535 |

Tasa de violación de D-06 (A73, #272) en el test de cada corrida de entrega, calculada con `evaluate_constraints` sobre su `predictions.csv`: `synthetic`: d06.hydrogen.propionate_bound 0.0 %; `synthetic_constrained`: d06.hydrogen.propionate_bound 0.0 %. En A68-P2 es 0 % (`reports/constraints/comparison/report.md`).

## 5. Desviaciones

| Desviación | Explicación |
|---|---|
| fraction_mae_pp: entrega 6.2093 frente a A68-P2 5.1033 | La corrida de entrega es la de demostración de la plataforma: 12 animales de train, 4 de test, un fold y hasta 30 épocas; A68-P2 promedia 50 folds con 60 animales y hasta 200 épocas. Con 4 animales de test la métrica tiene mucha más varianza. En este generador los AGCC no dependen de las entradas (DS-01): ninguna de las dos cifras mide capacidad predictiva. |
| log_total_mae: entrega 0.1101 frente a A68-P2 0.1172 | La corrida de entrega es la de demostración de la plataforma: 12 animales de train, 4 de test, un fold y hasta 30 épocas; A68-P2 promedia 50 folds con 60 animales y hasta 200 épocas. Con 4 animales de test la métrica tiene mucha más varianza. En este generador los AGCC no dependen de las entradas (DS-01): ninguna de las dos cifras mide capacidad predictiva. |
| reconstructed_mae: entrega 6.5285 frente a A68-P2 6.7264 | La corrida de entrega es la de demostración de la plataforma: 12 animales de train, 4 de test, un fold y hasta 30 épocas; A68-P2 promedia 50 folds con 60 animales y hasta 200 épocas. Con 4 animales de test la métrica tiene mucha más varianza. En este generador los AGCC no dependen de las entradas (DS-01): ninguna de las dos cifras mide capacidad predictiva. |
| Con y sin restricciones dan las mismas métricas | Igual que en A68-P2 y en el barrido de λ: ninguna predicción viola la cota de D-06 (p_p ≤ 2/3), así que la penalización y su gradiente son cero y el entrenamiento es idéntico. |
| A45-3 usa otra métrica de concentraciones | A45-3 entrenó contra concentraciones directas antes del contrato composicional v2; su MAE no es comparable con `reconstructed_mae` de la entrega. Se cita como contexto, no como término de comparación. |

Regenerar: `python scripts/run_delivery.py`.
