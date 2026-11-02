# Reproducción de `20261102-041750_hetero_sage_constrained_s0_f0` (A68-P4, #182)

Generado con `python scripts/reproduce_compositional_run.py runs/constraints/synthetic/20261102-041750_hetero_sage_constrained_s0_f0 --device cpu --output reports/constraints/reproducibility/cpu --runs-dir runs/reproduced/cpu`. Ver `docs/models/gnn-training.md`.

**No se reproduce**: Historial por época (pérdidas de datos, bio y total); Predicciones `(z_1, z_2, ln T)` del test; Métricas de D-03 del test (`metrics.csv`).

| | Original | Reproducida |
| :--- | :--- | :--- |
| `run_id` | `20261102-041750_hetero_sage_constrained_s0_f0` | `20261102-043234_hetero_sage_constrained_s0_f0` |
| Variante | `hetero_sage` | `hetero_sage` |
| Semilla | `0` | `0` |
| Commit | `c8e805992942` | `6186ed843985` |
| Dirty | no | no |
| Python | `3.14.6` | `3.14.6` |
| PyTorch | `2.13.0+rocm7.1` | `2.14.0+cpu` |
| PyG | `2.8.1` | `2.8.0.post1` |
| Sistema | `Linux` | `Linux` |
| Dispositivo | `cuda` | `cpu` |

| Comparación | Estado | Máx. diferencia | Tolerancia | Detalle |
| :--- | :--- | ---: | ---: | :--- |
| Plan de folds (SHA-256 canónico, #133) | ok | — | — | 15ecd1b749e3… |
| Animales de train, val interno y test | ok | — | — | — |
| Configuración: `variant` | ok | — | — | — |
| Configuración: `edges_arm` | ok | — | — | — |
| Configuración: `dataset_id` | ok | — | — | — |
| Configuración: `seed` | ok | — | — | — |
| Configuración: `fold` | ok | — | — | — |
| Configuración: `train_seed` | ok | — | — | — |
| Configuración: `training_config` | ok | — | — | — |
| Configuración: `model_config` | ok | — | — | — |
| Configuración: `target_names` | ok | — | — | — |
| Configuración: `constraint_lambda` | ok | — | — | — |
| Configuración: `constraint_terms` | ok | — | — | — |
| Configuración: `monitored_constraints` | ok | — | — | — |
| Escalado ajustado con train (medias y desviaciones) | ok | 0.0e+00 | 1.0e-06 | — |
| Épocas: `best_epoch` | ok | — | — | — |
| Épocas: `epochs_run` | ok | — | — | — |
| Épocas: `stopped_early` | ok | — | — | — |
| Historial por época (pérdidas de datos, bio y total) | difiere | 1.5e-01 | 1.0e-04 | 23 filas; mayor en 1 val_loss |
| Predicciones `(z_1, z_2, ln T)` del test | difiere | 9.5e-02 | 1.0e-04 | 12 filas; mayor en synthetic:sample:0003 z1 |
| Métricas de D-03 del test (`metrics.csv`) | difiere | 2.6e-01 | 1.0e-05 | 12 filas; mayor en hetero_sage/test/all/fraction_mae_pp butyrate |
| Violaciones: conteos por época, subconjunto y restricción | ok | — | — | — |
| Violaciones: magnitudes y tasas | ok | 0.0e+00 | 1.0e-04 | 376 filas |
| Recarga del checkpoint original | ok | 1.2e-07 | 1.0e-05 | — |

- Corrida original en `cuda` (AMD Radeon RX 9060 XT); reproducida en `cpu`. Entre dispositivos distintos la optimización puede seguir otro camino desde la primera época, y esas diferencias se informan sin ampliar tolerancias.
- PyTorch 2.13.0+rocm7.1 → 2.14.0+cpu.
