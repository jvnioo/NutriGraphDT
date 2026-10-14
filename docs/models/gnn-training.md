# Pipeline de entrenamiento GNN (actividad 44)

Piezas del entrenamiento de las GNN en `nutrigraphdt.models.training`. Requiere el extra
`graph`. Se completa con A44-1 (#95, grafos y `DataLoader`), A44-2 (#96, escalado), A44-3 (#97,
bucle), A44-5 (#99, trazabilidad) y A44-6 (#100, script `train_gnn.py`).

## Configuración y semillas (A44-4)

`TrainingConfig` declara los parámetros de una corrida. La configuración del modelo es aparte
(A41-8, #84). `configs/training/default.json` tiene los valores iniciales del §6 de
[gnn-architecture.md](gnn-architecture.md):

| Campo | Valor inicial | Restricción |
|---|---|---|
| `lr` | 0.001 | `> 0` |
| `weight_decay` | 0.0001 | `>= 0` |
| `batch_size` | 16 | entero `>= 1` |
| `max_epochs` | 200 | entero `>= 1` |
| `patience` | 20 | entero `>= 1`; épocas sin mejora del RMSE promedio de `val` |
| `seed` | 42 | entero en `[0, 2^32 - 1]` (límite de `numpy`) |
| `device` | `cpu` | `cpu`, `cuda` o `cuda:N` |
| `dataset_id` | `D1_holofood` | no vacío |
| `split_file` | `configs/splits/d1_holofood.json` | relativa a la raíz del repositorio o absoluta, como en `get_split` |

La validación es de Pydantic v2 (`extra="forbid"`, modo estricto): una clave desconocida, un
campo faltante, un tipo incorrecto (por ejemplo, `"16"` o `16.0` en `batch_size`) o un valor
fuera de rango se rechaza con `TrainingConfigError` (subclase de `ValueError`), con el archivo y
el campo en el mensaje. Todos los campos son obligatorios en el archivo salvo `device`.

```python
from nutrigraphdt.models.training import load_training_config, set_seed

config = load_training_config("configs/training/default.json")
set_seed(config.seed)  # antes de construir el modelo y los DataLoader
```

**Semillas.** `set_seed(seed)` fija `random`, `numpy` y `torch` y activa
`torch.use_deterministic_algorithms(True)`: una operación sin implementación determinista lanza
un error en lugar de dar resultados distintos entre corridas. El estado es global del proceso.
Con la misma semilla, la construcción del modelo da los mismos pesos iniciales y un `DataLoader`
con `shuffle=True` da el mismo orden de lotes (verificado en
`tests/unit/test_training_config.py`). En GPU, el determinismo de CUDA requiere además
`CUBLAS_WORKSPACE_CONFIG`; la línea base del proyecto es CPU y no se cubre aquí.

**Sobrescritura por línea de comandos (para A45-5).** `add_override_arguments(parser)` agrega un
argumento por campo (`--lr`, `--weight-decay`, `--batch-size`, `--max-epochs`, `--patience`,
`--seed`, `--device`, `--dataset-id`, `--split-file`). Un argumento omitido no sobrescribe.
`overrides_from_args(args)` devuelve solo los valores pasados y `apply_overrides(config, ...)`
devuelve una configuración nueva, validada igual que el archivo. Esa configuración efectiva,
junto con los valores sobrescritos, es la que debe registrar la corrida (A44-5).

```python
parser = argparse.ArgumentParser()
parser.add_argument("--config", default="configs/training/default.json")
add_override_arguments(parser)
args = parser.parse_args()
overrides = overrides_from_args(args)  # por ejemplo {"seed": 7}
config = apply_overrides(load_training_config(args.config), overrides)
```

**Formato.** JSON, igual que `configs/baselines/`, sin dependencias nuevas. La configuración de
modelos de A41-8 (#84) usa YAML porque su Issue lo pide; la alineación del formato queda para
A44-6 (#100), como anticipa el Issue de A44-4.
