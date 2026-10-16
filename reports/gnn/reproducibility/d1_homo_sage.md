# Reproducción de `20261015-182656_homo_sage_s42` (A45-8)

Generado con `python scripts/reproduce_run.py <run.json>`. Ver `docs/models/gnn-training.md`.

**Se reproduce**: ninguna comparación difiere.

| | Original | Reproducida |
| :--- | :--- | :--- |
| `run_id` | `20261015-182656_homo_sage_s42` | `20261016-040155_homo_sage_s42` |
| Variante | `homo_sage` | `homo_sage` |
| Semilla | `42` | `42` |
| Commit | `6595cc1b6a73` | `f46f37f00fe1` |
| Dirty | no | sí |
| Python | `3.13.14` | `3.13.13` |
| PyTorch | `2.14.1+cpu` | `2.14.1+cu130` |
| PyG | `2.8.0.post1` | `2.8.1` |
| Sistema | `Windows` | `Linux` |
| Dispositivo | `cpu` | `cpu` |

| Comparación | Estado | Máx. diferencia | Tolerancia | Detalle |
| :--- | :--- | ---: | ---: | :--- |
| Configuración (variante, semilla, fuente, entrenamiento, modelo) | ok | — | — | idéntico |
| Datos (partición, subconjuntos, metadatos del grafo) | ok | — | — | idéntico salvo `split.sha256`: el mismo archivo de partición con fines de línea LF y CRLF (Git en Windows) |
| Escalado ajustado con train (medias y desviaciones) | ok | 0.0e+00 | 1.0e-06 | — |
| Épocas (mejor época, épocas corridas, detención) | ok | — | — | idéntico |
| Historia por época (history.csv) | ok | 3.8e-06 | 1.0e-04 | 41 filas |
| Métricas (metrics.csv) | ok | 1.1e-06 | 1.0e-05 | 12 filas |
| Predicciones (predictions.csv) | ok | 3.8e-06 | 1.0e-04 | 59 filas |
| Recarga del checkpoint reproducido (load_run) | ok | 0.0e+00 | 1.0e-06 | 59 filas |
| Pesos del checkpoint | ok | 4.5e-06 | 1.0e-04 | 16 tensores |
| Recarga del checkpoint original (load_run) | ok | 3.8e-06 | 1.0e-04 | 59 filas |
