# Especificación del dataset sintético

## Estado y autoridad

- **Tarea:** DS-01 — Definir la estructura del dataset sintético.
- **Versión del esquema:** `1.0.0` (`synthetic-v1`).
- **Estado:** contrato estructural inicial para las capas `data` y `graph`.
- **Alcance científico:** provisional. Esta versión no valida relaciones biológicas,
  efectos de intervenciones, rangos fisiológicos ni causalidad.

Esta especificación es la fuente canónica para las tareas DS-02 a DS-07. Deriva del
[Esquema General del proyecto](../research/Esquema_General_del_proyecto_Microbioma_Digital.md),
en particular de sus secciones 2.1, 2.2, 2.3 y 6.1. Cuando este documento y una
implementación difieran, la implementación debe corregirse o el contrato debe cambiarse
explícitamente mediante revisión y actualización de `schema_version`.

La guía para generar, cargar y usar el dataset está en
[`synthetic-dataset-usage.md`](synthetic-dataset-usage.md). Los valores concretos que emite
el generador implementado (unidades, vocabularios y rangos) están en
[`synthetic-dataset-dictionary.md`](synthetic-dataset-dictionary.md).

En este documento, **obligatorio** significa que la clave debe existir. Un valor ausente
se representa con `null` en JSON y con su máscara activada; no se reemplaza por cero, una
cadena vacía ni una categoría inventada. El generador estándar debe completar todos los
campos obligatorios. Los valores ausentes solo se admiten en configuraciones destinadas a
probar ese comportamiento.

## Propósito y límites

El dataset sintético permite desarrollar y probar el flujo `data -> graph -> models` sin
presentar registros artificiales como observaciones reales. Debe poder sustituirse por una
fuente real compatible sin cambiar las interfaces entre `data` y `graph`.

Esta versión define:

- los objetos `Nodo`, `Arista`, `Instancia` y `Salida` del contrato mínimo;
- ocho tipos de nodo y once tipos de relación permitidos;
- los atributos obligatorios y sus tipos de intercambio;
- la correspondencia con `torch_geometric.data.HeteroData`;
- el formato de serialización y las reglas mínimas de integridad;
- las decisiones que siguen pendientes de Investigación.

Esta versión no define rangos biológicos, distribuciones estadísticas, vocabularios
taxonómicos o funcionales definitivos, ecuaciones bioquímicas, efectos de aditivos ni una
partición de entrenamiento. Tampoco implementa el generador.

## Convenciones generales

### Tipos de intercambio

Los tipos `str`, `bool`, `int`, `number`, `list[T]`, `object` y `null` tienen la semántica
de JSON. Los números deben ser finitos: `NaN`, `Infinity` y `-Infinity` no son válidos.

Los identificadores sintéticos deben usar un espacio de nombres reconocible, por ejemplo
`synthetic:taxon:0001`. No deben parecer accesiones reales ni reutilizar identificadores de
organismos, muestras, compuestos u ontologías reales sin una correspondencia verificada.

`node_id` debe ser único dentro de `(graph_id, node_type)`. La combinación de tipos de una
relación desambigua sus extremos. Se recomienda, además, usar prefijos por tipo para evitar
colisiones durante la inspección y exportación.

### Unidades y magnitudes

Toda magnitud debe viajar con una unidad explícita. Una cadena de unidad identifica la
convención usada por la configuración del generador; esta especificación no aprueba un
vocabulario de unidades concreto. No se pueden comparar, normalizar ni concatenar valores
de unidades o matrices diferentes sin una transformación documentada.

No se fijan rangos numéricos en DS-01. Las configuraciones futuras deben declarar rango,
distribución y unidad de cada variable y marcar esos valores como convenciones sintéticas
o respaldarlos con una fuente verificable. El término "plausible" no debe usarse para un
rango que solo fue elegido por conveniencia computacional.

### Ausencia de datos

En JSON, `missing_mask` es un objeto `dict[str, bool]` cuyas claves son rutas relativas a
`attributes`, por ejemplo `{"abundance": false}`. `true` significa que el valor es ausente.
En `HeteroData`, la máscara de features es un tensor booleano con la misma forma que `x`.

