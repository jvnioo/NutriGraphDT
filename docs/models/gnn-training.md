# Pipeline de entrenamiento GNN (actividad 44)

Piezas del pipeline de entrenamiento de las GNN en `nutrigraphdt.models.training`. Requiere el extra
`graph`. Se compone de A44-1 (#95, grafos y `DataLoader`), A44-2 (#96, escalado), A44-3 (#97,
bucle de entrenamiento), A44-4 (#98, configuración y semillas), A44-5 (#99, trazabilidad) y A44-6
(#100, script `train_gnn.py`).

## Preparación de grafos y DataLoaders (A44-1)

El §3 de [gnn-architecture.md](gnn-architecture.md) fija el orden canónico para que entrenamiento,
evaluación y reproducción reciban exactamente la misma estructura de datos:

1. **Compuerta de validación:** Si se entregan registros (`GraphRecords`), se ejecuta
   `prepare_graphs_for_model` (`nutrigraphdt.graph.validation.pipeline`). Solo los grafos sin
   errores bloqueantes avanzan. Si no se entregan registros (por ejemplo, grafos ya auditados y
   guardados en disco), debe indicarse explícitamente `validated=True`.
2. **Aristas inversas:** Se aplica `add_reverse_edges` (`nutrigraphdt.graph.builder`) sobre cada
   grafo entregable. EDG-01 prohíbe las aristas inversas en los registros, por lo que se añaden
   estrictamente después de validar sobre copias inmutables.
3. **Target por grafo:** Se aplica `add_graph_target` (`nutrigraphdt.models.gnn.target`) para
   agregar `data.y_graph` (`[1, 3]`) y `data.y_graph_mask` (`[1, 3]`).
4. **Asignación y agrupación de escenarios:** Cada grafo entregable se asigna a `train`, `val` o `test`
   mediante `split.subset_of(data.sample_id)`. Los escenarios `basal` e `intervened` de una misma
   muestra comparten `sample_id` (INS-05), por lo que quedan juntos en el mismo subconjunto. Si un
   grafo entregable no tiene `sample_id` o este no pertenece a la partición, se lanza un `ValueError`
   explícito.
5. **Filtrado de instancias sin target:** Las instancias sin ningún AGCC medido (`y_graph_mask`
   todo en `False`) no aportan señal supervisada y se excluyen de los `DataLoader` finales.
6. **Metadatos globales (`GraphMetadata`):** Se construye `GraphMetadata.from_graphs` sobre la unión
   de todos los grafos entregables de todos los subconjuntos, garantizando que el modelo conozca
   todos los tipos de arista (incluidas las inversas), sin fuga de datos ya que solo describe el
   esquema.
7. **Construcción de DataLoaders:** Se construyen los tres `DataLoader` con `batch_size`
   configurable: `train` barajado con un `torch.Generator` sembrado (reproducibilidad CPU), mientras
   que `val` y `test` no se barajan.

### Resumen de conteos (`SubsetSummary`)

La función devuelve un objeto `summary` con una entrada por subconjunto (`train`, `val`, `test`):

| Atributo | Tipo | Descripción |
|---|---|---|
| `received` | `int` | Grafos recibidos correspondientes a este subconjunto. |
| `deliverable` | `int` | Grafos entregables aprobados por `prepare_graphs_for_model`. |
| `with_any_scfa` | `int` | Grafos con al menos un AGCC (`y_graph_mask.any() == True`). |
| `with_all_scfa` | `int` | Grafos con los tres AGCC (`y_graph_mask.all() == True`). |

Los `DataLoader` contienen exactamente los grafos entregables con algún AGCC (`with_any_scfa`).
En la cohorte sintética, todas las instancias son válidas y tienen los tres AGCC, por lo que los
cuatro conteos coinciden con el número de grafos asignados al subconjunto.

### Ejemplo de uso

```python
from nutrigraphdt.data.split import get_split
from nutrigraphdt.graph.heterodata import load_graphs
from nutrigraphdt.models.training import prepare_training_graphs

# Grafos previamente validados al construirse y guardarse
graphs = load_graphs("artifacts/graphs/D1_holofood/graphs")
split = get_split(split_file="configs/splits/d1_holofood.json")

prepared = prepare_training_graphs(
    records=None,
    graphs=graphs,
    split=split,
    validated=True,
    batch_size=16,
    seed=42,
)

train_loader = prepared.train
val_loader = prepared.val
test_loader = prepared.test
metadata = prepared.metadata
summary = prepared.summary

print(f"Train recibidos: {summary['train'].received}, entregados: {summary['train'].deliverable}")
print(f"DataLoader train lotes: {len(train_loader)}")
```

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

## Bucle de entrenamiento y evaluación (A44-3)

`train_model(model, loaders, config, target_scaler)` entrena cualquier `SCFAGraphModel` con los
valores del §6 de [gnn-architecture.md](gnn-architecture.md) que trae `TrainingConfig`:

1. **Inicialización perezosa.** Si quedan parámetros perezosos (`(-1, -1)` en `hetero_sage` y
   `hetero_gat`), se inicializan con `initialize_lazy_parameters` **antes** de crear el
   optimizador. Esa pasada recorre todas las relaciones de `metadata`, no solo las de un lote, y
   no consume el generador del `DataLoader` de `train`. `build_model` (A41-8) ya la hace, así
   que con la fábrica este paso no hace nada.
2. **Optimización.** Adam con `lr` y `weight_decay`. La pérdida es `masked_mse_loss` en la
   escala estandarizada: el bucle transforma `y_graph` con `target_scaler.transform` en cada
   lote. Los `DataLoader` entregan el target en las unidades de la fuente y las features ya
   escaladas (A44-2).
3. **Evaluación por época.** Se predice `val` en modo `eval`, se invierte la escala con
   `target_scaler.inverse_transform` y se calcula `evaluate_predictions` sobre las muestras con
   los tres AGCC, igual que en los baselines.
4. **Detención temprana.** El criterio es el RMSE promedio sin ponderar de `val`
   (`SELECTION_METRIC = "rmse_average"`); con esta métrica el acetato pesa más por su escala. Una
   época mejora si baja estrictamente el mejor RMSE. El entrenamiento se detiene tras `patience`
   épocas seguidas sin mejora, o al llegar a `max_epochs`. Al terminar se restauran los pesos de
   la mejor época.
5. **Valores no finitos.** Si la pérdida o las predicciones de `train` o de `val` tienen NaN o
   infinitos, se lanza `NonFiniteError` con la época y el subconjunto.

`test` no participa: el bucle solo lee `loaders.train` y `loaders.val`. Hay un test que
verifica que alterar `test` produce exactamente el mismo modelo.

`train_model` no fija la semilla. Llame a `set_seed(config.seed)` antes de construir el modelo y
los `DataLoader`.

### Resultado

`TrainingResult` contiene el modelo con los pesos de la mejor época, `best_epoch`,
`best_val_rmse`, `stopped_early`, `duration_seconds` y `history`, con un `EpochRecord` por
época:

| Campo | Contenido |
|---|---|
| `epoch` | Número de época, desde 1. |
| `train_loss` | `masked_mse_loss` de `train`, escala estandarizada, promediada sobre las celdas con valor. |
| `val_loss` | Igual, sobre `val` (todas las celdas con valor). |
| `val_metrics` | Métricas de `val` en las unidades de la fuente: `mae_<agcc>`, `rmse_<agcc>`, `r2_<agcc>`, `negative_pct_<agcc>` y `<métrica>_average`. |
| `improved` | Si la época bajó el mejor RMSE promedio. |

`EpochRecord.to_dict()` da la fila plana para `history.csv` (A44-5); las métricas llevan el
prefijo `val_`.

### Predicción

`predict(model, loader, target_scaler)` devuelve `Predictions`, con `sample_ids`, `graph_ids` y
los tensores `measured`, `mask` y `predicted` (`[N, 3]`), todo en las unidades de la fuente.
`Predictions.evaluate(model_name, split)` calcula las métricas sobre las filas con los tres
AGCC, y `Predictions.to_records(subset)` da una fila por grafo para `predictions.csv` (A44-5).

### Sin escalado

`IdentityTargetScaler` cumple la misma interfaz que `TargetScaler` (`TargetTransform`), así que
el bucle funciona sin A44-2. Úselo solo para depurar: sin estandarizar, el acetato domina la
pérdida.

### Ejemplo

```python
from nutrigraphdt.models.gnn import build_model, load_model_config
from nutrigraphdt.models.training import (
    TargetScaler,
    load_training_config,
    predict,
    set_seed,
    train_model,
)

config = load_training_config("configs/training/default.json")
set_seed(config.seed)
# `loaders`: PreparedDataLoaders con features escaladas con train (A44-1 y A44-2).
model = build_model(load_model_config("configs/models/homo_sage.yaml"), loaders.metadata)
target_scaler = TargetScaler.fit(list(loaders.graphs["train"]))

result = train_model(model, loaders, config, target_scaler)
print(result.best_epoch, result.best_val_rmse, result.stopped_early)
test_report = predict(result.model, loaders.test, target_scaler).evaluate("homo_sage", "test")
```
