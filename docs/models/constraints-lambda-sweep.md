# Barrido de λ y selección solo por validación interna (A68-P1, #178)

Este documento describe cómo se elige el peso λ de la pérdida compuesta
`L = L_datos + λ·L_bio` del brazo con restricciones antes de compararlo con el brazo libre
(#185), siguiendo el protocolo A55-P1 ([`constraints-evaluation-protocol.md`](constraints-evaluation-protocol.md)
§1.3). Los resultados están en `reports/constraints/lambda_sweep/<dataset>/`.

## 1. Qué se fija antes de correr

Cada conjunto tiene una configuración versionada en `configs/constraints/`
(`lambda_sweep_d1.json` y `lambda_sweep_synthetic.json`), que lee `LambdaSweepConfig`
(`nutrigraphdt.models.training.lambda_sweep`):

| Campo | Valor | Motivo |
|---|---|---|
| `grid` | 0; 0,1; 1; 10; 100 | Elección de Desarrollo, sin valor científico de referencia. Va del brazo libre a una penalización que domina la pérdida de datos estandarizada (de orden 1). |
| `constraint_terms` | `d06.hydrogen.propionate_bound` | La única restricción bioquímica de D-06 v1. Las estructurales valen 0 por construcción en la salida composicional. |
| `feasibility_constraint` | la misma | Paso 1 de §5 en la redacción de P-07: ¿cumple la tolerancia de D-06? |
| `selection_seeds` | 0 y 1 | Las mismas semillas de selección que #142. |
| `variants` | `homo_sage`, `hetero_sage`, `hetero_gat` | Con su YAML por omisión de `configs/models/`. |
| `max_epochs`, `patience` | 200, 20 | Los de `configs/training/default.json`. |
| `train_seed_base` | 42000 | La semilla de cada fold es `42000 + semilla·100 + fold`, como en #142. |
| `max_trainings` | 150 | Presupuesto: 3 variantes × 5 λ × 2 semillas × 5 folds. Se comprueba antes de entrenar. |

Ampliar la grilla después de ver resultados de evaluación exige registrar una fase exploratoria
nueva.

## 2. Sin el test de los folds

`run_lambda_sweep` toma de cada fold solo su train. Lo reparte en train interno y val interno
por grupo (`split_inner_validation`) y entrena con `train_compositional_model`, que monitorea la
restricción de factibilidad en el val interno (#179). El test del fold no se entrega:
`test_sweep_never_reads_the_test_of_a_fold` registra qué animales se leen en cada fold y
comprueba que son todos de su train. Cada configuración queda en `sweep.csv`, también las que
fallan.

## 3. Criterio de elección

Las candidatas del brazo restringido son las λ > 0. λ = 0 es el brazo libre $M_0$: se entrena
como referencia en los mismos folds, pero no se elige. Para cada variante:

1. **Factibilidad:** se descartan las λ con VR > 0 de la restricción de factibilidad en el val
   interno, en la mejor época de algún fold. Si ninguna es factible, se informa y se usan todas.
2. **Calidad predictiva:** gana la menor media de `val_data_loss` (MSE estandarizado del
   objetivo, sin la penalización) entre las λ que entrenaron en todos los folds.
3. **Desempate:** a igual media, la menor λ, que es la que menos interviene.

`python scripts/sweep_constraint_lambda.py --dataset <d1|synthetic> --from-sweep` vuelve a
elegir y a escribir el reporte desde `sweep.csv`, sin reentrenar.

## 4. Conjuntos

- **D1:** cohorte oficial de 56 animales y plan `configs/splits/d1_holofood_cv.json`, con los
  grafos de `scripts/build_graph.py` (que desde #176 codifican la dieta).
- **Cohorte sintética:** 60 animales de `build_synthetic_cohort(60, first_seed=1)` y plan
  `configs/splits/synthetic_cohort_cv.json` (`create_cv_folds.py --synthetic`). Los animales
  sintéticos no tienen corral: cada uno es su propio grupo y hay un solo estrato. **Es un dato
  sintético**: no describe animales reales.

`nutrigraphdt.models.training.cv_inputs` prepara los dos conjuntos con la misma interfaz y
verifica cada plan contra su cohorte (`verify_plan`).

## 5. Resultado esperado y cómo leerlo

Con salidas composicionales, `L_bio` es `mean(relu(h)²)` y vale 0, con gradiente 0, mientras
ninguna predicción supere p_p = 2/3. En ese caso todas las λ dan exactamente el mismo
entrenamiento: el barrido lo muestra como un empate exacto y se elige la menor λ > 0. D-06 §6 lo
anticipa para D1 (p_p ≤ 0,12 en la literatura independiente). Las fracciones de propionato de la
cohorte sintética llegan como máximo a 0,35. Que λ no cambie nada es un resultado que se informa,
no un error.

## 6. Resultados (01-11-2026)

| Conjunto | Entrenamientos | Fallidos | Folds con `val_data_loss` idéntica en las 5 λ | VR máx. (val interno) | `L_bio` máx. | λ elegida |
|---|---:|---:|---:|---:|---:|---|
| Cohorte sintética | 150 | 0 | 30 de 30 | 0 % | 0 | 0,1 en las tres variantes (empate exacto) |
| D1 | 150 | 0 | 30 de 30 | 0 % | 0 | 0,1 en las tres variantes (empate exacto) |

En los dos conjuntos, ninguna predicción del val interno violó la cota de D-06, así que la
penalización no cambió el entrenamiento. La regla elige entonces la menor λ > 0. Las corridas se
hicieron en GPU (AMD RX 9060 XT, ROCm 7.1). El detalle está en
`reports/constraints/lambda_sweep/<dataset>/`.
