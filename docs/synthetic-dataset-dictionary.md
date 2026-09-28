# Diccionario del dataset sintético

- **Tarea:** DS-07 — Documentar el dataset y preparar un ejemplo de uso (#8).
- **Versión del esquema:** `1.0.0`. **Versión del generador descrita:** `0.1.0.dev0`.
- **Alcance:** describe los valores que el generador implementado en
  `src/nutrigraphdt/data/synthetic/` produce hoy. No redefine el contrato.

La [especificación del dataset sintético](synthetic-dataset-spec.md) es la fuente canónica
de campos, tipos, relaciones permitidas y reglas de validación. Este diccionario la
complementa con lo que el contrato deja abierto: identificadores, unidades, vocabularios,
rangos por defecto y el origen de cada valor. Si ambos documentos difieren, prevalece la
especificación y este diccionario debe corregirse.

La guía de uso (instalación, generación, carga y errores) está en
[`synthetic-dataset-usage.md`](synthetic-dataset-usage.md).

> **Todo el contenido es sintético.** Nombres, unidades y rangos son convenciones
> computacionales para probar la estructura del grafo. No son observaciones, mediciones,
> rangos fisiológicos ni relaciones biológicas validadas. Los nombres de géneros bacterianos,
> sustratos y metabolitos reales se usan solo como etiquetas legibles; sus valores asociados
> no provienen de ninguna fuente.

## Cómo leer este diccionario

- **Origen del valor:**
  - *catálogo*: se toma de una lista fija del generador;
  - *configuración*: se toma de `SyntheticNodeConfig` o `SyntheticEdgeConfig`;
  - *aleatorio*: se muestrea con una semilla determinista dentro de un rango configurable;
  - *derivado*: se copia o calcula a partir de otro valor.
- **Estado:** reproduce el estado del contrato. *Provisional* significa que Investigación aún
  no confirmó ontologías, magnitudes, unidades ni vocabularios (§6.1 del Esquema General).
- **Rango por defecto:** corresponde a `SyntheticRangeConfig()` sin modificar. Cada entrada de
  catálogo ocupa una fracción de ese rango, así que los valores concretos varían por entrada.

## Campos comunes

### Nodo (`raw/nodes.jsonl`)

| Campo | Tipo | Valor emitido |
|---|---|---|
| `graph_id` | `str` | `SyntheticNodeConfig.graph_id`; por defecto `synthetic:graph:0001`. |
| `node_id` | `str` | `synthetic:<node_type>:<NNNN>`, numerado desde `0001` dentro de cada tipo. |
| `node_type` | `str` | Uno de los ocho tipos de la tabla siguiente. |
| `source_id` | `str` | `SYNTHETIC_V1` (configurable). Indica procedencia, no un nodo de origen. |
| `attributes` | `object` | Atributos propios del tipo; se detallan abajo. |
| `missing_mask` | `object` | Siempre `{}`: el generador estándar no produce valores ausentes. |

### Conteos por defecto

| Tipo | `NodeCountConfig` | Entradas de catálogo | Si el conteo supera el catálogo |
|---|---:|---:|---|
| `diet` | 1 | 2 | Repite el catálogo, agrega ` Var N` al nombre y multiplica la composición por `1 + 0.05·k` (k = vuelta del ciclo). |
| `additive` | 1 | 5 | Repite el catálogo sin cambios. |
| `substrate` | 4 | 8 | Agrega el sufijo `_NN` a `chemical_id`. |
| `taxon` | 10 | 12 | Agrega el sufijo `_NN` a `taxonomy_id`. |
| `function` | 8 | 9 | Agrega el sufijo `_NN` a `function_id`. |
| `metabolite` | 5 | 6 | Agrega el sufijo `_NN` a `chemical_id`. |
| `host` | 1 | — | Con más de un huésped, agrega `_NN` a `cohort_id`. |
| `phenotype` | 2 | 4 | Agrega el sufijo `_NN` a `trait`. |

Con los conteos por defecto, cada instancia tiene 32 nodos y usa las primeras entradas de
cada catálogo en el orden listado abajo.

## Nodos

### `diet` (D) — dieta

| Atributo | Tipo | Unidad | Origen | Valores |
|---|---|---|---|---|
| `name` | `str` | — | catálogo | `Dieta basal estándar de maíz y harina de soya`; `Dieta de crecimiento basada en trigo y cebada`. |
| `ingredients` | `list[str]` | — | catálogo | Por ejemplo, `corn`, `soybean_meal`, `wheat_middlings`, `limestone`, `salt`, `vitamin_premix`. |
| `composition` | `list[object]` | por componente | catálogo | Elementos `{component_id, value, unit}`; ver la tabla siguiente. |
| `source_version` | `str` | — | catálogo | `synthetic_diet_v1`. |

Componentes de `composition` (primera y segunda dieta del catálogo):

| `component_id` | Unidad | Dieta 1 | Dieta 2 |
|---|---|---:|---:|
| `crude_protein` | `g/kg` | 215.0 | 195.0 |
| `crude_fiber` | `g/kg` | 38.0 | 46.0 |
| `crude_fat` | `g/kg` | 52.0 | 44.0 |
| `metabolizable_energy` | `MJ/kg` | 12.8 | 12.2 |
| `calcium` | `g/kg` | 9.5 | 8.8 |
| `total_phosphorus` | `g/kg` | 6.8 | 6.2 |

Estas composiciones no provienen de una fórmula comercial ni de una referencia nutricional.

### `additive` (A) — aditivo

| Atributo | Tipo | Origen | Valores del catálogo |
|---|---|---|---|
| `category` | `str` | catálogo | `probiotic`, `prebiotic`, `phytogenic`, `organic_acid`, `control`. |
| `substance` | `str` | catálogo | Respectivamente: `Bacillus sp. SYN-PRO-001` (cepa ficticia), `Inulina / Fructooligosacáridos`, `Mezcla de aceites esenciales de timol y carvacrol`, `Butirato de sodio encapsulado`, `Ninguno`. |
| `dose` | `number` | catálogo | `1.0e9`, `5000.0`, `150.0`, `1000.0`, `0.0`. |
| `dose_unit` | `str` | catálogo | `CFU/kg` para el probiótico; `mg/kg` para el resto. |
| `control_label` | `str` | catálogo | `supplemented`, o `control_basal` para el control. |

Con el conteo por defecto (1), solo se genera el probiótico. Las dosis son convenciones
sintéticas y no implican un efecto.

### `substrate` (S) — sustrato

| Atributo | Tipo | Unidad | Origen | Valores |
|---|---|---|---|---|
| `chemical_id` | `str` | — | catálogo | `synthetic:substrate:<nombre>`: `arabinoxylan`, `resistant_starch`, `beta_glucan`, `cellulose`, `pectin`, `mucin_glycans`, `inulin`, `xylooligosaccharides`. |
| `name` | `str` | — | catálogo | Nombre legible en español (`Arabinoxilano`, `Almidón resistente`, …). |
| `quantity` | `number` | `g/kg` | aleatorio | Uniforme dentro del rango de la entrada; rango global por defecto 1–50 g/kg. |
| `unit` | `str` | — | catálogo | `g/kg`. |

### `taxon` (T) — taxón o gremio

| Atributo | Tipo | Unidad | Origen | Valores |
|---|---|---|---|---|
| `taxonomy_id` | `str` | — | catálogo | `synthetic:taxon:<nombre>`: `bacteroides`, `faecalibacterium`, `lactobacillus`, `ruminococcus`, `clostridium_cluster_iv`, `akkermansia`, `bifidobacterium`, `prevotella`, `roseburia`, `escherichia_shigella`, `syntheticobacter_a` (ficticio), `streptococcus`. |
| `taxonomy_level` | `str` | — | catálogo | `genus`, o `clade` para `clostridium_cluster_iv`. |
| `abundance` | `number` | `relative_abundance` | aleatorio | Muestras Gamma(α=2, β=1) normalizadas; la suma por instancia es ≈ 1 (redondeo a 6 decimales). |
| `abundance_unit` | `str` | — | fijo | `relative_abundance`. |
| `quantification_method` | `str` | — | fijo | `16S_amplicon`. Es solo una etiqueta: no hubo secuenciación. |

Los pesos del catálogo (`abundance_weight`) no se usan para calcular `abundance`.

### `function` (F) — función, enzima, gen o ruta

| Atributo | Tipo | Unidad | Origen | Valores |
|---|---|---|---|---|
| `function_id` | `str` | — | catálogo | `synthetic:annotation:<id>`: `pathway_a`–`pathway_c`, `enzyme_a`, `enzyme_b`, `gh_family_a`, `gh_family_b`, `gene_a`, `gene_b`. |
| `function_type` | `str` | — | catálogo | `pathway`, `enzyme`, `gh_family` o `gene`. |
| `annotation_source` | `str` | — | catálogo | `synthetic:annotation:source_a` a `source_d`. No corresponde a KEGG, MetaCyc, CAZy ni EggNOG. |
| `annotation_value` | `number` | `CPM` o `binary` | aleatorio o fijo | Para `abundance`: uniforme, con rango global por defecto 1–300 CPM. Para `presence`: siempre `1.0`. |
| `annotation_value_type` | `str` | — | catálogo | `abundance` (rutas, enzimas y familias GH) o `presence` (genes). |
| `unit` | `str` | — | catálogo | `CPM` con `abundance`; `binary` con `presence`. |

Con el conteo por defecto (8), `gene_b` no se genera.

### `metabolite` (M) — metabolito

| Atributo | Tipo | Unidad | Origen | Valores |
|---|---|---|---|---|
| `chemical_id` | `str` | — | catálogo | `synthetic:metabolite:<nombre>`: `acetate`, `propionate`, `butyrate`, `lactate`, `succinate`, `valerate`. |
| `name` | `str` | — | catálogo | `Acetato`, `Propionato`, `Butirato`, `Lactato`, `Succinato`, `Valerato`. |
| `sample_matrix` | `str` | — | catálogo | `cecal_content`. |
| `concentration` | `number` | `mmol/kg` | aleatorio | Uniforme dentro del rango de la entrada; rango global por defecto 0.1–100 mmol/kg. |
| `unit` | `str` | — | catálogo | `mmol/kg`. |

### `host` (H) — huésped

| Atributo | Tipo | Origen | Valores |
|---|---|---|---|
| `species` | `str` | configuración | `chicken` (marcador provisional). |
| `gut_segment` | `str` | configuración | `cecum` (marcador provisional). |
| `cohort_id` | `str` | configuración | `cohort_01`. |
| `covariates.age_days` | `int` | configuración | Igual a `timepoint_days`; por defecto `42`. |
| `covariates.sex` | `str` | aleatorio | `male`, `female` o `mixed`. |
| `covariates.body_weight_g` | `number` | aleatorio | Uniforme, por defecto 500–3500 g. |

### `phenotype` (P) — fenotipo

| Atributo | Tipo | Origen | Valores |
|---|---|---|---|
| `trait` | `str` | catálogo | `feed_conversion_ratio`, `body_weight_gain`, `cecal_scfa_total`, `gut_permeability_fitc`. |
| `timepoint` | `str` | configuración | `day_<timepoint_days>`; por defecto `day_42`. |
| `value` | `number` | aleatorio | Uniforme dentro de una fracción de la escala por defecto 0–1. |
| `unit` | `str` | catálogo | `ratio`, `g`, `mmol/kg` y `ug/mL`, respectivamente. |

**Advertencia:** con la escala por defecto 0–1, `value` no tiene la magnitud que su `unit`
sugiere. Por ejemplo, `body_weight_gain` queda entre 0.5 y 0.85 `g`. Estos valores sirven
para probar estructura; no deben interpretarse en la unidad declarada.

## Aristas (`raw/edges.jsonl`)

Todas las aristas generadas tienen `evidence_id: "SYNTHETIC_V1"`,
`evidence_status: "synthetic"` y `evidence_method: "synthetic_generator"`. El estado
estructural describe la semántica prevista por el contrato. **No indica evidencia.**

Cada par candidato `(origen, destino)` se conecta con una probabilidad fija por relación
(*densidad*). Las densidades por defecto son convenciones para obtener fixtures variados; no
estiman la frecuencia real de ninguna relación.

| Tupla `(origen, relación, destino)` | Estado estructural | Atributos emitidos | Origen del atributo | Densidad por defecto |
|---|---|---|---|---:|
| `('diet', 'provides', 'substrate')` | Aprobada como estructura | `proportion: number`, `unit: str` | derivado: copia `quantity` y `unit` del sustrato | 0.75 |
| `('substrate', 'available_to', 'taxon')` | Provisional | — | — | 0.3 |
| `('taxon', 'has_capacity', 'function')` | Provisional | `annotation_source: str` | derivado: copia el de la función | 0.3 |
| `('function', 'produces', 'metabolite')` | Provisional | — | — | 0.3 |
| `('metabolite', 'measured_in', 'host')` | Provisional | `sample_matrix: str` | derivado: copia el del metabolito | 1.0 |
| `('additive', 'modulates', 'taxon')` | Hipotética | — | — | 0.2 |
| `('additive', 'modulates', 'function')` | Hipotética | — | — | 0.2 |
| `('metabolite', 'associated_with', 'phenotype')` | Hipotética | — | — | 0.3 |
| `('host', 'exhibits', 'phenotype')` | Provisional | `timepoint: str` | derivado: copia el del fenotipo | 1.0 |
| `('taxon', 'interacts_with', 'taxon')` | Hipotética | `interaction_type: str` | aleatorio: `competition`, `cooperation` o `inhibition` | 0.1 |
| `('function', 'cross_feeds', 'function')` | Hipotética | `substrate_id: str` | aleatorio: `node_id` de un sustrato de la misma instancia | 0.1 |

Reglas del generador que conviene tener presentes:

- Los aditivos con `control_label: "control_basal"` no reciben aristas `modulates`.
- No se crean autoaristas en `interacts_with` ni en `cross_feeds`.
- `proportion` es la cantidad del sustrato, no una fracción de la dieta: es igual para todas
  las dietas de una instancia.
- La relación `measured_in` y la etiqueta `16S_amplicon` son nombres del contrato. En este
  dataset no representan ninguna medición.
- Un nodo sin aristas es un resultado válido. El generador no agrega relaciones para forzar
  conectividad.

## Instancias (`raw/instances.jsonl`)

| Campo | Modo escenarios (por defecto) | Modo `--seed N` / `generate_synthetic_dataset` |
|---|---|---|
| `graph_id` | `synthetic:scenario:basal:0001` y `synthetic:scenario:intervened:0001` | `SyntheticNodeConfig.graph_id` (por defecto `synthetic:graph:0001`) |
| `species`, `gut_segment` | Leídos de los nodos `host`: `chicken`, `cecum` | De la configuración de nodos |
| `study_id` | `SYNTHETIC_V1` | `SYNTHETIC_V1` |
| `sample_id` | `synthetic:sample:0001`, compartido por ambos escenarios | `synthetic:sample:<último segmento de graph_id>` |
| `scenario_id` | `basal` / `intervention` | `basal` (configurable a `intervention`) |
| `diet_treatment` | `synthetic_basal_diet` / `synthetic_basal_diet:crude_protein=270.0` | `synthetic_basal_diet` (configurable) |
| `timepoint` | `null` | `null` |
| `is_synthetic` | `true` | `true` |
| `schema_version` | `1.0.0` | `1.0.0` |
| `generator_version` | Versión del paquete (`0.1.0.dev0`) | Versión del paquete |

## Salidas (`raw/outputs.jsonl`)

El generador no produce salidas: el archivo existe y está vacío. El contrato y la validación
de `OutputRecord` ya están implementados. `measured_or_predicted` admite `measured`,
`predicted` y `synthetic`, y `model_version` es obligatorio solo para `predicted`.

## Metadatos (`metadata.json`)

| Campo | Contenido emitido |
|---|---|
| `dataset_id` | `synthetic-scenarios-v1` (escenarios) o `synthetic-v1` (instancia única); configurable desde la API. |
| `schema_version` | `1.0.0` |
| `generator_version` | `0.1.0.dev0` |
| `is_synthetic` | `true` |
| `random_seed` | `42` en modo escenarios; la semilla usada en modo instancia. |
| `configuration` | Configuración efectiva de nodos y aristas. Las relaciones usan claves `origen\|relación\|destino`. |
| `node_feature_schema`, `edge_feature_schema` | `{}`: la codificación de features aún no está implementada. |
| `vocabularies` | Valores presentes de `function_type` y `annotation_value_type`, y el vocabulario configurado de `interaction_type`. |
| `counts` | Nodos por tipo, aristas por relación y salidas, por cada `graph_id`. |

`metadata.json` no incluye fechas, rutas locales ni otros valores no deterministas.