Los campos identificadores, discriminadores de tipo y metadatos de procedencia no pueden
ser ausentes. En particular, no pueden ser `null`: `graph_id`, `node_id`, `node_type`,
`source_id` de un nodo, los extremos y tipo de una arista, `evidence_id`,
`evidence_status`, `is_synthetic`, `schema_version` y `generator_version`.

## Contrato de nodo

Cada línea de `nodes.jsonl` contiene `graph_id` más el objeto lógico `Nodo`:

| Campo | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `graph_id` | `str` | Sí | Clave de transporte que enlaza el nodo con una instancia. |
| `node_id` | `str` | Sí | Único dentro de `(graph_id, node_type)`. |
| `node_type` | `str` | Sí | Uno de los ocho códigos definidos abajo. |
| `source_id` | `str` | Sí | Procedencia; para el generador base, `SYNTHETIC_V1`. |
| `attributes` | `object` | Sí | Atributos propios del tipo de nodo. |
| `missing_mask` | `object` | Sí | Máscara por atributo; `{}` si no hay valores ausentes. |

`source_id` en un nodo identifica procedencia. No debe confundirse con `source_id` en una
arista, que por el contrato original identifica el nodo de origen.

### Tipos de nodo y atributos

Todos los atributos enumerados como obligatorios se almacenan dentro de `attributes`.
`source_id` permanece en el nivel común del nodo.

| Código | Tipo `HeteroData` | Atributos obligatorios | Tipo |
|---|---|---|---|
| D | `diet` | `name` | `str` |
|  |  | `ingredients` | `list[str]` |
|  |  | `composition` | `list[object]` |
|  |  | `source_version` | `str` |
| A | `additive` | `category`, `substance` | `str`, `str` |
|  |  | `dose`, `dose_unit` | `number`, `str` |
|  |  | `control_label` | `str` |
| S | `substrate` | `chemical_id`, `name` | `str`, `str` |
|  |  | `quantity`, `unit` | `number`, `str` |
| T | `taxon` | `taxonomy_id`, `taxonomy_level` | `str`, `str` |
|  |  | `abundance`, `abundance_unit` | `number`, `str` |
|  |  | `quantification_method` | `str` |
| F | `function` | `function_id`, `function_type` | `str`, `str` |
|  |  | `annotation_source` | `str` |
|  |  | `annotation_value`, `annotation_value_type`, `unit` | `number`, `str`, `str` |
| M | `metabolite` | `chemical_id`, `name`, `sample_matrix` | `str`, `str`, `str` |
|  |  | `concentration`, `unit` | `number`, `str` |
| H | `host` | `species`, `gut_segment`, `cohort_id` | `str`, `str`, `str` |
|  |  | `covariates` | `object` |
| P | `phenotype` | `trait`, `timepoint` | `str`, `str` |
|  |  | `value`, `unit` | `number`, `str` |

Los nombres de los ocho tipos y el envoltorio común de nodo son decisiones estructurales
de DS-01. Todos los atributos de dominio de esta tabla permanecen provisionales hasta que
Investigación confirme ontologías, magnitudes, matrices, unidades y covariables.

Cada elemento de `diet.attributes.composition` contiene obligatoriamente
`component_id: str`, `value: number` y `unit: str`. La lista permite expresar composición
sin fijar en DS-01 un conjunto definitivo de nutrientes. `function_type` distingue, como
mínimo, gen, enzima o ruta; `annotation_value_type` distingue presencia de abundancia. Los
vocabularios exactos de estas categorías son provisionales y deben declararse en
`metadata.json`.

La primera versión usa `concentration` para metabolitos porque esa es la magnitud prevista
en el plan de implementación. Si Investigación selecciona flujo o producción como objetivo,
no se debe guardar esa magnitud bajo `concentration`: se requiere una revisión versionada
del contrato.

### Vectores de features

`x` es una representación numérica derivada; no reemplaza los atributos de intercambio.
La lista y orden de columnas se registra por tipo en `metadata.json` bajo
`node_feature_schema`. No se admite inferir el orden desde un diccionario JSON.

