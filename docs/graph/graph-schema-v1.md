# Esquema estructural v1 del grafo heterogéneo

## Estado y alcance

El módulo [`nutrigraphdt.graph.schema`](../../src/nutrigraphdt/graph/schema.py) contiene una
versión estructural provisional del esquema, identificada como
`GRAPH_SCHEMA_VERSION = "1.0.0-provisional"`. Sigue la responsabilidad del módulo `graph`
descrita en [architecture.md](../architecture/architecture.md): declarar los esquemas heterogéneos de nodos y
aristas sin esconderlos en el código del modelo.

El líder aprobó avanzar con esta base provisional mientras Investigación entrega el modelo
conceptual y el contrato de datos v1. Esta aprobación permite preparar y probar la estructura;
no equivale a una validación científica ni a la revisión conjunta de Investigación que requiere
el Issue #32.

El módulo usa dataclasses congeladas y `MappingProxyType`. Define los ocho tipos de nodo, sus
atributos obligatorios tal como están enumerados en el contrato sintético, y las once tripletas,
semánticas y estados estructurales actualmente documentados allí. Cada tipo, atributo y relación
conserva su fuente y estado estructural. La versión del grafo es distinta de
`SCHEMA_VERSION` del exportador sintético.

La tabla de atributos, la correspondencia propuesta con fuentes y el diagrama del esquema están
en el [diccionario de datos del grafo](graph-data-dictionary.md).

La lista de atributos y sus tipos de intercambio es provisional: el contrato sintético declara
que los atributos de dominio deben confirmarse con Investigación. Las unidades no se fijan como
valores por defecto: los atributos cuantitativos apuntan al campo que porta su unidad
(`dose_unit`, `abundance_unit`, `unit` o el campo unitario de cada elemento de `composition`).
Un puntero describe dónde declara la unidad el registro; no selecciona ni convierte esa unidad.

## Correspondencia de nombres

| Nombre en el Esquema General v3.1 | Identificador en código |
|---|---|
| Dieta | `diet` |
| Aditivo | `additive` |
| Sustrato | `substrate` |
| Taxón / gremio | `taxon` |
| Función / ruta | `function` |
| Metabolito | `metabolite` |
| Huésped | `host` |
| Fenotipo | `phenotype` |

## Tripletas permitidas y estado estructural

Los estados se copian sin traducir de `structural_status` en
`nutrigraphdt.data.synthetic.edges.ALLOWED_RELATIONS`.

| Tripleta `(origen, relación, destino)` | Semántica | Estado estructural |
|---|---|---|
| (`diet`, `provides`, `substrate`) | Composición documentada de dieta. | `approved_structure` |
| (`substrate`, `available_to`, `taxon`) | Recurso potencialmente disponible. | `provisional` |
| (`taxon`, `has_capacity`, `function`) | Capacidad anotada, no actividad demostrada. | `provisional` |
| (`function`, `produces`, `metabolite`) | Transformación candidata. | `provisional` |
| (`metabolite`, `measured_in`, `host`) | Medición o exposición contextual. | `provisional` |
| (`additive`, `modulates`, `taxon`) | Hipótesis de modulación. | `hypothetical` |
| (`additive`, `modulates`, `function`) | Hipótesis de modulación. | `hypothetical` |
| (`metabolite`, `associated_with`, `phenotype`) | Asociación, no efecto causal. | `hypothetical` |
| (`host`, `exhibits`, `phenotype`) | Correspondencia observacional. | `provisional` |
| (`taxon`, `interacts_with`, `taxon`) | Interacción ecológica candidata. | `hypothetical` |
| (`function`, `cross_feeds`, `function`) | Sustrato cruzado candidato entre funciones. | `hypothetical` |

`approved_structure` describe el estado estructural que registra el contrato sintético para esa
tripleta; no afirma que exista evidencia biológica en una instancia real. El Esquema General
indica que las aristas de ejemplo requieren evidencia y prohíbe inferir `taxon → metabolite` por
mera coocurrencia.

## Diferencias existentes y decisiones pendientes

Este primer cambio solo declara el esquema central y verifica las definiciones actuales. No
modifica los generadores sintéticos, validadores, `heterodata.py` ni `data/schema.py`; su
integración se reserva para un segundo PR.

| Diferencia | Estado registrado | Pendiente |
|---|---|---|
| `data.schema.ALLOWED_RELATION_TYPES` admite `consumes`, `ferments`, `affects`, `targets` y `participates_in`, sin una tripleta correspondiente en el catálogo sintético actual. | El vocabulario tabular contiene nombres de relación genéricos; no equivale a una tripleta permitida por el esquema del grafo. | Investigación y Desarrollo deben acordar el vocabulario de relaciones y la correspondencia entre capas antes de integrar los contratos. |
| El vocabulario de unidades de `data/schema.py` incluye `g_kg`; los ejemplos del diccionario del dataset sintético (`synthetic-dataset-dictionary.md`) usan `g/kg`. | Notaciones existentes discrepantes; no se normalizan ni se elige una representación en este PR. | Acordar representación canónica y conversiones, si correspondieran, con Investigación. |
| `data.schema.ALLOWED_EVIDENCE_STATUSES` incluye `experimental` y `literature`, que no aparecen en `data.synthetic.edges.EVIDENCE_STATUSES`. | Los conjuntos de estados difieren; este módulo no consolida ni autoriza estados de evidencia. | Investigación debe definir criterios de evidencia y estados admitidos antes de validar o instanciar relaciones reales. |

## Decisiones científicas abiertas con Investigación

El Esquema General v3.1, §6.1, señala que deben cerrarse con Investigación:

- especie y segmento inicial;
- intervención y dosis que realmente se registran;
- variable objetivo, matriz y unidad;
- ontología concreta de taxones y rutas;
- criterio para distinguir aristas sustentadas e inferidas;
- ecuaciones y tolerancias bioquímicas;
- partición y conjunto de validación externa.

La Figura 1 y sus tablas son una plantilla de diseño, no confirmación de relaciones biológicas
concretas. Los nombres, atributos y estados estructurales de esta versión no sustituyen el
modelo conceptual ni el contrato de datos v1 pendientes de Investigación. Las unidades,
magnitudes, vocabularios y relaciones que el contrato sintético marca como provisionales siguen
sujetos a esa revisión.
