# Barrido de λ en `D1_holofood` (A68-P1, #178)

Generado con `python scripts/sweep_constraint_lambda.py` en 371 s.

## Método (fijado antes de correr)

- **Configuración:** `configs/constraints/lambda_sweep_d1.json` (versión 1.1.0).
- **Grilla de λ:** [0.0, 0.1, 1.0, 10.0, 100.0]. Es una elección de Desarrollo, sin valor científico de referencia: cubre desde el brazo libre (λ = 0) hasta una penalización que domina la pérdida de datos estandarizada.
- **Pérdida:** `L_datos + λ·L_bio` con los términos ['d06.hydrogen.propionate_bound'].
- **Folds de selección:** semillas [0, 1] del plan `configs/splits/d1_holofood_cv.json` (k = 5), 150 entrenamientos (presupuesto: 150). En cada fold solo se usa el train: un val interno de 1/5 de los grupos para la detención temprana y la selección. **El test de los folds no se lee.**
- **Entrenamiento:** variantes ['homo_sage', 'hetero_sage', 'hetero_gat'] con su YAML de `configs/models/`; máx. 200 épocas, paciencia 20; semilla `42000 + semilla·100 + fold`.
- **Candidatas:** las λ > 0 de la grilla. λ = 0 es el brazo libre $M_0$ del protocolo: se entrena en los mismos folds como referencia, pero no se elige.
- **Criterio:** (1) factibilidad: se descartan las λ con VR > 0 de `d06.hydrogen.propionate_bound` en el val interno, en la mejor época de algún fold; (2) menor `val_data_loss` media (MSE estandarizado sin la penalización) entre las λ que entrenaron en todos los folds; (3) a igual media, la menor λ.

## Candidatas

| Variante | λ | Folds ok | `val_data_loss` (media ± std) | VR val interno (%) | Factible | Elegida |
|---|---:|---:|---:|---:|---|---|
| `homo_sage` | 0 | 10/10 | 0.8937 ± 0.3565 | 0.00 | sí |  |
| `homo_sage` | 0.1 | 10/10 | 0.8937 ± 0.3565 | 0.00 | sí | **sí** |
| `homo_sage` | 1 | 10/10 | 0.8937 ± 0.3565 | 0.00 | sí |  |
| `homo_sage` | 10 | 10/10 | 0.8937 ± 0.3565 | 0.00 | sí |  |
| `homo_sage` | 100 | 10/10 | 0.8937 ± 0.3565 | 0.00 | sí |  |
| `hetero_sage` | 0 | 10/10 | 0.8833 ± 0.3442 | 0.00 | sí |  |
| `hetero_sage` | 0.1 | 10/10 | 0.8833 ± 0.3442 | 0.00 | sí | **sí** |
| `hetero_sage` | 1 | 10/10 | 0.8833 ± 0.3442 | 0.00 | sí |  |
| `hetero_sage` | 10 | 10/10 | 0.8833 ± 0.3442 | 0.00 | sí |  |
| `hetero_sage` | 100 | 10/10 | 0.8833 ± 0.3442 | 0.00 | sí |  |
| `hetero_gat` | 0 | 10/10 | 0.8656 ± 0.3571 | 0.00 | sí |  |
| `hetero_gat` | 0.1 | 10/10 | 0.8656 ± 0.3571 | 0.00 | sí | **sí** |
| `hetero_gat` | 1 | 10/10 | 0.8656 ± 0.3571 | 0.00 | sí |  |
| `hetero_gat` | 10 | 10/10 | 0.8656 ± 0.3571 | 0.00 | sí |  |
| `hetero_gat` | 100 | 10/10 | 0.8656 ± 0.3571 | 0.00 | sí |  |

## Elección

- `homo_sage`: λ = 0.1 (menor val_data_loss media (0.8936891198158264) entre las λ > 0 factibles; empate exacto entre λ = [0.1, 1.0, 10.0, 100.0], se elige la menor).
- `hetero_sage`: λ = 0.1 (menor val_data_loss media (0.8833413600921631) entre las λ > 0 factibles; empate exacto entre λ = [0.1, 1.0, 10.0, 100.0], se elige la menor).
- `hetero_gat`: λ = 0.1 (menor val_data_loss media (0.8655555337667465) entre las λ > 0 factibles; empate exacto entre λ = [0.1, 1.0, 10.0, 100.0], se elige la menor).

## Advertencias y limitaciones

- La λ elegida aquí es la que usa la evaluación pareada con y sin restricciones (#185). Ampliar la grilla después de ver resultados de evaluación exige registrar una fase exploratoria nueva.
- Si todas las λ empatan exactamente, la penalización no cambió el entrenamiento: ninguna predicción del val interno violó la cota y su gradiente fue cero. D-06 §6 lo anticipa para D1 (p_p ≤ 0,12 en la literatura frente a la cota 2/3).
- Folds fallidos: 0 (`status = error` en `sweep.csv`).
- **Identidad de los taxones (#266).** Los taxones llevan su linaje por familia multiplicado por la abundancia, con el vocabulario ajustado en cada train interno.

## Archivos

- `sweep.csv`: una fila por variante, λ, semilla y fold, incluidas las fallidas.
- `selection.json`: λ elegida, razón y candidatas por variante.
- `run.json`: configuración (con SHA-256), plan, cohorte, Git, entorno y duración.
