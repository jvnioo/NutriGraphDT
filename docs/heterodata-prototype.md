# Prototipo HeteroData del dataset sintético

- **Tarea:** A35-1 — Construir el prototipo HeteroData desde el dataset sintético (#28).
- **Módulo:** `nutrigraphdt.graph.heterodata` (requiere el extra `graph`; ver
  [`development.md`](development.md#optional-graph-extra-pytorch-and-pytorch-geometric)).
- **Codificación:** `prototype-0.1`, provisional.

El prototipo convierte cada instancia del dataset sintético en un
[`HeteroData`](https://pytorch-geometric.readthedocs.io/en/2.7.0/generated/torch_geometric.data.HeteroData.html)
de PyTorch Geometric, según la correspondencia de [DS-01](synthetic-dataset-spec.md). Declara
en `metadata.json` las columnas de features y del target, valida cada grafo con todas las
[reglas de integridad](graph-integrity-rules.md) y serializa los grafos entregables.

> **Alcance.** Es un prototipo para ejercitar el flujo `data -> graph -> models` con datos
> sintéticos. La codificación de features es mínima y no es una propuesta científica. El
> constructor definitivo, desde datos preprocesados y con el esquema v1 acordado con
> Investigación, es A39-1 (#35). Ningún valor sintético es una observación real.

## Uso

Desde la línea de comandos, `--graphs` agrega los grafos al dataset exportado:

```bash
python scripts/generate_synthetic_dataset.py --graphs
python scripts/validate_graph.py --graphs
```

Desde Python:

```python
from nutrigraphdt.data.synthetic import export_dataset, generate_scenario_dataset
from nutrigraphdt.graph.heterodata import build_synthetic_graphs, save_graphs

build = build_synthetic_graphs(generate_scenario_dataset())
root = export_dataset(build.dataset, "artifacts/synthetic/prototype", overwrite=True)
save_graphs(build.graphs, root / "graphs", overwrite=True)

print(build.report.is_valid, sorted(build.graphs))
data = build.graphs["synthetic:scenario:basal:0001"]
print(data["metabolite"].y_mask.flatten().tolist())  # los tres AGCC
```

`build_synthetic_graphs` sigue el orden de evaluación de VG-01: valida los registros, convierte
solo las instancias sin `ERROR` y pasa los grafos por `prepare_graphs_for_model`, que evalúa las
reglas de tensores. El resultado de validar el prototipo está en el
[reporte de validación](prototype-validation-report.md) (A35-2). `build.dataset` es el dataset de entrada con el esquema declarado en sus
metadatos, listo para exportar; `build.graphs` contiene solo los grafos entregables, y
`build.report`, todos los hallazgos.

Para cargar los grafos y validarlos junto con los registros exportados:

```python
from nutrigraphdt.graph.heterodata import load_graphs
from nutrigraphdt.graph.validation import prepare_graphs_for_model, read_raw_dataset

graphs = load_graphs("artifacts/synthetic/prototype/graphs")
records = read_raw_dataset("artifacts/synthetic/prototype")
delivered, report = prepare_graphs_for_model(records, graphs)
print(sorted(delivered), report.to_dict()["summary"])
```

Para inspeccionar los grafos guardados (conteos por tipo, grado medio, componentes conexas y
un subgrafo de muestra en Mermaid), usa `scripts/graph_stats.py` (A35-4), descrito en
[`scripts/README.md`](../scripts/README.md):

```bash
python scripts/graph_stats.py --graphs artifacts/synthetic/prototype/graphs
```

## Qué contiene cada grafo

| Contrato DS-01 | En el `HeteroData` |
|---|---|
| Nodos de cada tipo | `data[node_type]`, con filas ordenadas por `node_id`. |
| Features | `x` (`float32`, `[N, F]`) y `missing_mask` (`bool`, misma forma). |
| Trazabilidad | `node_id`, `source_id` y `raw_attributes`, alineados con las filas. Además, `raw_missing_mask`, la máscara JSON original de cada nodo, para que el round-trip no pierda campos. |
| Relaciones | `data[source, relation, target]`: `edge_index` (`long`, `[2, E]`), `edge_attr` (`float32`, `[E, A]`), `evidence_id`, `evidence_status`, `evidence_method` y `raw_attributes`. Columnas en el orden de exportación de DS-05. |
| Instancia | Atributos globales con los campos del registro de instancia. `timepoint = null` queda ausente, porque PyG no almacena `None`. |
| Salidas | `data.output_records` con todas las salidas de la instancia, e `y`/`y_mask` en `metabolite` (ver "Variable objetivo"). |

Cada conversión termina con `data.validate(raise_on_error=True)`, como exige DS-01, y
`heterodata_to_records` reconstruye los registros JSONL de un grafo: las pruebas comprueban que
el round-trip JSONL -> `HeteroData` -> JSONL no pierde ni cambia campos.

## Codificación `prototype-0.1`

Las features son valores **crudos, sin normalizar**. No existe una partición de datos, y DS-01
exige ajustar los escaladores solo sobre entrenamiento.

| Tipo | Columnas de `x` | No se usan como feature |
|---|---|---|
| `diet` | Un valor por componente de `composition` y unidad (por ejemplo, `composition.crude_protein (g/kg)`). | `name`, `ingredients`, `source_version`. |
| `additive` | `dose`, una columna por unidad (`CFU/kg`, `mg/kg`). | `category`, `substance`, `control_label` (categorías). |
| `substrate` | `quantity`, por unidad. | `chemical_id`, `name`. |
| `taxon` | `abundance`, por unidad. | `taxonomy_level` (categoría), `quantification_method`. |
| `function` | `annotation_value`, una columna por tipo de valor y unidad (`presence`/`binary`, `abundance`/`CPM`). | `function_type`, `annotation_source` (categorías). |
| `metabolite` | Ninguna: la concentración es el target. | `concentration`, `sample_matrix`, `unit`. |
| `host` | `covariates.age_days (d)` y `covariates.body_weight_g (g)`, con las unidades del [diccionario](synthetic-dataset-dictionary.md). | `covariates.sex` (categoría), `species`, `gut_segment`, `cohort_id`. |
| `phenotype` | Ninguna: un fenotipo es un resultado observado. | `value`, `trait`, `timepoint`, `unit`. |

| Relación | Columnas de `edge_attr` |
|---|---|
| `diet -provides-> substrate` | `proportion`, en la unidad del sustrato. |
| Las demás | Ninguna (`[E, 0]`); su evidencia se conserva en las listas alineadas. |

**Una columna nunca mezcla unidades ni magnitudes** (DS-01). Si los nodos de un tipo declaran la
misma magnitud en unidades o con calificadores distintos, cada combinación es una columna, y un
nodo sin valor en ella (de otra unidad, o `null`) tiene `0.0` con máscara `true`. `edge_attr` no
tiene máscara en DS-01, así que una feature de arista con varias unidades es un error de
construcción, no una columna ambigua. Un valor no finito también es un error: nunca se enmascara
en silencio.

Las columnas se derivan del **dataset completo**, para que todas sus instancias compartan
columnas, y se declaran en `metadata.json` bajo `node_feature_schema`, `edge_feature_schema` y
`target_schema`, junto con `feature_encoding = prototype-0.1`. Cada columna registra nombre,
fuente, unidad, calificador y codificación (`raw`).

## Variable objetivo (AGCC)

La variable objetivo es la **concentración de los ácidos grasos de cadena corta** acetato,
propionato y butirato, la lista que priorizan el Esquema General (Figura 1) y A34-3. Se
configura con `SyntheticTargetConfig` (`nutrigraphdt.data.synthetic.targets`).

- La capa de datos escribe una salida por metabolito objetivo en `outputs.jsonl`, con
  `measured_or_predicted = "synthetic"` (un target artificial nunca es una medición), la unidad
  y la matriz del metabolito, y `model_version = null`.
- El constructor materializa esas salidas en `data["metabolite"].y` (`[N, 1]`) e `y_mask`
  (`true` en las filas con target). Las salidas `predicted` se conservan en
  `data.output_records`, pero nunca se usan como target.
- Todas las salidas de un tipo deben compartir origen, unidad y matriz; si no, la construcción
  falla en lugar de mezclarlas en una columna.

**Sin fuga del target.** `x` de `metabolite` no incluye la concentración, y `x` de `phenotype`
no incluye su valor: rasgos como `cecal_scfa_total` se derivan de los AGCC y revelarían el
target. Los atributos no tensoriales (`raw_attributes`) conservan esos valores para la
trazabilidad; un modelo solo debe consumir los tensores declarados.

La elección de la variable objetivo sigue pendiente de Investigación (§6.1-iii del Esquema
General): variable, matriz y unidad. Un metabolito es objetivo solo si su `chemical_id` coincide
exactamente con la lista. Las copias que el generador crea más allá del catálogo
(`synthetic:metabolite:acetate_06`) no lo son, y el valerato del catálogo tampoco, porque no
está en la lista priorizada. Esa exclusión no afirma que no sea un AGCC.

## Serialización

`save_graphs` escribe `graph_0001.pt`, `graph_0002.pt`… en orden de `graph_id`, porque un
`graph_id` sintético contiene `:`, que no es válido en nombres de archivo de Windows. El
`manifest.json` asocia cada archivo con su `graph_id`, formato y codificación. No reemplaza grafos
existentes salvo con `overwrite=True`.

`load_graphs` usa `torch.load(weights_only=True)` y **solo** permite las clases de
almacenamiento de PyG (`BaseStorage`, `NodeStorage`, `EdgeStorage`, `GlobalStorage`), así que un
`.pt` manipulado no puede ejecutar código: la carga falla. Además, comprueba que cada archivo
contenga el `graph_id` que declara el manifiesto. Aun así, carga `.pt` solo de fuentes
confiables; JSONL sigue siendo el formato de intercambio auditable (DS-01).

## Limitaciones

- **Codificación provisional:** no hay normalización, codificación de categorías ni vocabularios
  versionados; las columnas dependen de los valores presentes en el dataset. A38-1 (#32) y A39-1
  (#35) deben fijarlos con Investigación.
- **Precisión:** los tensores son `float32`. Los valores exactos se conservan en
  `raw_attributes` y `output_records`.
- **Escenarios sin efecto modelado:** desde la corrección de #46, el escenario intervenido copia
  los nodos y aristas del basal y solo cambia `crude_protein`, así que no hay advertencias
  INS-06 ni INS-07. El generador no modela efectos de la intervención: los valores derivados,
  incluidos los targets, son idénticos entre escenarios.
- **Advertencia de PyG:** si un tipo de nodo queda sin aristas (por ejemplo, un aditivo aislado
  en el perfil mínimo), `validate()` de PyG emite una advertencia. Es la condición CON-03 del
  reporte, no un error.
