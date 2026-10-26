# Reproducción de `20261015-044030_hetero_gat_s42` (A45-8)

Generado con `python scripts/reproduce_run.py <run.json>`. Ver `docs/models/gnn-training.md`.

**Se reproduce**: ninguna comparación difiere.

| | Original | Reproducida |
| :--- | :--- | :--- |
| `run_id` | `20261015-044030_hetero_gat_s42` | `20261016-040052_hetero_gat_s42` |
| Variante | `hetero_gat` | `hetero_gat` |
| Semilla | `42` | `42` |
| Commit | `51ed4e17c01c` | `f46f37f00fe1` |
| Dirty | no | sí |
| Python | `3.14.5` | `3.13.13` |
| PyTorch | `2.14.1+cpu` | `2.14.1+cu130` |
| PyG | `2.8.0.post1` | `2.8.1` |
| Sistema | `Windows` | `Linux` |
| Dispositivo | `cpu` | `cpu` |

| Comparación | Estado | Máx. diferencia | Tolerancia | Detalle |
| :--- | :--- | ---: | ---: | :--- |
| Configuración (variante, semilla, fuente, entrenamiento, modelo) | ok | — | — | idéntico |
| Datos (partición, subconjuntos, metadatos del grafo) | ok | — | — | idéntico |
| Escalado ajustado con train (medias y desviaciones) | ok | 0.0e+00 | 1.0e-06 | — |
| Épocas (mejor época, épocas corridas, detención) | ok | — | — | idéntico |
| Historia por época (history.csv) | no disponible | — | — | falta el archivo original |
| Métricas val y test (reports/gnn/synthetic/report.csv) | ok | 5.7e-07 | 1.0e-05 | 8 filas |
| Predicciones (predictions.csv) | no disponible | — | — | falta el archivo original |
| Recarga del checkpoint reproducido (load_run) | ok | 0.0e+00 | 1.0e-06 | 50 filas |
| Pesos del checkpoint | no disponible | — | — | falta el checkpoint.pt original |
| Recarga del checkpoint original (load_run) | no disponible | — | — | falta el checkpoint.pt original |

- Solo se dispuso de `reports/gnn/synthetic/run_hetero_gat.json`: la carpeta original (historia, predicciones y checkpoint) no está versionada. Las métricas se compararon con `reports/gnn/synthetic/report.csv`, que copia `val` y `test` de su `metrics.csv`.