| Tipo | Fuente prevista para `x` | Estado |
|---|---|---|
| `diet` | Composición ordenada según vocabulario configurado. | Provisional |
| `additive` | Dosis normalizada y categorías codificadas. | Provisional |
| `substrate` | Cantidad normalizada. | Provisional |
| `taxon` | Abundancia y nivel taxonómico codificado. | Provisional |
| `function` | Valor de anotación y categorías funcionales codificadas. | Provisional |
| `metabolite` | Concentración normalizada, sin mezclar matriz ni unidad. | Provisional |
| `host` | Covariables configuradas y codificadas. | Provisional |
| `phenotype` | Valor del rasgo normalizado. | Provisional |

Normalización, vocabularios y escaladores son configuración versionada. Cuando exista una
partición de datos, sus parámetros se ajustan solo sobre entrenamiento. DS-01 no aprueba
ninguna codificación concreta.

## Contrato de arista

Cada línea de `edges.jsonl` contiene los campos siguientes:

| Campo | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `graph_id` | `str` | Sí | Clave de transporte de la instancia. |
| `source_type` | `str` | Sí | Tipo del extremo de origen. |
| `source_id` | `str` | Sí | `node_id` existente del tipo de origen. |
| `relation_type` | `str` | Sí | Relación permitida para ambos tipos. |
| `target_type` | `str` | Sí | Tipo del extremo de destino. |
| `target_id` | `str` | Sí | `node_id` existente del tipo de destino. |
| `evidence_id` | `str` | Sí | Procedencia de la afirmación relacional. |
| `evidence_status` | `str` | Sí | `synthetic`, `observed`, `annotated`, `inferred` o `hypothetical`. |
| `evidence_method` | `str` | Sí | Método que originó la relación. |
| `attributes` | `object` | Sí | Atributos particulares; `{}` cuando no correspondan. |

Mientras Investigación no defina criterios de evidencia, las aristas generadas usan
`evidence_id: "SYNTHETIC_V1"`, `evidence_status: "synthetic"` y
`evidence_method: "synthetic_generator"`. El estado estructural de la tabla siguiente
explica la semántica prevista, pero no convierte una arista sintética en evidencia
biológica.

### Relaciones permitidas

Los atributos indicados son adicionales a los campos comunes del contrato de arista.

| Tupla `(origen, relación, destino)` | Semántica | Atributos obligatorios | Estado estructural |
|---|---|---|---|
| `('diet', 'provides', 'substrate')` | Composición documentada de dieta. | `proportion: number`, `unit: str` | Aprobada como estructura |
| `('substrate', 'available_to', 'taxon')` | Recurso potencialmente disponible. | Ninguno | Provisional |
| `('taxon', 'has_capacity', 'function')` | Capacidad anotada, no actividad demostrada. | `annotation_source: str` | Provisional |
| `('function', 'produces', 'metabolite')` | Transformación candidata. | Ninguno | Provisional |
| `('metabolite', 'measured_in', 'host')` | Medición o exposición contextual. | `sample_matrix: str` | Provisional |
| `('additive', 'modulates', 'taxon')` | Hipótesis de modulación. | Ninguno | Hipotética |
| `('additive', 'modulates', 'function')` | Hipótesis de modulación. | Ninguno | Hipotética |
| `('metabolite', 'associated_with', 'phenotype')` | Asociación, no efecto causal. | Ninguno | Hipotética |
| `('host', 'exhibits', 'phenotype')` | Correspondencia observacional. | `timepoint: str` | Provisional |
| `('taxon', 'interacts_with', 'taxon')` | Interacción ecológica candidata. | `interaction_type: str` | Hipotética |
| `('function', 'cross_feeds', 'function')` | Sustrato cruzado candidato entre funciones. | `substrate_id: str` | Hipotética |

Si se usa `cross_feeds`, `substrate_id` debe identificar un nodo `substrate` de la misma
instancia. No se crean aristas `taxon -> metabolite` por coocurrencia. Tampoco se crean
aristas inversas implícitas: cualquier relación inversa derivada debe tener un tipo distinto,
procedencia explícita y una actualización de este catálogo.

## Contrato de instancia

Cada línea de `instances.jsonl` representa un grafo y contiene:

