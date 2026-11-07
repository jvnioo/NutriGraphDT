# Constructor del grafo heterogéneo desde datos preprocesados

Guía de A39-1 (#35). El constructor recibe las tablas normalizadas del módulo de datos y el
esquema v1 del grafo, y entrega un `HeteroData` por instancia. Requiere el extra `graph`
(ver [`development.md`](../process/development.md#optional-graph-extra-pytorch-and-pytorch-geometric)).

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
| features `host` (`<sample_id>:host`) | covariables numéricas del nodo `host` (`body_weight_g`) | no entran a `x` en D1: el peso se informa, no es entrada (contrato v2 §3) |
| `host_covariates` de la instancia | `trial_code`, `pen_code`, `sampling_day`, `sex` y `breed` en `host.covariates`; un valor ausente queda en `null` con `missing_mask["covariates.<nombre>"]` | `x` de `host`: one-hot de `trial_code`, `sampling_day`, `sex` y `breed` (10 columnas; `pen_code` nunca). Los vocabularios se declaran en `metadata.json` (`vocabularies`) y NOD-11 informa los valores fuera de ellos (#147) |
| `diet_treatment` conocido | nodo `diet` (`<sample_id>:diet`) con el nombre del tratamiento | nodo `diet`; con el contrato v2, una columna one-hot por tratamiento de D1 (`diet_treatment=CC`, `=CO`, `=CE`; #176). La composición no está en las tablas. |
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
  `node_id`, y `taxonomy_level` viene de la columna homónima de `features`.
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

Con las reglas de integridad 1.3.0, de los 185 grafos reales de D1 son entregables los 61 que
tienen metabolitos: NOD-12 exige en datos reales dieta, taxón, metabolito y huésped (D-08).
Las reglas aplican la [propuesta de evidencia y escenario](evidence-and-scenario-proposal.md)
corregida por Investigación. Ver el
[reporte de validación de los grafos reales](real-graph-validation-report.md).

**Evidencia de las aristas de tabla.** `evidence_method` es el de la fila de `edges` o, si
falta, el que respalda su estado en el vocabulario cerrado de EDG-04 (`observed` →
`measurement`, `annotated` → `database_annotation`, `inferred` → `model_prediction`,
`hypothetical` → `expert_hypothesis`). Desde el esquema tabular `2.0.0` (contrato v2 §5, #149)
los estados son los cinco de DS-01: una fila con `experimental` o `literature` se rechaza al
crearla, con un mensaje que indica el estado y el método equivalentes (`observed` +
`measurement`, `annotated` + `literature_curation`). `evidence_source`
(procedencia: `<base>@<versión>` o `doi:…`) pasa de la fila a la arista. Una anotación sin
procedencia no se inventa: EDG-04 la informa como `ERROR`.

**Capacidad funcional y tabla de equivalencias (S-04).** `build_hetero_graph(...,
taxon_links=...)` recibe la tabla SILVA → GTDB con la forma `{"source", "version",
"one_to_one": [taxon_id, ...]}`, la copia a `metadata.json` y solo genera aristas `taxon →
has_capacity → function` de instancias reales desde taxones con enlace `1:1`. Sin tabla no se
genera ninguna; `metadata.configuration.skipped_has_capacity` cuenta las filas descartadas.

**Ruta taxón → función → metabolito de D1 (#175).** `scripts/build_graph.py` agrega las abundancias
a género con nodos residuales (contrato v2 §6) y pasa `annotations=FunctionalAnnotations.load()`.
Esa clase lee y contrasta tres tablas versionadas:

| Tabla | Contenido | Origen |
|---|---|---|
| `configs/taxonomy/s04_silva132_gtdb_r207.tsv` | Enlaces SILVA 132 → GTDB r207 | Decisión de Investigación de #236 |
| `configs/functions/has_capacity_d1.tsv` | Qué KO trae cada género `1:1` en el catálogo, con su soporte | `scripts/build_capacity_table.py` (regla de #257, sección 4) |
| `configs/functions/scfa_produces_d1.tsv` | Qué AGCC libera cada KO | Decisión de Investigación de #257 |

- **Identificadores.** Los nodos conservan el nombre SILVA, y el género GTDB solo sirve para consultar
  el catálogo. Por eso `g__Tyzzerella` recibe las funciones de `g__Anaerotignum`, y
  `g__Bifidobacterium`, que es `1:N`, no recibe ninguna aunque el catálogo tenga ese nombre. No se
  pasa `mapping_table` a `aggregate_to_genus`, porque renombraría los nodos y uniría géneros.
- **`function`.** `function_id = ko:Kxxxxx`, `function_type = kegg_ortholog`. No tiene columnas en
  `x`: el encoder usa un vector aprendido común, y cada nodo se distingue por lo que recibe.
- **Evidencia.** `has_capacity` es `annotated` / `database_annotation` /
  `mgnify-chicken-gut@v1.0.1`. `produces` es `annotated` / `database_annotation` / `KEGG@120.0`, y
  solo existe si el metabolito se midió en esa instancia.
- **Residuales y linaje.** Los nodos residuales no reciben aristas funcionales. `taxonomy_id` guarda
  el linaje hasta el rango de trabajo, del que `lineage_group` obtiene la familia (#239).
- **Soporte.** La fracción de especies con el KO queda en la tabla y no entra al grafo: la decisión
  de #257 lo deja a criterio de Desarrollo, y agregarla cambiaría el contrato de la relación.

`--raw-taxa` y `--no-functions` construyen el grafo anterior a #175. Capacidad anotada no es
actividad demostrada, y las cifras de cobertura están en
[`decision_minimal_graph_D1.md`](../research/decision_minimal_graph_D1.md).

## Datos sintéticos

El constructor también acepta las tablas del dataset sintético
(`DataPipeline(...).run(["synthetic-v1"])`), pero el pipeline solo conserva las abundancias,
así que el grafo resultante tiene menos tipos de nodo que el sintético original. Para el
prototipo sintético completo siga usando `build_synthetic_graphs` (A35-1).
