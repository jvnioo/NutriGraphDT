# Módulos de la entrega y API pública (A120-P2, #353)

Referencia de los módulos de `src/nutrigraphdt/` en el estado de entrega: para qué sirve cada uno,
qué recibe, qué entrega y qué límites tiene, con el documento detallado de cada uno. Los límites
de módulo y la dirección de dependencias están en [`architecture.md`](architecture.md). Cómo
instalar y correr todo, en la [guía de reproducibilidad](../process/reproducibility-guide.md).

> **Datos sintéticos.** La plataforma, la simulación y la entrega usan la cohorte sintética: una
> diferencia entre escenarios describe al modelo, no un efecto biológico. D1 (HoloFood) queda
> como resultado exploratorio ([alcance](../process/final-scope.md)).

## Mapa

| Módulo | Extras | Propósito |
|---|---|---|
| [`api`](#api) | `graph`, `baselines` (motor) | **API pública** entre el motor y la interfaz: contrato versionado y motor de escenarios. |
| [`simulation`](#simulation) | (usa `api`) | Catálogo de escenarios de referencia y comparación basal frente a intervenido. |
| [`scenarios`](#scenarios) | — | Soporte empírico de las predicciones de escenarios (D-06 §7). |
| [`demo`](#demo) | `graph`, `baselines`, `demo` | Web App en Streamlit. |
| [`delivery`](#delivery) | `graph`, `baselines` | Pipeline sintético completo con la configuración de entrega. |
| [`data`](#data) | — | Contratos de datos, cohorte sintética, carga y preprocesamiento de D1. |
| [`graph`](#graph) | `graph` (tensores) | Esquema, construcción y validación del grafo heterogéneo. |
| [`models`](#models) | `baselines`, `graph` | Baselines, GNN, entrenamiento, validación cruzada, métricas e incertidumbre. |
| [`constraints`](#constraints) | `graph` (penalizaciones) | Restricciones estructurales y bioquímicas (D-06) y su evaluación. |
| [`explainability`](#explainability) | `graph` (explicadores) | Contrato de explicaciones, explicadores de PyG y análisis. |

Los extras se instalan con `pip install -e ".[…]"`; ver
[`development.md`](../process/development.md). Los paquetes que necesitan PyTorch lo importan
solo al usarse, así que `nutrigraphdt` se importa sin él.

## `api`

**API pública de la entrega.** Es lo único que importa la interfaz.

- **Entradas:** un `ScenarioRequest` (instancia base, cambios de dieta o aditivo, versión del
  contrato) y una corrida congelada (`run_dir` con `checkpoint.pt` y `run.json`).
- **Salidas:** un `ScenarioResponse` con las fracciones de acetato, propionato y butirato,
  `ln T`, el estado (`estimable` o `no_estimable` con sus motivos), el soporte aplicado y, con
  `with_interval`, el intervalo MC-dropout (`PredictionInterval`).
- **Piezas:**
  - `contract`: modelos pydantic del contrato (`ScenarioRequest`, `ScenarioResponse`,
    `PredictionInterval`, `Bounds`…). No depende de PyTorch.
  - `engine`: `ScenarioEngine` (carga la corrida, predice, calcula el intervalo y aplica la
    calibración de #391) y `predict_scenario`.
  - `demo` y `fixtures`: corridas de demostración (`DEMO_RUNS`) y su reconstrucción.
- **Límites:**
  - Una predicción fuera del soporte empírico es `no_estimable` y no lleva número.
  - El intervalo solo está calibrado si la corrida coincide con la calibración
    (`ScenarioEngine.calibration_note` dice por qué no).
- **Documentos:** [`api-contract.md`](api-contract.md) y
  [`uncertainty.md`](../models/uncertainty.md) §7.

## `simulation`

- **Entradas:** el catálogo de `configs/scenarios/` y un `ScenarioEngine`.
- **Salidas:** para cada escenario, la comparación basal frente a intervenido con el mismo modelo
  congelado (`compare_scenario`) y su estado por AGCC.
- **Límites:** reutiliza el motor de `api`; no importa PyTorch hasta construir el motor.
- **Documento:** [`scenario-comparison.md`](../models/scenario-comparison.md).

## `scenarios`

- **Entradas:** fracciones medidas del train de una corrida.
- **Salidas:** `EmpiricalSupport`, el intervalo `[mínimo, máximo]` de cada fracción, y la
  decisión de si una predicción está dentro.
- **Límites:** es el control de D-06 §7. No extrapola fuera del soporte.
- **Documento:** [`scenario-support.md`](../models/scenario-support.md).

## `demo`

- **Entradas:** la corrida activa de `configs/platform.json` y lo que el usuario elige en la app.
- **Salidas:** las páginas de Streamlit (inicio, escenario, resultados, grafo, comparación de
  grafos, explicación) y la exportación del resultado a JSON y CSV.
- **Piezas:** `service` (simula y exporta), `results` y `plots` (figuras), `state` (sesión),
  `pages` (una función `render()` por página). La entrada es `scripts/demo_app.py`.
- **Límites:** todo resultado lleva los rótulos de datos sintéticos y de que asociación no es
  causalidad.
- **Documentos:** [`demo.md`](../demo.md), [`e2e-cases.md`](../process/e2e-cases.md) y
  [`platform-manual-test.md`](../process/platform-manual-test.md).

## `delivery`

- **Entradas:** `configs/delivery.json` (semillas, corridas, tolerancias).
- **Salidas:** `reports/delivery/` (`report.md` y `results.json`): datos, grafo, entrenamiento,
  reproducibilidad frente a las corridas congeladas, escenarios y explicación.
- **Límites:** sin red ni `data/raw/`. Termina con código 1 si una corrida no se reproduce o un
  escenario cambia de estado.
- **Documento:** [`delivery.md`](../process/delivery.md).

## `data`

- **Entradas:** semillas de la cohorte sintética, o los archivos de D1 descargados con
  `scripts/fetch_holofood.py`.
- **Salidas:** registros de nodos, aristas e instancias según el contrato de datos, y tablas
  normalizadas.
- **Piezas:** `synthetic` (generador y escenarios sintéticos), `loaders` y `preprocessors` (D1),
  `schema`, `covariates`, `derived`, `split`.
- **Límites:** no contiene lógica de entrenamiento.
- **Documentos:** [especificación del dataset sintético](../synthetic-dataset/synthetic-dataset-spec.md),
  [contrato de datos v2](../graph/data-contract-v2.md) y [D1](../data-sources/holofood-source.md).

## `graph`

- **Entradas:** los registros de `data`.
- **Salidas:** grafos `HeteroData` (8 tipos de nodo, 11 relaciones) y hallazgos de validación.
- **Piezas:** `builder`, `heterodata`, `validation` (`validate_graph`, `prepare_graphs_for_model`).
- **Límites:** un grafo con errores no llega al modelo.
- **Documentos:** [esquema](../graph/graph-schema-v1.md),
  [reglas de integridad](../graph/graph-integrity-rules.md) y
  [constructor](../graph/graph-builder.md).

## `models`

- **Entradas:** grafos o tablas de atributos, configuraciones de `configs/models/` y
  `configs/training/`, y planes de validación cruzada de `configs/splits/`.
- **Salidas:** corridas en `runs/` (no versionadas), métricas, reportes de evaluación e
  intervalos con su calibración.
- **Piezas:** `baselines`, `gnn` (`homo_sage`, `hetero_sage`, `hetero_gat`), `training`,
  `cross_validation`, `composition` (objetivo composicional), `uncertainty` (ensamble,
  MC-dropout y `IntervalCalibration`).
- **Límites:** la elección de arquitectura es una decisión de investigación; las métricas en D1
  son exploratorias.
- **Documentos:** [arquitectura de la GNN](../models/gnn-architecture.md),
  [entrenamiento](../models/gnn-training.md), [métricas](../models/metrics.md) e
  [incertidumbre](../models/uncertainty.md).

## `constraints`

- **Entradas:** predicciones composicionales.
- **Salidas:** penalizaciones diferenciables para el entrenamiento y registros de violación por
  muestra.
- **Límites:** solo las restricciones aprobadas (estructurales y la cota de propionato de D-06
  v1).
- **Documentos:** [restricciones](../models/constraints.md) y
  [protocolo de evaluación](../models/constraints-evaluation-protocol.md).

## `explainability`

- **Entradas:** un modelo entrenado y un grafo.
- **Salidas:** una `Explanation` en el formato `nutrigraphdt-explanation` (importancia de nodos,
  atributos y aristas, subgrafo y advertencias obligatorias).
- **Límites:** la importancia no es evidencia ni causalidad; la atención no se usa como
  explicación.
- **Documentos:** [contrato de explicaciones](../models/explanation-contract.md) y
  [compatibilidad de explicadores](../models/explainer-wrapper-compatibility.md).

## Docstrings

Toda función y clase pública de `nutrigraphdt` tiene docstring.
`tests/unit/test_public_docstrings.py` lo comprueba.