| Campo | Tipo | Obligatorio | Convención sintética inicial | Estado |
|---|---|---:|---|---|
| `graph_id` | `str` | Sí | Identificador único y determinista. | Estructura aprobada |
| `species` | `str` | Sí | `chicken` | Provisional |
| `gut_segment` | `str` | Sí | `cecum` | Provisional |
| `study_id` | `str` | Sí | `SYNTHETIC_V1` | Estructura aprobada |
| `sample_id` | `str` | Sí | Identificador sintético determinista. | Estructura aprobada |
| `scenario_id` | `str` | Sí | `basal` o `intervention` | Estructura aprobada |
| `diet_treatment` | `str` | Sí | Etiqueta sintética configurada. | Provisional |
| `timepoint` | `str` o `null` | Sí | `null` hasta definirlo. | Provisional |
| `is_synthetic` | `bool` | Sí | Siempre `true`. | Estructura aprobada |
| `schema_version` | `str` | Sí | `1.0.0` | Estructura aprobada |
| `generator_version` | `str` | Sí | Versión del paquete/generador. | Estructura aprobada |

Los valores `chicken` y `cecum` son marcadores de posición motivados por la priorización
aviar y cecal de los documentos internos; no son una decisión confirmada de Investigación.
Una instancia no mezcla especies, segmentos, individuos, escenarios ni tiempos. Las
matrices de muestra se conservan en nodos, aristas y salidas y no se combinan como si fueran
equivalentes.

## Contrato de salida

El objeto `Salida` forma parte del contrato mínimo aunque DS-01 no genere predicciones.
`outputs.jsonl` puede estar vacío hasta que una tarea produzca targets o resultados, pero
su estructura no se omite:

| Campo | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `graph_id` | `str` | Sí | Instancia a la que pertenece. |
| `target_type` | `str` | Sí | Tipo del nodo objetivo. |
| `target_id` | `str` | Sí | Nodo existente en la instancia. |
| `value` | `number` | Sí | Valor de la salida. |
| `measured_or_predicted` | `str` | Sí | `measured`, `predicted` o `synthetic`. |
| `unit` | `str` | Sí | Unidad explícita de `value`. |
| `sample_matrix` | `str` | Sí | Matriz de la salida. |
| `model_version` | `str` o `null` | Sí | Obligatorio para `predicted`; `null` en los demás casos. |

Un target artificial usa `synthetic`, nunca `measured`. Una predicción se conserva por
separado de una medición y no reemplaza atributos observados o sintéticos del nodo.

## Trazabilidad al contrato mínimo

La tabla siguiente hace explícita la correspondencia con la sección 2.3 del Esquema
General. Los campos de transporte adicionales (`graph_id`, tipos de los extremos y
`attributes` de arista) permiten reconstruir registros autocontenidos, pero no sustituyen
ningún campo del contrato base.

| Objeto del contrato | Campos de §2.3 | Representación en esta especificación |
|---|---|---|
| Nodo | `node_id`, `node_type`, `source_id`, `attributes`, `missing_mask` | Campos homónimos de `nodes.jsonl`; `node_type` selecciona el almacén PyG. |
| Arista | `source_id`, `relation_type`, `target_id`, `evidence_id`, `evidence_status` | Campos homónimos de `edges.jsonl`; se añaden tipos, método y atributos. |
| Instancia | `graph_id`, `species`, `gut_segment`, `study_id`, `sample_id`, `scenario_id` | Campos homónimos de `instances.jsonl` y atributos globales de `HeteroData`. |
| Salida | `target_id`, `measured_or_predicted`, `unit`, `sample_matrix`, `model_version` | Campos homónimos de `outputs.jsonl`; se añaden `graph_id`, tipo y valor. |

## Correspondencia con `HeteroData`

