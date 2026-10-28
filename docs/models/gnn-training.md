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
   Después, `align_graph_types` (#119) agrega a cada grafo los tipos de nodo y de arista de esa
   unión que le faltan, vacíos. PyG exige las mismas claves en todos los grafos de un lote: sin
   esta alineación, un lote reasigna aristas a otro grafo y la predicción de un grafo depende de
   con qué otros grafos comparte lote.
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
## Trazabilidad de corridas (A44-5)

`save_run(record, runs_dir="runs")` (`nutrigraphdt.models.training.tracking`) deja cada
entrenamiento en `runs/<run_id>/`, con lo necesario para saber exactamente qué se entrenó y para
volver a predecir sin reentrenar. `runs/` está en `.gitignore`. Lo que vaya al informe se copia
a `reports/gnn/` en la act. 45. El registro es local y en archivos, porque
[cost-policy.md](../process/cost-policy.md) excluye el seguimiento de experimentos alojado de
pago.

`run_id` = `<AAAAMMDD-HHMMSS>_<variante>_s<semilla>`, con la hora en UTC (por ejemplo,
`20261014-153005_homo_sage_s42`). Si el directorio ya existe, `save_run` lanza
`FileExistsError` y no sobrescribe.

| Archivo | Contenido |
|---|---|
| `run.json` | Ver la tabla siguiente. |
| `history.csv` | Una fila por época (`EpochRecord.to_dict()` de A44-3): `epoch`, `train_loss`, `val_loss`, `val_<métrica>_<agcc>`, `improved`. |
| `metrics.csv` | `EvaluationReport.to_csv()`, byte a byte. |
| `predictions.csv` | Una fila por grafo (`Predictions.to_records(subset)` de A44-3): `sample_id`, `graph_id`, `subset`, `measured_<agcc>` (vacío si no se midió) y `predicted_<agcc>`. |
| `checkpoint.pt` | `state_dict` de la mejor época, en CPU (`torch.save`). |

Los números de los CSV se escriben con `repr`, la representación más corta que vuelve
exactamente al mismo `float`.

**`run.json`**

| Clave | Contenido |
|---|---|
| `format_version`, `run_id`, `created_at` | Formato del registro (`1.0.0`), identificador y hora UTC. |
| `variant`, `seed`, `dataset_id` | Variante, semilla y dataset de la corrida. |
| `source` | De dónde salieron los grafos, tal como lo entrega quien entrena (por ejemplo, los parámetros de la cohorte sintética). |
| `training_config`, `model_config` | Configuración **efectiva** (después de sobrescribir por línea de comandos), tal como la validan `TrainingConfig` y `GNNModelConfig`. |
| `metadata` | `GraphMetadata`: columnas por tipo de nodo y tripletas de arista, para reconstruir el modelo. |
| `split` | Archivo (relativo a la raíz del repositorio, o solo el nombre si está fuera; `null` si la partición se creó en memoria), `dataset_id`, `version`, `seed`, conteos y SHA-256. El hash es el del JSON canónico de la partición (`split_content_sha256`: `json.dumps(..., sort_keys=True, ensure_ascii=False)` en UTF-8): con archivo, el de su contenido; sin archivo, el de `DatasetSplit.to_dict()`. No depende del fin de línea (#133). Las corridas anteriores a #133 registran el hash de los bytes del archivo. |
| `subsets` | `SubsetSummary` de A44-1 por subconjunto. |
| `scaling` | `scalers_to_dict` de A44-2: estadísticas de `train` de features y target. |
| `best_epoch`, `epochs_run`, `stopped_early`, `duration_seconds` | Resultado del bucle de A44-3. |
| `git` | Commit de `HEAD` y `dirty` (cambios sin confirmar en archivos versionados); `null` sin Git. |
| `environment` | Versiones de Python, torch y torch-geometric, y sistema operativo. |

El registro no guarda datos crudos (`raw_attributes`, tablas de la fuente) ni rutas absolutas
del equipo de quien entrena.

### Recargar una corrida

`load_run(run_dir)` lee `run.json` y construye el modelo con `build_model` desde
`model_config` y `metadata`. Después carga `checkpoint.pt` con `weights_only=True`, igual que
los grafos (`graph/heterodata.py`), y reconstruye los escaladores con `scalers_from_dict`.
Devuelve `LoadedRun`, con el modelo en modo `eval`, `feature_scaler`, `target_scaler`, las dos
configuraciones e `info` (el contenido de `run.json`). Un test verifica que, con los mismos
grafos, las predicciones del modelo recargado coinciden exactamente con `predictions.csv`.

```python
from nutrigraphdt.models.training import load_run

run = load_run("runs/20261014-153005_homo_sage_s42")
graphs = run.feature_scaler.transform(raw_graphs)  # grafos con inversas y target (A44-1)
# predict(run.model, DataLoader(graphs, batch_size=16), run.target_scaler) de A44-3
```

## Entrenar una variante: `scripts/train_gnn.py` (A44-6)

Un solo comando entrena una variante de principio a fin con la configuración versionada y deja
la corrida registrada:

```bash
pip install -e ".[dev,graph]"
python scripts/train_gnn.py --model homo_sage --dataset synthetic
python scripts/train_gnn.py --model hetero_gat --dataset d1
```

| Argumento | Valor por defecto | Uso |
|---|---|---|
| `--model` | (obligatorio) | `homo_sage`, `hetero_sage` o `hetero_gat`. |
| `--dataset` | (obligatorio) | `synthetic` o `d1`. |
| `--config` | `configs/training/default.json` | Configuración de entrenamiento (A44-4). |
| `--model-config` | `configs/models/<model>.yaml` | Configuración del modelo (A41-8). Su `variant` debe coincidir con `--model`. |
| `--runs-dir` | `runs/` | Dónde se crea `<run_id>/`. |
| `--graphs-dir` | `artifacts/graphs/D1_holofood` | Solo `d1`: salida de `scripts/build_graph.py --save-graphs`. |
| `--n-samples`, `--first-seed`, `--split-seed` | 50, 1, 42 | Solo `synthetic`: cohorte y partición. |
| `--lr`, `--seed`, `--max-epochs`… | — | Sobrescriben la configuración (A44-4); la configuración efectiva queda en `run.json`. |

El script hace, en orden:

1. **Datos.**
   - `synthetic`: la misma cohorte y partición que `scripts/compare_baselines.py`
     (`build_synthetic_cohort(50, 1)` y `create_split` con semilla 42). Las mismas instancias
     se convierten con `build_synthetic_graphs`. La partición se crea en memoria: el
     `split_file` de la configuración no se usa, `run.json` guarda la partición con
     `file: null` y su hash, y `dataset_id` pasa a `synthetic_baseline_cohort`.
   - `d1`: lee los grafos de `--graphs-dir/graphs` y conserva solo los entregables según
     `--graphs-dir/report.json`, porque `build_graph.py` también guarda los grafos con `ERROR`.
     La partición es la de `split_file` (`configs/splits/d1_holofood.json`).
2. **Preparación** con `prepare_training_graphs` (A44-1).
3. **Escalado**: `FeatureScaler` y `TargetScaler` se ajustan con `train` (A44-2).
   `scale_loaders` aplica las features a los tres subconjuntos y rehace los `DataLoader`.
4. **Modelo**: `set_seed(seed)` y `build_model` (A41-8).
5. **Entrenamiento** con `train_model` (A44-3).
6. **Evaluación** de `train`, `val` y `test` con los pesos de la mejor época.
   `predictions.csv` sigue el orden de los grafos, sin barajar.
7. **Registro** en `runs/<run_id>/` con `save_run` (A44-5).

Imprime los conteos por subconjunto, la mejor época, el RMSE promedio de `val` y la tabla de
métricas, y termina con la ruta de la corrida. Código de salida `2` si faltan datos o una
configuración es inválida.

Desde Python, `run_training(prepared, model_config, config, split, split_file=...)`
(`nutrigraphdt.models.training.pipeline`) hace los pasos 3 a 7.

**Dónde quedan los archivos.** En `runs/<run_id>/`, ignorado por Git; ver
[Trazabilidad de corridas](#trazabilidad-de-corridas-a44-5). Para recargar una corrida y predecir
sin reentrenar, use `load_run` como en [Recargar una corrida](#recargar-una-corrida).

### Reportar las corridas sintéticas (A45-3)

`scripts/report_gnn.py` consume tres corridas existentes de `homo_sage`, `hetero_sage` y
`hetero_gat`; no entrena ni selecciona automáticamente la corrida más reciente. Lee
`metrics.csv` y `run.json` de cada directorio y valida la cohorte y los tamaños de partición
contra `reports/baselines/run.json`, además de exigir el mismo SHA-256 de partición entre las
tres corridas (en D1, que el de cada una pertenezca al archivo de partición; ver más abajo). La comparación con `dummy_mean` lee las métricas de
`reports/baselines/report.csv`.

Escribe `report.md`, `report.csv` y `run_<variante>.json` en
`reports/gnn/synthetic/`. Solo copia los metadatos `run.json`; no copia checkpoints ni otros
archivos de entrenamiento. Para que las corridas correspondan a la misma evaluación, use la
cohorte y semilla indicadas en `reports/baselines/run.json` y conserve juntos los tres
directorios de corrida:

```bash
python scripts/report_gnn.py --homo-sage-run runs/<run_id> \
    --hetero-sage-run runs/<run_id> --hetero-gat-run runs/<run_id>
```

El reporte advierte que los AGCC del generador sintético no dependen de las entradas. Por ello,
los resultados verifican el flujo, no capacidad predictiva; diferencias pequeñas frente a
`dummy_mean` no se interpretan ni se presentan como superioridad de una variante.

### Reportar las corridas D1 (A45-4)

El mismo script acepta `--dataset d1`. En ese modo, los valores predeterminados son
`reports/baselines/d1/run.json`, `reports/baselines/d1/report.csv` y `reports/gnn/d1/`. La
partición de referencia es `configs/splits/d1_holofood.json`; `--split-config` permite indicar
otra configuración, lo que también permite probar el reporte con
`tests/fixtures/holofood/split.json` sin leer `data/` ni `artifacts/`.

Antes de escribir, el script verifica para cada corrida que su variante y `dataset_id` sean los
esperados, que `split.file`, `split.version` y `split.sha256` correspondan al archivo de
partición indicado (`split.sha256` puede ser el hash canónico o, en corridas anteriores a #133,
el de los bytes del archivo con fines de línea LF o CRLF) y que el número de grafos con los tres AGCC en cada subconjunto coincida con
`subset_sizes` del `run.json` baseline D1. Así las tres variantes quedan alineadas con el mismo
baseline y partición. Los argumentos `--baseline-run-json` y `--baseline-report-csv` pueden
sobrescribir los baselines predeterminados, por ejemplo en pruebas.

El `report.md` contiene las métricas de `val` y `test`, la comparación con `dummy_mean`, conteos
de grafos recibidos/entregables/con AGCC por subconjunto y una tabla de duración, dispositivo,
commit y estado `dirty` de cada corrida. La duración se describe según el dispositivo registrado;
no se exige que las corridas sean de CPU. El informe advierte que D1 no incluye el tratamiento
dietario en las entradas de la GNN, que los taxones aislados impiden comparar el efecto de las
convoluciones entre variantes y que `val` solo tiene 7 animales con los tres AGCC.

Los grafos D1 contienen aproximadamente 1315 taxones por animal. El coste de entrenamiento,
especialmente en CPU, puede ser mayor que en los experimentos sintéticos pequeños; no se fija una
duración estimada sin medirla en el dispositivo y entorno de cada corrida.

**Corridas oficiales.** No genere los archivos de `reports/gnn/d1/` durante la edición de código.
Después del primer commit, con el árbol limpio, entrene las tres variantes y luego genere el
reporte para que `run.json` registre `git.dirty = false`. En PowerShell, desde la raíz:

```powershell
$runsRoot = Join-Path .\runs ("d1-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
python .\scripts\train_gnn.py --model homo_sage --dataset d1 --seed 42 --runs-dir (Join-Path $runsRoot "homo_sage")
python .\scripts\train_gnn.py --model hetero_sage --dataset d1 --seed 42 --runs-dir (Join-Path $runsRoot "hetero_sage")
python .\scripts\train_gnn.py --model hetero_gat --dataset d1 --seed 42 --runs-dir (Join-Path $runsRoot "hetero_gat")

$homoSageRun = Get-ChildItem (Join-Path $runsRoot "homo_sage") -Directory | Select-Object -ExpandProperty FullName
$heteroSageRun = Get-ChildItem (Join-Path $runsRoot "hetero_sage") -Directory | Select-Object -ExpandProperty FullName
$heteroGatRun = Get-ChildItem (Join-Path $runsRoot "hetero_gat") -Directory | Select-Object -ExpandProperty FullName
python .\scripts\report_gnn.py --dataset d1 --homo-sage-run $homoSageRun --hetero-sage-run $heteroSageRun --hetero-gat-run $heteroGatRun --output .\reports\gnn\d1
```

### Reproducir una corrida registrada (A45-8)

`scripts/reproduce_run.py` comprueba que otra persona, en otro equipo, obtiene lo mismo a partir
de una corrida registrada. Recibe la carpeta de la corrida o solo su `run.json`. La comparación
está en `nutrigraphdt.models.training.reproducibility`, que no requiere PyTorch.

**Pasos**

1. **Entorno limpio.** Clone el repositorio en una carpeta nueva y cree un entorno virtual
   nuevo:

   ```bash
   git clone https://github.com/jvnioo/NutriGraphDT.git && cd NutriGraphDT
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
   pip install -e ".[dev,graph,baselines]"
   ```

   La cohorte sintética requiere el extra `baselines`. Para D1, genere antes los grafos con
   `scripts/fetch_holofood.py` y `scripts/build_graph.py --save-graphs`.

2. **Reentrenar y comparar** con un solo comando:

   ```bash
   python scripts/reproduce_run.py reports/gnn/synthetic/run_homo_sage.json
   python scripts/reproduce_run.py runs/<run_id>        # carpeta completa de otra persona
   ```

   El script hace lo siguiente:

   - lee del `run.json` la variante, la semilla, `source` (cohorte o grafos),
     `training_config` y `model_config`;
   - los escribe en archivos temporales y llama a `train_gnn.py` con `--config` y
     `--model-config`, sin usar `configs/` del repositorio;
   - deja la corrida nueva en `runs/reproduce/<run_id original>/`.

3. **Comparación.** Cada fila del reporte queda como `ok`, `difiere` o `no disponible`.

   | Comparación | Contra | Tolerancia |
   |---|---|---|
   | Configuración, datos (partición, subconjuntos, metadatos), épocas | `run.json` original | igualdad exacta |
   | Escalado (medias y desviaciones de `train`) | `run.json` original | 1e-6 relativa |
   | Historia por época | `history.csv` original | 1e-4 |
   | Métricas | `metrics.csv` original o, si falta, filas `val` y `test` de `reports/gnn/<dataset>/report.csv` | 1e-5 |
   | Predicciones | `predictions.csv` original | 1e-4 mmol/kg |
   | Pesos | `checkpoint.pt` original | 1e-4 |
   | Recarga del checkpoint reproducido con `load_run` | su propio `predictions.csv` | 1e-6 |
   | Recarga del checkpoint original con `load_run` | `predictions.csv` original | 1e-4 mmol/kg |

   Las tolerancias son provisionales y se fijaron con las diferencias observadas entre Windows
   y Linux, que se deben al redondeo de float32. Un `run.json` suelto, como las copias
   `run_<variante>.json` versionadas, deja como no disponibles la historia, las predicciones y
   los pesos.

4. **Reporte.** Queda en `reports/gnn/reproducibility/<dataset>_<variante>.md` y `.json`. El
   código de salida es `0` si se reproduce, `1` si algo difiere y `2` si la entrada no es
   válida. Si algo difiere, abra una issue de corrección con la causa: versión, no determinismo
   o dependencia faltante.

**Fin de línea de la partición.** Hasta #133, `run.json` guardaba el SHA-256 de los bytes de
`configs/splits/d1_holofood.json`. En Windows, Git deja ese archivo con CRLF, así que el mismo
archivo tenía otro hash que en Linux. Desde #133 el hash es el del JSON canónico del contenido
y es igual en ambos sistemas. Para las corridas ya registradas, el script acepta una diferencia
solo en `split.sha256` cuando ambos hashes pertenecen al mismo archivo (canónico, o de bytes con
LF o CRLF) y el resto de la partición coincide, y lo deja escrito en el reporte.
`report_gnn.py --dataset d1` y `compare_models.py` aplican la misma regla.

**Cohorte de D1 (#138).** Desde #138, `train_gnn.py --dataset d1` entrena solo con la cohorte
supervisada y la registra en `source.cohort` del `run.json`. Al reentrenar una corrida D1, el
script recalcula esa cohorte desde `--sources` (por defecto, `configs/sources.json`) con el umbral
de lecturas SSU registrado, y la comparación de `source` verifica que coincida. Una corrida D1
anterior a #138 no registra la cohorte: el script se detiene con código 2 y pide usar el código de
antes de #138 (por ejemplo, el commit `2db4371`) o comparar una corrida ya reproducida con
`--reproduced`. En los subconjuntos, el campo `outside_cohort`, agregado en #138, cuenta como 0
cuando falta, así las corridas anteriores siguen siendo comparables.

**Resultados (16/10/2026)**

Reproducido en un entorno limpio por un integrante distinto de quien hizo las corridas
originales. El entorno era una clonación nueva de esta rama en Linux, con Python 3.13.13,
torch 2.14.1 (CPU), torch-geometric 2.8.1 y scikit-learn 1.9.1, instalada con
`pip install -e ".[dev,graph,baselines]"`. Reportes en `reports/gnn/reproducibility/`.

Los reportes se generaron con el código de esta rama antes de incorporar la cohorte de #138
(commit `f46f37f`). Después de rebasar sobre `main` se repitieron las tres reproducciones
sintéticas, con el mismo resultado. La corrida D1 de referencia es anterior a #138 (se entrenó sin
el filtro de cohorte), así que su reporte vale para el código de ese momento y ya no se puede
reentrenar con el código actual.

| Corrida original | Equipo original | Qué se comparó | Mayor diferencia | Resultado |
|---|---|---|---|---|
| A45-3 `homo_sage` (`20261015-044002`) | Windows, Python 3.14.5, PyG 2.8.0.post1 | `run.json` versionado y métricas de `report.csv` | 1.2e-6 (métricas) | se reproduce |
| A45-3 `hetero_sage` (`20261015-044015`) | ídem | ídem | 1.0e-6 | se reproduce |
| A45-3 `hetero_gat` (`20261015-044030`) | ídem | ídem | 5.7e-7 | se reproduce |
| D1 `homo_sage` 64 × 2, semilla 42 (`20261015-182656`, fase de semillas de A45-5) | Windows, Python 3.13.14 | carpeta completa: historia, métricas, predicciones, pesos y checkpoint | 4.5e-6 (pesos); 3.8e-6 mmol/kg (predicciones) | se reproduce |

- **Corridas de A45-3.**
  - Configuración, partición (mismo SHA-256), subconjuntos, metadatos, escalado y épocas
    coinciden exactamente: mejor época 4, 4 y 6, y 24, 24 y 26 épocas.
  - Las métricas de `val` y `test` coinciden dentro de 1.2e-6.
  - El checkpoint reproducido, recargado con `load_run`, da exactamente sus predicciones.
  - La carpeta original de A45-3 (historia, predicciones y checkpoint) no está versionada, así
    que esas comparaciones quedan como no disponibles.
- **Corrida completa de D1.** Sirve para comparar archivo por archivo entre equipos.
  - Todo coincide dentro de la tolerancia.
  - El checkpoint de Windows, recargado en Linux, reproduce sus predicciones (3.8e-6 mmol/kg).
  - La única diferencia exacta es `split.sha256`, por el fin de línea (ver arriba). Las corridas
    registradas después de #133 ya no tienen esta diferencia.
- **Conclusión.** En CPU, una corrida registrada se reproduce en otro equipo, sistema operativo y
  versión de Python a partir de su `run.json`. Las diferencias están en el orden de 1e-6, por el
  redondeo de float32. No se encontró no determinismo.

### GPU (opcional)

`--device cuda` (o `cuda:N`) entrena en GPU. El bucle mueve el modelo y cada lote al
dispositivo, y `set_seed` mantiene los algoritmos deterministas. **CPU sigue siendo la
referencia de reproducibilidad** (política de costo cero, §6 de
[gnn-architecture.md](gnn-architecture.md)): la misma configuración da resultados distintos en
CPU y en GPU, porque el redondeo de punto flotante cambia. Por ejemplo, en el sintético
`homo_sage` elige la época 4 en CPU y la 8 en GPU. Las cifras que vayan al informe deben salir
de una sola clase de dispositivo, y `run.json` registra cuál (`environment.device`,
`device_name` y `gpu_backend`).

Con una GPU AMD, PyTorch necesita la compilación ROCm, que se instala en un entorno aparte para
no reemplazar el torch de CPU del entorno de desarrollo. Por ejemplo, en una Radeon RX 9060 XT
(RDNA4) con Python 3.14:

```bash
python -m venv ~/.venvs/nutrigraphdt-rocm
# La rueda ROCm ocupa varios GB al descomprimirse; si /tmp es un tmpfs pequeño, use otro TMPDIR.
TMPDIR=~/.cache/pip-tmp ~/.venvs/nutrigraphdt-rocm/bin/pip install "torch==2.13.0+rocm7.1" \
    --index-url https://download.pytorch.org/whl/rocm7.1
~/.venvs/nutrigraphdt-rocm/bin/pip install -e ".[dev,graph]"
~/.venvs/nutrigraphdt-rocm/bin/python scripts/train_gnn.py --model hetero_gat --dataset d1 --device cuda
```

PyTorch expone ROCm con la misma API de `cuda`. En NVIDIA, el determinismo de cuBLAS además
requiere `CUBLAS_WORKSPACE_CONFIG=:4096:8`.

En el sintético (50 animales, configuración por defecto), una RX 9060 XT entrenó `homo_sage` en
10 s y `hetero_gat` en 13 s, frente a 50 s y 20 s en una CPU de 6 núcleos que estaba corriendo
otros procesos. Con grafos tan pequeños la ganancia es moderada. En D1 (1315 taxones por grafo)
debería ser mayor, pero no está medido.
