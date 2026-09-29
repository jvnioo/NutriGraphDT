# Reglas de integridad del grafo

- **Tarea:** VG-01 — Definir las reglas de integridad del grafo (#11).
- **Versión de las reglas:** `1.0.0`, aplicable al contrato `schema_version = 1.0.0`.
- **Estado:** especificación canónica para VG-02 a VG-07. Este documento define reglas; no
  implementa validadores.

Esta especificación establece cuándo un grafo heterogéneo de NutriGraphDT es
**computacionalmente íntegro**, qué hallazgos bloquean su uso y qué excepciones se admiten.
Deriva del [contrato del dataset sintético](synthetic-dataset-spec.md) (DS-01), de la
[arquitectura](architecture.md) y de la sección 6 del
[Esquema General](Esquema_General_del_proyecto_Microbioma_Digital.md) ("Integridad del grafo").

Si este documento y el contrato DS-01 difieren, prevalece el contrato. Una regla nueva o un
cambio de severidad requiere actualizar este documento e incrementar su versión.

## Integridad computacional frente a validez biológica

Un grafo que cumple todas las reglas es **estructuralmente coherente con el contrato**: sus
identificadores resuelven, sus relaciones están permitidas, sus unidades y matrices no se
mezclan y sus tensores son consumibles por un modelo. **Nada de eso afirma que el grafo sea
biológicamente correcto.**

| Estas reglas verifican | Estas reglas **no** verifican |
|---|---|
| Que cada arista apunte a nodos existentes del tipo declarado. | Que la relación exista en el organismo. |
| Que cada magnitud tenga unidad y valor finito. | Que el valor esté en un rango fisiológico. |
| Que la evidencia esté declarada con un estado permitido. | Que la evidencia sea suficiente o de calidad. |
| Que una instancia no mezcle especies, segmentos ni tiempos. | Que la especie o el segmento elegido sea adecuado. |
| Que los escenarios comparables compartan estructura. | Que una diferencia entre escenarios sea causal. |

Ninguna regla usa umbrales biológicos. Las reglas que dependen de una decisión aún abierta en
la sección 6.1 del Esquema General se marcan como **provisionales (P)**. Cuando Investigación
cierre esa decisión, deben revisarse.

## Severidades

| Severidad | Significado | Efecto en el pipeline (lo implementa VG-07) |
|---|---|---|
| `ERROR` | Se incumple el contrato o la integridad computacional. El grafo podría interpretarse mal o fallar en el modelo. | El grafo **no** se entrega al modelo. |
| `ADVERTENCIA` | El grafo es utilizable, pero presenta una condición que el contrato admite y que puede afectar la interpretación. | El grafo se entrega. El hallazgo queda en el reporte y requiere revisión humana. |
| `INFO` | Una excepción admitida explícitamente por este documento. | El grafo se entrega. El hallazgo solo se registra y se cuenta. |

Criterio general: es `ERROR` lo que rompe la trazabilidad o la consumibilidad del grafo; es
`ADVERTENCIA` lo que el contrato permite, pero conviene revisar; es `INFO` lo que el propio
diseño produce de forma esperada.

Los validadores deben informar **todos** los hallazgos de un grafo, no solo el primero. Un
`ERROR` en una regla no suprime la evaluación de las demás, salvo cuando la regla dependiente
no puede evaluarse (por ejemplo, las reglas de atributos de un nodo cuyo tipo es desconocido).

## Estructura de un hallazgo

Cada regla produce hallazgos con esta información mínima, que VG-07 consolida en el reporte:

| Campo | Contenido |
|---|---|
| `rule_id` | Identificador estable de la regla, por ejemplo `EDG-02`. |
| `severity` | `ERROR`, `ADVERTENCIA` o `INFO`. |
| `graph_id` | Instancia afectada; en las reglas de pares (INS-05, INS-06), la instancia `intervention`, con ambas instancias identificadas en `location`; `null` si el hallazgo es de nivel dataset. |
| `location` | Ubicación exacta: tipo y `node_id` del nodo; tupla, `source_id`, `target_id` o columna de la arista; nombre y dimensión del tensor; o campo de metadatos. |
| `expected` | Lo que exige la regla. |
| `observed` | Lo que se encontró. |
| `message` | Descripción legible. |

La columna **Evidencia** de cada tabla indica qué debe contener `location` y `observed` para
que el hallazgo sea verificable, y qué defecto debe fabricar VG-06 para probar la regla.

## Alcance y orden de evaluación

Las reglas se aplican sobre dos representaciones del mismo grafo:

1. **Registros** (`Node`, `Edge`, `InstanceRecord`, `OutputRecord` y `metadata.json`), antes
   de construir tensores. Reglas `INS`, `NOD`, `EDG`, `OUT`, `MET` y `CON`.
2. **Tensores** (`HeteroData`), después de la conversión. Reglas `TEN`.

Orden recomendado: registros → conversión → tensores → `HeteroData.validate()`. Un `ERROR` de
nivel registro impide la conversión, porque produciría índices o features sin significado.

---

## Reglas de instancia (`INS`)

Alcance: INS-01 a INS-04 se aplican a cada registro de `instances.jsonl` y a la relación de
sus nodos con él. INS-05 e INS-06 se aplican a **pares de instancias** que comparten
`sample_id`.

| ID | Regla | Severidad | Evidencia | Origen |
|---|---|---|---|---|
| INS-01 | `graph_id` es único en el dataset, y todos los campos obligatorios de la instancia existen con su tipo. Solo `timepoint` puede ser `null`. | ERROR | `graph_id` repetido o campo faltante; valor observado. | DS-01, contrato de instancia |
| INS-02 | `schema_version` es compatible (`1.0.0`) e `is_synthetic` es booleano. DS-01 exige `true` para el dataset sintético; las reglas admiten `false` para datos reales futuros, que igualmente quedan bloqueados por EDG-04 mientras no exista un criterio de evidencia. | ERROR | Valor observado. | DS-01, regla 1 |
| INS-03 | `scenario_id` pertenece a `{basal, intervention}`. | ERROR | Valor observado. | DS-01, contrato de instancia |
| INS-04 | Los nodos `host` de una instancia declaran la misma `species` y el mismo `gut_segment` que la instancia. | ERROR | `node_id` del host; valor de instancia frente a valor del nodo. | DS-01, regla 8; Esquema §6 |
| INS-05 | Dos instancias con el mismo `sample_id` (escenarios comparables) tienen la misma estructura: mismos tipos, mismos `node_id` por tipo y mismas claves de atributos. | ERROR | `sample_id`, tipo y diferencia de conjuntos de IDs o claves. | Esquema §5 y §6 ("Escenarios") |
| INS-06 **(P)** | En escenarios comparables, solo difieren los valores de la variable declarada en `diet_treatment`. Cualquier otro atributo con valor distinto se informa. | ADVERTENCIA | Nodo, atributo, valor basal y valor intervenido. | Esquema §6 ("la intervención altera exclusivamente entradas seleccionadas") |

**Por qué INS-05 es error y INS-06 advertencia.** Si la estructura difiere, la comparación
basal/intervención no está definida y el grafo no sirve para el escenario. Si solo difieren
valores fuera de la intervención, la estructura sigue siendo válida, pero la comparación
queda confundida. Hoy es advertencia porque el mecanismo formal para declarar variables
intervenidas aún no existe (§6.1-ii). Nota: los escenarios sintéticos actuales disparan
INS-06, porque sus valores aleatorios dependen de `graph_id` (ver
[guía de uso](synthetic-dataset-usage.md#limitaciones)). El hallazgo es correcto y debe
aparecer en el reporte.

## Reglas de nodo (`NOD`)

Alcance: cada registro de `nodes.jsonl` y su almacén `data[node_type]`.

| ID | Regla | Severidad | Evidencia | Origen |
|---|---|---|---|---|
| NOD-01 | `node_type` es uno de los ocho tipos del contrato. Las reglas NOD-05 a NOD-11 no se evalúan sobre nodos de tipo desconocido. | ERROR | `node_id` y tipo observado. | DS-01, tipos de nodo |
| NOD-02 | `graph_id`, `node_id` y `source_id` son cadenas no vacías, y `graph_id` corresponde a una instancia existente. | ERROR | Campo y valor observado. | DS-01, ausencia de datos |
| NOD-03 | `node_id` es único dentro de `(graph_id, node_type)`. | ERROR | Tipo, `node_id` repetido y número de apariciones. | DS-01, regla 4 |
| NOD-04 | En una instancia sintética (`is_synthetic = true`), `node_id` y los identificadores de dominio (`chemical_id`, `taxonomy_id`, `function_id`) usan el prefijo `synthetic:`. | ERROR | Campo y valor observado. | DS-01, tipos de intercambio |
| NOD-05 | `attributes` es un objeto que contiene todos los atributos obligatorios del tipo, cada uno con su tipo JSON. Los números son finitos y un booleano no cuenta como número. | ERROR | Nodo, atributo, tipo esperado y valor observado. | DS-01, regla 3 |
| NOD-06 | Cada elemento de `diet.composition` tiene `component_id: str`, `value: number` finito y `unit: str` no vacía. | ERROR | Nodo, posición del elemento y campo faltante. | DS-01, tipos de nodo |
| NOD-07 | `missing_mask` es coherente con `attributes`: sus claves son atributos existentes y sus valores booleanos. Un valor `null` tiene máscara `true`, y una máscara `true` corresponde a un valor `null`. | ERROR | Nodo, atributo, valor y máscara observados. | DS-01, ausencia de datos |
| NOD-08 | Hay atributos marcados como ausentes. El contrato los admite, pero afectan las features. | ADVERTENCIA | Conteo de ausencias por tipo y atributo. | DS-01, ausencia de datos |
| NOD-09 | `attributes` contiene claves que no están en el contrato del tipo. | ADVERTENCIA | Nodo y claves adicionales. | DS-01 (cambios de contrato requieren versión) |
| NOD-10 **(P)** | Las magnitudes que físicamente no pueden ser negativas (`quantity`, `abundance`, `concentration`, `dose`, `annotation_value`, `covariates.body_weight_g`) son `>= 0`. | ADVERTENCIA | Nodo, atributo y valor. | Esquema §4.2 (no negatividad) |
| NOD-11 **(P)** | `function_type` y `annotation_value_type` pertenecen a los vocabularios declarados en `metadata.json`. | ADVERTENCIA | Campo, valor y vocabulario declarado. | DS-01, vocabularios provisionales |
| NOD-12 **(P)** | La instancia contiene al menos un nodo de cada uno de los ocho tipos. | ERROR si `is_synthetic = true`; ADVERTENCIA si no. | Tipos ausentes. | DS-01, regla 2; Esquema §5.2 |

**Por qué NOD-04 es error.** Es la barrera que impide presentar un registro artificial como
una accesión real. El contrato lo exige ("no deben parecer accesiones reales").

**Por qué NOD-10 es advertencia provisional y no error.** La no negatividad es una propiedad
física, no un umbral biológico. Pero una transformación ya aplicada sobre el valor crudo
(logaritmo o CLR) produce negativos legítimos, y el vocabulario de unidades todavía no está
aprobado. Pasará a error cuando las unidades se fijen.

**Por qué NOD-12 depende del origen.** El perfil sintético estándar debe tener los ocho tipos.
En cambio, un dataset real puede no tener, por ejemplo, fenotipo emparejado (el Esquema §5.2
lo anticipa para cerdo). Exigirlo como error rechazaría datos reales válidos.

No se define ninguna regla de suma de abundancias relativas (≈ 1). Un grafo puede contener
solo un subconjunto de taxones, así que la suma no es un invariante del contrato.

## Reglas de arista (`EDG`)

Alcance: cada registro de `edges.jsonl` y su almacén `data[src, rel, dst]`. Todas las
relaciones son **dirigidas**: la dirección la fija la tupla, y una tupla invertida es una
relación distinta.

| ID | Regla | Severidad | Evidencia | Origen |
|---|---|---|---|---|
| EDG-01 | La tupla `(source_type, relation_type, target_type)` es una de las once permitidas. No se admiten inversas implícitas ni `taxon -> metabolite`. | ERROR | Índice o identificación de la arista y tupla observada. | DS-01, regla 5 |
| EDG-02 | `source_id` y `target_id` existen como nodos del tipo declarado **en el mismo `graph_id`**. Esto también prohíbe aristas entre instancias. | ERROR | Arista y extremo inexistente. | DS-01, regla 5; Esquema §6 |
| EDG-03 | Los campos comunes son cadenas no vacías, y `evidence_status` pertenece a `{synthetic, observed, annotated, inferred, hypothetical}`. | ERROR | Campo y valor observado. | DS-01, contrato de arista |
| EDG-04 **(P)** | `evidence_status = "synthetic"` en toda arista, mientras Investigación no apruebe criterios de evidencia. | ERROR | Arista y estado observado. | DS-01, regla 6; §6.1-v |
| EDG-05 | Los atributos obligatorios de la relación existen con su tipo. | ERROR | Arista, atributo, tipo esperado y valor. | DS-01, relaciones permitidas |
| EDG-06 | En `cross_feeds`, `substrate_id` identifica un nodo `substrate` de la misma instancia. | ERROR | Arista y `substrate_id`. | DS-01, relaciones permitidas |
| EDG-07 | Los atributos de arista que describen una magnitud del nodo coinciden con él: `sample_matrix` de `measured_in` con la del metabolito, `unit` de `provides` con la del sustrato, y `timepoint` de `exhibits` con el del fenotipo. | ERROR | Arista, atributo, valor en la arista y valor en el nodo. | DS-01, reglas 7 y 8 |
| EDG-08 | `annotation_source` de `has_capacity` difiere del `annotation_source` de la función destino. | ADVERTENCIA | Arista y ambos valores. | DS-01, relaciones permitidas |
| EDG-09 | Hay dos aristas idénticas: misma tupla, extremos y `evidence_id`. | ERROR | Tupla, extremos y número de repeticiones. | Integridad computacional |
| EDG-10 | Hay dos aristas con la misma tupla y los mismos extremos, pero distinto `evidence_id`. | ADVERTENCIA | Tupla, extremos y `evidence_id` involucrados. | Integridad computacional |
| EDG-11 | Hay un autolazo (`source_id = target_id`) en `interacts_with` o `cross_feeds`. | ADVERTENCIA | Arista. | Integridad computacional |
| EDG-12 **(P)** | `interaction_type` de `interacts_with` pertenece al vocabulario declarado en `metadata.json`. | ADVERTENCIA | Arista, valor y vocabulario declarado. | DS-01, vocabularios provisionales |

**Por qué EDG-04 es provisional.** Refleja una decisión temporal de DS-01. Cuando exista un
criterio de evidencia aprobado, se reemplaza por reglas sobre `observed`, `annotated`, etc.
Hasta entonces, cualquier otro estado equivaldría a declarar una evidencia inexistente.

**Por qué EDG-07 es error.** Una arista `measured_in` con una matriz distinta de la del
metabolito mezcla matrices, y una `exhibits` con otro tiempo mezcla tiempos. Ambas cosas
están prohibidas por el contrato, no son una preferencia. En cambio, EDG-08 es advertencia:
con datos reales, la capacidad de un taxón puede anotarse con otra fuente que la de la
función.

**Por qué EDG-09 es error y EDG-10 advertencia.** Una arista duplicada exacta duplica el paso
de mensajes en la GNN sin aportar información: es un defecto. Dos aristas con distinta
procedencia sobre el mismo par pueden ser legítimas (dos fuentes que respaldan la misma
relación). Cómo agregarlas es una decisión pendiente, así que se informan.

**Por qué los autolazos son advertencia.** El generador no los produce, y en `cross_feeds`
carecen de sentido operativo. Pero una interacción de un taxón consigo mismo (competencia
intraespecífica) no es incoherente con el contrato. Rechazarla sería una decisión biológica.

## Reglas de conectividad (`CON`)

Alcance: el grafo de cada instancia, tratando las aristas como **no dirigidas** para calcular
grado y componentes. Estas reglas **nunca** modifican el grafo: no eliminan ni conectan nodos.

| ID | Regla | Severidad | Evidencia | Origen |
|---|---|---|---|---|
| CON-01 | Un nodo tiene grado 0 (nodo aislado o huérfano), salvo que corresponda a una excepción de la tabla siguiente. | ADVERTENCIA | Conteo por tipo y lista de `node_id`. | DS-01, reglas de validación |
| CON-02 | Un nodo aislado corresponde a una excepción admitida. | INFO | Conteo por tipo, `node_id` y excepción aplicada. | Este documento |
| CON-03 | Un tipo de nodo tiene nodos, pero ninguna arista lo referencia en la instancia. | ADVERTENCIA | Tipo y número de nodos. | `HeteroData.validate()` (lo advierte sin fallar) |
| CON-04 | La instancia tiene más de un componente conexo con dos o más nodos. | ADVERTENCIA | Número de componentes y composición de cada uno (conteo por tipo). | DS-01 (no se fuerza conectividad) |

**Ninguna condición de conectividad es `ERROR`.** DS-01 establece que "un nodo aislado es
preferible a una relación biológica no sustentada" y que el generador no inventa aristas
para alcanzar conectividad total. Exigir conexión obligaría a fabricar relaciones.

### Excepciones admitidas para nodos aislados

| Excepción | Condición | Justificación |
|---|---|---|
| X-01 | Nodo `additive` cuyo `control_label` pertenece a `non_modulating_control_labels` (por defecto `control_basal`). | Un control no modula por diseño: el generador no le crea aristas `modulates`, y ninguna otra relación sale de un aditivo. Su aislamiento es el comportamiento esperado. |

Cualquier otra excepción debe agregarse a esta tabla con su justificación. No se admiten
excepciones implícitas en el código de VG-04.

### Excepciones admitidas para componentes desconectados

**Ninguna.** La desconexión ya está admitida, porque CON-04 es una advertencia y no un error.
Una excepción adicional la volvería invisible en el reporte, y hoy no hay un criterio que
distinga un componente esperado de uno anómalo. Todos los componentes se informan con su
composición para que la revisión humana decida. Un nodo aislado es un componente de tamaño 1
y se evalúa solo con CON-01 y CON-02, no con CON-04. Queda pendiente (P) una
regla más específica: marcar los componentes sin nodos del tipo objetivo, que no pueden
influir en la predicción por paso de mensajes. Depende de la variable objetivo (§6.1-iii).

## Reglas de salida (`OUT`)

Alcance: registros de `outputs.jsonl` y, cuando exista, `data.output_records` y `data[t].y`.

| ID | Regla | Severidad | Evidencia | Origen |
|---|---|---|---|---|
| OUT-01 | `target_id` existe como nodo de `target_type` en la misma instancia. | ERROR | Salida y nodo inexistente. | DS-01, regla 11 |
| OUT-02 | `measured_or_predicted` pertenece a `{measured, predicted, synthetic}`. `model_version` es obligatorio solo para `predicted` y `null` en los demás casos. | ERROR | Salida y valores observados. | DS-01, contrato de salida |
| OUT-03 | En una instancia sintética, ninguna salida es `measured`. | ERROR | Salida. | DS-01 ("un target artificial usa synthetic, nunca measured") |
| OUT-04 | `unit` y `sample_matrix` son cadenas no vacías, y `value` es finito. | ERROR | Salida, campo y valor. | DS-01, contrato de salida |

## Reglas de metadatos (`MET`)

Alcance: `metadata.json` de un dataset exportado.

| ID | Regla | Severidad | Evidencia | Origen |
|---|---|---|---|---|
| MET-01 | Existen los campos mínimos, `schema_version` es compatible y `random_seed` es entero. | ERROR | Campo faltante o valor observado. | DS-01, metadatos |
| MET-02 | `is_synthetic` del dataset coincide con el de todas sus instancias. | ERROR | `graph_id` discordantes. | DS-01, regla 1 |
| MET-03 | `counts` coincide con los nodos, aristas y salidas realmente presentes por instancia. | ERROR | Instancia, tipo o relación, valor declarado y valor real. | DS-01, metadatos |

**Por qué MET-03 es error.** Una discrepancia significa que los archivos se editaron o
quedaron incompletos después de exportar. Esa evidencia de corrupción no debe pasar al
modelo.

## Reglas de tensores (`TEN`)

Alcance: el objeto `HeteroData` construido a partir de una instancia válida (Actividad 3.3),
según la correspondencia de DS-01. La columna **PyG** indica si `HeteroData.validate()` de
PyTorch Geometric 2.7.0 ya comprueba la regla.

| ID | Regla | Severidad | PyG | Evidencia |
|---|---|---|---|---|
| TEN-01 | Todo tipo de nodo referenciado por una relación existe como almacén de nodos. | ERROR | Sí | Tupla y tipo faltante. |
| TEN-02 | `num_nodes` está definido en cada tipo de nodo usado por una relación. | ERROR | Sí | Tipo de nodo. |
| TEN-03 | `edge_index` tiene forma `[2, E]`. | ERROR | Sí | Tupla y forma observada. |
| TEN-04 | Los índices de `edge_index` son `>= 0`, los de origen `< N_src` y los de destino `< N_dst`. | ERROR | Sí | Tupla, fila, índice y límite. |
| TEN-05 | `edge_index` es `torch.long`. | ERROR | **No** | Tupla y `dtype` observado. |
| TEN-06 | `x` es un tensor de punto flotante, de forma `[N_type, F_type]`, con `F_type` igual al número de columnas declaradas en `node_feature_schema[node_type]`. | ERROR | **No** | Tipo, forma, `dtype` y columnas declaradas. |
| TEN-07 | `missing_mask` es booleano y tiene la misma forma que `x`. | ERROR | **No** | Tipo y formas. |
| TEN-08 | `node_id`, `source_id` y `raw_attributes` tienen `N_type` elementos, y `node_id` no tiene repetidos. | ERROR | **No** | Tipo y longitudes. |
| TEN-09 | `edge_attr` es de punto flotante con forma `[E, A_type]`, con `A_type` igual a las columnas de `edge_feature_schema`. Una relación sin features usa `[E, 0]`. `evidence_id`, `evidence_status`, `evidence_method` y `raw_attributes` tienen `E` elementos. | ERROR | **No** | Tupla, forma y longitudes. |
| TEN-10 | `x`, `edge_attr` e `y` no contienen `NaN` ni infinitos, incluidas las posiciones enmascaradas. | ERROR | **No** | Tensor, tipo o tupla, y número y posición de los valores no finitos. |
| TEN-11 | Para cada columna `k`, `node_id[edge_index[0, k]]` y `node_id[edge_index[1, k]]` coinciden con los extremos del registro de arista correspondiente. | ERROR | **No** | Tupla, columna e IDs esperados y observados. |
| TEN-12 | Los atributos globales (`graph_id`, `species`, `gut_segment`, …) coinciden con el registro de instancia. | ERROR | **No** | Atributo y ambos valores. |

**Uso de `HeteroData.validate()`.** El contrato DS-01 exige terminar la conversión con
`data.validate(raise_on_error=True)`. Esa llamada se mantiene como **comprobación de base
final**, pero no sustituye estas reglas, por dos motivos:

1. **Cubre poco.** Solo verifica TEN-01 a TEN-04. No revisa `dtype`, forma de `x` o
   `edge_attr`, valores no finitos, IDs, evidencia ni unidades.
2. **Se detiene en el primer error.** Con `raise_on_error=True` lanza una excepción con el
   primer defecto. Un reporte completo requiere que el proyecto evalúe TEN-01 a TEN-04 por
   su cuenta.

Además, PyG solo *advierte* sobre tipos de nodo sin aristas, y esa condición ya está en
CON-03. Fuente: método `HeteroData.validate` en
[`torch_geometric/data/hetero_data.py`, versión 2.7.0](https://github.com/pyg-team/pytorch_geometric/blob/2.7.0/torch_geometric/data/hetero_data.py).

**TEN-06 y TEN-09 frente a la codificación de features.** DS-01 no aprueba todavía ninguna
codificación, y el exportador actual declara `node_feature_schema` y `edge_feature_schema`
vacíos. La regla no es provisional; lo pendiente es el esquema de features que la alimenta.
Un tensor cuyas columnas no están declaradas es `ERROR`, porque DS-01 prohíbe inferir el orden
de las columnas. Por eso el constructor de `HeteroData` (Actividad 3.3) debe declarar ese
esquema en los metadatos antes de que VG-05 pueda aceptar un grafo.

**Por qué TEN-10 incluye las posiciones enmascaradas.** Un `NaN` en una posición marcada como
ausente también se propaga en las operaciones de la GNN (por ejemplo, al multiplicar por
cero). El valor ausente se representa con la máscara, no con `NaN`.

**Por qué TEN-11 existe.** Las otras reglas pueden cumplirse aunque la conversión haya
asignado los índices a los nodos equivocados. TEN-11 es la única que comprueba que el
significado de cada arista sobrevive a la conversión.

## Correspondencia con las reglas de validación de DS-01

| Regla DS-01 | Reglas de este documento |
|---|---|
| 1. `schema_version` compatible e `is_synthetic` | INS-02, MET-01, MET-02 |
| 2. Ocho tipos de nodo presentes | NOD-12 |
| 3. Campos obligatorios, tipos y números finitos | INS-01, NOD-02, NOD-05, NOD-06, EDG-03, EDG-05, OUT-04 |
| 4. IDs únicos | INS-01, NOD-03, TEN-08 |
| 5. Tuplas permitidas y extremos existentes | EDG-01, EDG-02, EDG-06 |
| 6. Evidencia sintética declarada | EDG-04 |
| 7. Unidad y matriz explícitas y compatibles | NOD-05, NOD-06, EDG-07, OUT-04 |
| 8. Sin mezcla de especies, segmentos, individuos, escenarios o tiempos | INS-04, EDG-02, EDG-07 |
| 9. Alineación de `x`, máscara, IDs y metadatos de arista | TEN-06, TEN-07, TEN-08, TEN-09 |
| 10. `edge_index` long, `[2, E]`, índices válidos y `validate()` | TEN-01 a TEN-05 |
| 11. Salidas apuntan a nodos y distinguen su origen | OUT-01, OUT-02, OUT-03 |
| 12. Determinismo | Fuera de alcance: se prueba en DS-05/DS-06, no en un grafo individual. |

## Asignación a tareas

| Tarea | Reglas que implementa |
|---|---|
| VG-02 — nodos | NOD-01 a NOD-12, INS-01 a INS-04 |
| VG-03 — aristas | EDG-01 a EDG-12 |
| VG-04 — conectividad | CON-01 a CON-04 y la excepción X-01 |
| VG-05 — tensores | TEN-01 a TEN-12 |
| VG-06 — casos defectuosos | Al menos un caso negativo por regla y un grafo válido sin hallazgos `ERROR` |
| VG-07 — integración | Estructura de hallazgo, severidades, efecto en el pipeline, INS-05, INS-06, OUT-01 a OUT-04 y MET-01 a MET-03 |

Las reglas de instancia, salida y metadatos que involucran varias instancias o el dataset
completo se asignan a VG-07, porque las tareas VG-02 a VG-05 validan una instancia. Esta
asignación es una propuesta. Si al refinar VG-07 resulta que implementar esas reglas excede
su alcance de integración, deben moverse a un Issue propio en lugar de ampliar VG-07 sin
registro.

### Comprobaciones ya existentes

`nutrigraphdt.data.synthetic` ya implementa parte de estas reglas a nivel de registro. Sus
mensajes son texto libre, sin `rule_id` ni severidad, así que no sustituyen a los
validadores. Sirven como referencia y deben mantenerse coherentes con ellos:

| Función | Reglas cubiertas total o parcialmente |
|---|---|
| `find_edge_errors` (`edges.py`) | EDG-01, EDG-02, EDG-03, EDG-04, EDG-05, EDG-06 |
| `find_dataset_errors` (`export.py`) | INS-01 (unicidad de `graph_id`), INS-02, INS-03, NOD-01, NOD-02 (instancia existente), NOD-03, MET-01, OUT-01, OUT-02 |

Estas funciones no cubren NOD-04 a NOD-12, EDG-07 a EDG-12, INS-04 a INS-06, OUT-03,
OUT-04, MET-02, MET-03 ni las reglas `CON` y `TEN`. Las reglas `NOD` e INS-01 a INS-04 las
implementa el validador de VG-02; las reglas `EDG`, el de VG-03, y las reglas `CON`, el de VG-04
(sección siguiente).

### Validadores implementados

Estos validadores producen hallazgos con la estructura de este documento
(`nutrigraphdt.graph.validation.Finding`). No modifican el grafo.

| Tarea | Función | Reglas |
|---|---|---|
| VG-02 | `find_node_findings(instances, nodes, metadata=...)` (`graph/validation/nodes.py`) | NOD-01 a NOD-12, INS-01 a INS-04 |
| VG-03 | `find_edge_findings(nodes, edges, metadata=...)` (`graph/validation/edges.py`) | EDG-01 a EDG-12 |
| VG-04 | `find_connectivity_findings(nodes, edges, metadata=...)` (`graph/validation/connectivity.py`) | CON-01 a CON-04, excepción X-01 |

VG-02 aplica estos criterios, que precisan las reglas sin cambiarlas:

- NOD-05: un atributo obligatorio de tipo `str`, y cada elemento de `ingredients`, es una
  cadena no vacía, porque DS-01 prohíbe representar un valor ausente con una cadena vacía. Un
  valor `null` no incumple NOD-05: es un valor ausente, que se evalúa con NOD-07 y NOD-08.
- NOD-07: las claves de `missing_mask` son rutas relativas a `attributes`. Una ruta con puntos,
  como `covariates.sex`, recorre objetos anidados.
- INS-01 comprueba que `schema_version` e `is_synthetic` existan, e INS-02 evalúa su valor, para
  no informar dos veces el mismo defecto.
- NOD-04 se evalúa solo en nodos de una instancia existente con `is_synthetic = true`. NOD-12
  trata como no sintética cualquier instancia cuyo `is_synthetic` no sea `true`.
- NOD-11 se evalúa solo si se entregan los metadatos del dataset. Un vocabulario que no está
  declarado en ellos se trata como vacío.

VG-03 aplica estos criterios, que precisan las reglas sin cambiarlas:

- EDG-01 se evalúa solo si los tres tipos de la tupla son cadenas no vacías; si no, EDG-03
  informa el campo. Una tupla que invierte una relación permitida se informa como tal.
- EDG-02 se evalúa aunque la tupla no esté permitida, salvo en un extremo cuyo tipo no es uno de
  los ocho del contrato, porque ese defecto ya lo informa EDG-01. Un extremo que solo existe en
  otra instancia no resuelve, y el hallazgo indica en qué instancias existe.
- EDG-03 también informa una arista que no es un objeto. EDG-04 se evalúa solo si
  `evidence_status` es un estado permitido, para no informar dos veces un estado desconocido.
- EDG-05 exige que `attributes` sea un objeto, como NOD-05 en los nodos. Los atributos
  obligatorios se evalúan solo en tuplas permitidas y con el criterio de NOD-05 (cadena no vacía,
  número finito no booleano). Las aristas no tienen `missing_mask`, así que un `null` en un
  atributo obligatorio incumple EDG-05. Los atributos adicionales no se informan: VG-01 no define
  una regla equivalente a NOD-09 para aristas.
- EDG-06, EDG-07, EDG-08 y EDG-12 comparan solo valores que EDG-05 aceptó. EDG-07 y EDG-08
  además requieren que el nodo exista una sola vez en la instancia (si se repite, NOD-03 informa
  el defecto y la comparación sería ambigua) y que su valor sea una cadena no vacía (un valor
  ausente lo evalúan NOD-07 y NOD-08).
- EDG-09 y EDG-10 agrupan las aristas por instancia, tupla y extremos, aunque la tupla no esté
  permitida. Las aristas de sentido opuesto no son repetidas, porque todas las relaciones son
  dirigidas.
- EDG-11 compara `source_id` y `target_id` solo en `interacts_with` y `cross_feeds`, donde ambos
  extremos son del mismo tipo. En las demás relaciones, dos nodos de distinto tipo pueden
  compartir `node_id` sin formar un autolazo.
- EDG-12 se evalúa solo si se entregan los metadatos del dataset. Un vocabulario que no está
  declarado en ellos se trata como vacío.

VG-04 aplica estos criterios, que precisan las reglas sin cambiarlas:

- Un nodo es cada `(graph_id, node_type, node_id)` con los tres campos como cadenas no vacías; un
  `node_id` repetido (NOD-03) cuenta una vez. Solo conectan las aristas cuyos dos extremos
  existen en la misma instancia: una arista con un extremo inexistente (EDG-02) no une nada.
- CON-01 considera aislado un nodo sin aristas hacia **otro** nodo: su grado se calcula sin
  autolazos. Así coincide con la definición de esta especificación, según la cual un nodo aislado
  es un componente de tamaño 1. El autolazo lo informa EDG-11.
- X-01 lee `non_modulating_control_labels` de `configuration.edges` en `metadata.json`, donde
  DS-05 exporta la configuración del generador. Si no está declarada, usa el valor por defecto
  del generador (`control_basal`). La excepción solo existe en la tabla
  `ISOLATED_NODE_EXCEPTIONS`; una nueva excepción requiere actualizar primero este documento.
- CON-03 no tiene excepciones: un tipo cuyos únicos nodos son aditivos de control aislados
  produce CON-02 y CON-03. Un autolazo cuenta como referencia al tipo.
- CON-04 describe cada componente con su tamaño, su conteo por tipo y la lista de sus nodos, para
  que la revisión humana pueda ubicarlos. Los hallazgos no dependen del orden de los registros.

## Reglas provisionales y decisiones pendientes

| Regla | Decisión pendiente (Esquema §6.1) | Cambio esperado cuando se resuelva |
|---|---|---|
| INS-06 | (ii) Intervención y dosis registradas | Pasar a `ERROR` cuando exista una declaración formal de variables intervenidas. |
| NOD-10 | (iii) Variable, matriz y unidad | Pasar a `ERROR` para magnitudes crudas con unidad aprobada. |
| NOD-11, EDG-12 | (iv) Ontología de taxones y rutas; vocabulario de interacciones | Validar contra vocabularios y ontologías aprobadas en vez de los vocabularios sintéticos. |
| NOD-12 | (i) Especie y segmento inicial | Definir qué tipos son obligatorios en datos reales. |
| EDG-04 | (v) Criterio de aristas sustentadas o inferidas | Reemplazar por reglas que admitan `observed`, `annotated` e `inferred` con su evidencia. |
| CON-04 (regla pendiente) | (iii) Variable objetivo | Marcar componentes sin nodos del tipo objetivo. |

Las restricciones bioquímicas (balance de masa, estequiometría y tolerancias; §6.1-vi)
**no** son reglas de integridad del grafo: corresponden al futuro módulo `constraints` y no
se definen aquí.
