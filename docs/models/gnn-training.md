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
4. **Asignación y agrupación de escenarios:** Cada grafo se asigna a `train`, `val` o `test`
   mediante `split.subset_of(data.sample_id)`. Los escenarios `basal` e `intervened` de una misma
   muestra comparten `sample_id` (INS-05), por lo que quedan juntos en el mismo subconjunto. Si un
   grafo no tiene `sample_id` o este no pertenece a la partición, se lanza un `ValueError`
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
