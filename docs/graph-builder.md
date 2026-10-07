# Constructor del grafo heterogéneo desde datos preprocesados

Guía de A39-1 (#35). El constructor recibe las tablas normalizadas del módulo de datos y el
esquema v1 del grafo, y entrega un `HeteroData` por instancia. Requiere el extra `graph`
(ver [`development.md`](development.md#optional-graph-extra-pytorch-and-pytorch-geometric)).

## Flujo

```text
DataPipeline           → instancias y features de taxón (abundancias)
attach_sample_context  → contexto de la instancia, huésped y targets (metadatos y metabolitos)
build_hetero_graph     → registros DS-01 y un HeteroData por instancia
audit_built_graphs     → reglas de registro y de tensores, y contratos Pydantic
```

Con la fuente real D1 HoloFood ya descargada (`scripts/fetch_holofood.py`):

```bash
python scripts/build_graph.py --save-graphs
```

Escribe `artifacts/graphs/D1_holofood/report.json` y, con `--save-graphs`, un `.pt` por
instancia en `graphs/`. Desde Python:

```python
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.graph.audit import audit_built_graphs
from nutrigraphdt.graph.builder import add_reverse_edges, build_hetero_graph

sources = load_sources()
tables = DataPipeline({"D1_holofood": sources["D1_holofood"]}).run(["D1_holofood"]).dataset
tables, integration = attach_sample_context(
    tables,
    metadata=MetadataLoader(sources["D1_holofood_metadata"]).load(),
    metabolites=MetaboliteLoader(sources["D1_holofood_scfa_content"]).load(),
)
built = build_hetero_graph(tables)  # built.graphs: {graph_id: HeteroData}
audit = audit_built_graphs(built)
model_inputs = [
    add_reverse_edges(built.graphs[graph_id])
    for graph_id in audit.report.deliverable_graph_ids  # hoy vacío: ver "Entrega a un modelo"
]
```

## Qué produce cada tabla

| Tabla normalizada | Registro DS-01 | En el `HeteroData` |
|---|---|---|
| `instances` | instancia | atributos globales (`graph_id`, `species`, `diet_treatment`, …) |
| `features` de un nodo | nodo con los atributos numéricos del esquema v1 | fila de `x` del tipo |
| features `host` (`<sample_id>:host`) | covariables del nodo `host` | `x` de `host` (`covariates.body_weight_g`) |
| `diet_treatment` conocido | nodo `diet` (`<sample_id>:diet`) con el nombre del tratamiento | nodo `diet` (sin columnas: la composición no está en las tablas) |
| `targets` de metabolitos | nodo `metabolite` y salida `measured` | `y` e `y_mask` de `metabolite` |
| cada target medido | arista `metabolite → measured_in → host`, `observed` | `edge_index` de esa relación |
| `edges` | arista con su relación, si está en el esquema v1 | `edge_index` de la relación |

La codificación de features es la del prototipo (`prototype-0.1` en `heterodata.py`): valores
crudos, una columna por magnitud y unidad, y las columnas son comunes a todas las instancias
del conjunto (TEN-06). Una instancia sin un valor tiene `0.0` y `missing_mask = true` en esa
columna.

## Decisiones

- **Nunca se inventa un valor.** Un atributo del esquema v1 que las tablas no traen queda en
  `null` con `missing_mask: true` (DS-01). En `taxon`, `taxonomy_id` es `raw_id` o el
  `node_id`; `taxonomy_level` queda ausente hasta #66.
- **El target no se filtra a `x`.** El nodo `metabolite` no guarda la concentración en sus
  atributos; el valor medido solo vive en `y`.
- **IDs derivados del `sample_id`.** `host` y `diet` usan `<sample_id>:host` y
  `<sample_id>:diet`, de modo que conservan el prefijo `synthetic:` en datos sintéticos
  (NOD-04) y los escenarios de una misma muestra comparten IDs (INS-05).
- **Errores que impiden traducir.** `build_hetero_graph` lanza `ValueError` ante una relación
  fuera del esquema v1, referencias a instancias inexistentes, features repetidas en un nodo,
  dos targets del mismo metabolito en una instancia o una mezcla de instancias sintéticas y
  reales. Los tipos de nodo desconocidos ya los rechaza `NormalizedFeatureRecord`.
- **Reproducible.** Para la misma entrada, en cualquier orden, los grafos son idénticos: nodos,
  aristas y columnas se ordenan de forma determinista.
- **Relaciones inversas solo para el modelo.** EDG-01 prohíbe inversas en los registros.
  `add_reverse_edges` devuelve una copia con `rev_<relación>` para modelos de paso de
  mensajes, después de validar.

## Entrega a un modelo

`build_hetero_graph` no aplica la compuerta de entrega. `audit_built_graphs` evalúa todas las
reglas; solo los grafos de `audit.report.deliverable_graph_ids` deben llegar a un modelo. A
diferencia de `prepare_graphs_for_model`, la auditoría evalúa las reglas de tensores en todos
los grafos, también en los que tienen errores de registro, porque los tensores ya existen.

Hoy ningún grafo real es entregable por tres reglas provisionales que esperan decisiones:
EDG-04 (#62), INS-03 (#63) y MET-01 (#64). Ver el
[reporte de validación de los grafos reales](real-graph-validation-report.md).

## Datos sintéticos

El constructor también acepta las tablas del dataset sintético
(`DataPipeline(...).run(["synthetic-v1"])`), pero el pipeline solo conserva las abundancias,
así que el grafo resultante tiene menos tipos de nodo que el sintético original. Para el
prototipo sintético completo siga usando `build_synthetic_graphs` (A35-1).