La correspondencia sigue la API oficial de
[`HeteroData`](https://pytorch-geometric.readthedocs.io/en/2.7.0/generated/torch_geometric.data.HeteroData.html).
Cada tipo de nodo tiene su propio almacén y cada relación se identifica mediante la tupla
completa `(source_type, relation_type, target_type)`.

| Contrato | Ubicación en `HeteroData` | Tipo/forma |
|---|---|---|
| Tipo de nodo | `data[node_type]` | `NodeStorage` |
| Features | `data[node_type].x` | `FloatTensor [N_type, F_type]` |
| Máscara de features | `data[node_type].missing_mask` | `BoolTensor [N_type, F_type]` |
| IDs | `data[node_type].node_id` | `list[str]`, alineada con las filas de `x` |
| Procedencia | `data[node_type].source_id` | `list[str]`, alineada con `x` |
| Atributos sin pérdida | `data[node_type].raw_attributes` | `list[object]`, alineada con `x` |
| Tipo de arista | `data[src, rel, dst]` | `EdgeStorage` |
| Conectividad | `data[src, rel, dst].edge_index` | `LongTensor [2, E_type]` |
| Features de arista | `data[src, rel, dst].edge_attr` | `FloatTensor [E_type, A_type]` |
| Evidencia | `.evidence_id`, `.evidence_status`, `.evidence_method` | `list[str]`, alineadas con columnas de `edge_index` |
| Atributos sin pérdida | `.raw_attributes` | `list[object]`, alineada con `edge_index` |
| Instancia | `data.graph_id`, `data.species`, etc. | Atributos globales |
| Salidas | `data.output_records` y, cuando aplique, `data[target_type].y` | Registros completos y tensor alineado |

`edge_index` no contiene `node_id` de texto. Contiene índices locales de fila para el tipo
de origen y el tipo de destino. La conversión debe construir un mapa
`(node_type, node_id) -> row_index`, ordenar los nodos de manera determinista y comprobar
los límites de cada índice.

Las dimensiones de features pueden variar entre tipos de nodo. `node_feature_schema` y
`edge_feature_schema` registran nombre, orden, codificación y unidad de cada columna. Una
relación sin features numéricas usa un tensor de forma `[E_type, 0]`; sus metadatos de
evidencia siguen siendo obligatorios.

Las salidas completas se conservan en `data.output_records` para no perder unidad, matriz
o versión de modelo. Si se materializa `y`, su correspondencia con nodos y el orden de sus
columnas también se declara en metadatos.

Los atributos Python no tensoriales (`node_id`, procedencia y registros crudos) se usan para
trazabilidad y round-trip. Su comportamiento al agrupar grafos debe probarse antes de usar
un `DataLoader`; las entradas del modelo son los tensores y diccionarios tipados declarados
por el pipeline.

Ejemplo estructural, no ejecutable hasta incorporar PyTorch y PyG en una tarea aprobada:

```python
from torch_geometric.data import HeteroData

data = HeteroData()
data["taxon"].x = taxon_x
data["taxon"].missing_mask = taxon_missing_mask
data["taxon"].node_id = taxon_ids
data["taxon", "has_capacity", "function"].edge_index = edge_index
data["taxon", "has_capacity", "function"].edge_attr = edge_attr
data.graph_id = graph_id
```

La conversión debe terminar con `data.validate(raise_on_error=True)` y con las validaciones
de dominio de esta especificación. La validación de PyG no sustituye la comprobación de
procedencia, unidades, evidencia o aislamiento de instancias.

## Serialización y organización de archivos

El formato primario de ejecución es un `HeteroData` por grafo serializado como `.pt`
mediante `torch.save()`. El formato de intercambio y auditoría es JSON Lines. Ambos deben
contener la misma información del contrato; el round-trip
JSONL -> `HeteroData` -> JSONL no debe perder campos ni cambiar su significado.

```text
data/
└── synthetic/
    └── v1/
        ├── README.md
        ├── metadata.json
        ├── graphs/
        │   ├── graph_0001.pt
        │   └── ...
        └── raw/
            ├── nodes.jsonl
            ├── edges.jsonl
            ├── instances.jsonl
            └── outputs.jsonl
```

Los archivos se codifican como UTF-8. Cada línea JSONL contiene exactamente un objeto JSON.
Para resultados reproducibles, el exportador ordena instancias por `graph_id`, nodos por
`(graph_id, node_type, node_id)`, aristas por
`(graph_id, source_type, relation_type, target_type, source_id, target_id)` y salidas por
`(graph_id, target_type, target_id)`.

`metadata.json` contiene como mínimo:

| Campo | Tipo | Propósito |
|---|---|---|
| `dataset_id` | `str` | Identidad del conjunto generado. |
| `schema_version` | `str` | Versión de este contrato. |
| `generator_version` | `str` | Versión del código generador. |
| `is_synthetic` | `bool` | Siempre `true`. |
| `random_seed` | `int` | Semilla de generación. |
| `configuration` | `object` | Parámetros efectivos, incluidos conteos y rangos sintéticos. |
| `node_feature_schema` | `object` | Columnas, orden, unidades y codificaciones por tipo. |
| `edge_feature_schema` | `object` | Columnas, orden, unidades y codificaciones por relación. |
| `counts` | `object` | Conteos por instancia y tipo. |

Fechas de ejecución, rutas locales u otros campos no deterministas no participan en la
identidad reproducible del contenido. Si se registran, deben separarse de los campos usados
para comprobar igualdad.

Los `.pt` solo se cargan desde una fuente confiable: `torch.load` usa mecanismos de
deserialización que no son seguros para archivos no confiables. JSONL es el formato para
inspección e intercambio independiente de clases de Python.

Los archivos generados son artefactos locales por defecto. Las tareas posteriores deben
subir código, configuración, manifiestos y ejemplos mínimos revisados; no deben subir
datasets voluminosos salvo aprobación explícita y revisión de procedencia/licencia.

## Reglas de validación

Un dataset conforme cumple todas estas reglas:

1. `schema_version` es compatible y `is_synthetic` vale `true` en dataset e instancias.
2. El perfil estándar incluye los ocho tipos de nodo y al menos un nodo de cada tipo.
3. Todos los campos obligatorios existen y respetan su tipo; los números son finitos.
4. Los IDs son únicos en su alcance y se generan de forma determinista desde configuración,
   semilla y posición estable.
5. Toda arista usa una tupla permitida y apunta a nodos existentes de los tipos declarados.
6. Toda arista declara evidencia sintética y método mientras no exista un criterio aprobado
   para otro estado.
7. `sample_matrix`, unidad y tipo de magnitud permanecen explícitos y compatibles dentro de
   cada valor o relación.
8. Una instancia no mezcla especies, segmentos, individuos, escenarios ni tiempos.
9. `x`, `missing_mask`, IDs y atributos tienen el mismo número de nodos; `edge_attr` y los
   metadatos de evidencia tienen el mismo número de aristas que `edge_index`.
10. `edge_index` es `torch.long`, tiene forma `[2, E]`, usa índices locales válidos y supera
    `HeteroData.validate(raise_on_error=True)`.
11. Las salidas apuntan a nodos existentes y diferencian `measured`, `predicted` y
    `synthetic`.
12. Misma versión de generador, configuración y semilla producen el mismo contenido
    determinista.

Las [reglas de integridad del grafo](../graph/graph-integrity-rules.md) (VG-01) detallan estas reglas
con identificador, severidad, evidencia esperada y excepciones admitidas.

El perfil estándar no inventa aristas para alcanzar conectividad total. Un nodo aislado es
preferible a una relación biológica no sustentada. En el dataset sintético, cualquier
relación existe para probar estructura y se etiqueta como tal.

## Decisiones provisionales pendientes de Investigación

| Decisión de §6.1 | Campos o estructuras afectados | Convención temporal | Impacto pendiente |
|---|---|---|---|
| Especie y segmento inicial | `species`, `gut_segment`, nodo `host` | `chicken`, `cecum` | Datasets, ontologías y alcance de generalización. |
| Intervención y dosis registradas | Nodo `additive`, relaciones `modulates`, escenarios | Sustancia/categoría sintética y dosis configurable, sin efecto asumido. | Variable intervenida y comparación válida. |
| Variable objetivo, matriz y unidad | Nodo `metabolite`, `phenotype`, `Salida` | Se permiten IDs sintéticos de AGCC como ejemplos, sin rangos ni matriz confirmados. | Cabezal de predicción e interpretación. |
| Ontología de taxones y rutas | `taxonomy_id`, `taxonomy_level`, `function_id`, `function_type` | Namespace `synthetic:*`. | Vocabularios, features y correspondencia entre fuentes. |
| Criterio de aristas sustentadas/inferidas | Todos los campos `evidence_*` | `evidence_status = synthetic`. | Qué relaciones pueden instanciarse con datos reales. |
| Ecuaciones y tolerancias bioquímicas | Futuro módulo `constraints` | No se definen ni simulan en DS-01. | Restricciones, unidades y pruebas científicas. |
| Partición y validación externa | Metadatos futuros de split | No definida. | Prevención de fuga y protocolo de evaluación. |

Los rangos de abundancia, dosis y concentración también siguen pendientes. DS-02 puede
hacerlos configurables para generar fixtures, pero no debe etiquetarlos como fisiológicos ni
convertirlos en valores por defecto definitivos sin la revisión científica correspondiente.

## Handoff para DS-02 a DS-07

Esta sección coordina integración; no añade campos al contrato.

- Cada tarea trabaja en una rama propia y abre un Pull Request contra `main`. No se deben
  acumular DS-02 a DS-07 en la rama de DS-01.
- Las tareas deben partir del `main` que ya contenga DS-01. Si avanzan en paralelo antes de
  su integración, pueden ramificarse temporalmente desde `docs/ds-01-synthetic-dataset-spec`
  y rebasar su rama sobre `main` después del merge.
- Nombres sugeridos: `feat/ds-02-synthetic-nodes`, `feat/ds-03-synthetic-edges`,
  `feat/ds-04-synthetic-scenarios`, `feat/ds-05-synthetic-export`,
  `test/ds-06-synthetic-generator` y `docs/ds-07-synthetic-usage`.
- DS-02 a DS-05 pertenecen a `src/nutrigraphdt/data/synthetic/`; DS-03 puede depender de
  validadores de `graph`, pero no debe esconder el contrato dentro del modelo. DS-06 ubica
  pruebas unitarias bajo `tests/unit/` y round-trips bajo `tests/integration/`. DS-07 amplía
  documentación y ejemplos solo después de que exista una interfaz ejecutable.
- Una tarea que necesite cambiar un campo o relación actualiza primero esta especificación,
  explica compatibilidad y, si el cambio es incompatible, incrementa `schema_version`.
- Los agentes deben subir código y documentación a sus ramas, no los `.pt`/JSONL generados,
  salvo un fixture mínimo acordado y revisable.

## Referencias técnicas

- [PyTorch Geometric: HeteroData](https://pytorch-geometric.readthedocs.io/en/2.7.0/generated/torch_geometric.data.HeteroData.html)
- [PyTorch Geometric: aprendizaje con grafos heterogéneos](https://pytorch-geometric.readthedocs.io/en/latest/notes/heterogeneous.html)
- [PyTorch: advertencia de seguridad de `torch.load`](https://docs.pytorch.org/docs/stable/generated/torch.load)

### Registro de evidencia técnica

| Pregunta/afirmación | Fuente y alcance | Uso en NutriGraphDT | Limitación | Estado |
|---|---|---|---|---|
| `HeteroData` separa almacenes por tipo de nodo y por tupla de arista, y ofrece `validate()`. | API oficial de PyG 2.7.0. | Define la ubicación de `x`, `edge_index`, metadatos tipados y la validación estructural. | PyG aún no es dependencia del proyecto; DS-03/DS-05 deben volver a comprobar la versión que se adopte. | Provisional |
| Los tipos pueden tener dimensiones de features diferentes. | Guía oficial de grafos heterogéneos de PyG, documentación `latest` consultada el 2026-09-21. | Permite un `F_type` distinto por cada almacén de nodo. | No selecciona arquitectura GNN ni codificación de features. | Aceptado para el contrato |
| Un objeto guardado con `torch.save()` no debe cargarse desde una fuente no confiable. | API oficial estable de `torch.load`, consultada el 2026-09-21. | Limita `.pt` al intercambio confiable y mantiene JSONL como formato auditable. | La estrategia exacta de carga y compatibilidad se implementa y prueba en DS-05. | Aceptado para el contrato |
