# Contrato de salida de las explicaciones (A55-P3, #156)

- **Formato:** `nutrigraphdt-explanation`, versión **`1.0.0`**.
- **Validador:** `nutrigraphdt.explainability.validate_explanation` (no requiere PyTorch).
- **Ejemplo:** [`examples/explanation-synthetic.json`](examples/explanation-synthetic.json),
  sintético y válido.
- **Estado:** propuesta de Desarrollo. La revisión con Investigación es #158 (A55-P4); hasta
  entonces el contrato no tiene aprobación científica.

Una **explicación** describe, para **una salida** del modelo y **una instancia**, cuánto depende
esa salida de cada nodo, atributo y arista del grafo (la **importancia**, que calcula un
explicador), cuál es el **subgrafo top-k** que la resume y qué **evidencia** declara el grafo para
cada arista. Es el formato común de los explicadores (#157, #170), del subgrafo serializado
(#169), de los reportes y de la futura aplicación web.

## 1. Principios

1. **Importancia no es evidencia.** `importance` es un resultado del explicador sobre el modelo
   entrenado. `evidence` es el estado y el método que el **grafo** declara para la arista
   (reglas de integridad, EDG-04), copiados sin cambios. Una arista muy importante no gana
   evidencia, y una poco importante no la pierde.
2. **Asociación no es causalidad.** Que la salida dependa de un taxón no significa que ese taxón
   cause el cambio en los AGCC; tampoco valida una relación biológica.
3. **La atención no es una explicación.** Los pesos de atención de `hetero_gat` no se usan como
   importancia por defecto; si se usan, se declara (`uses_attention`) y se advierte.
4. **Trazable y sin datos crudos.** Cada explicación identifica la corrida (`run.json`), el
   explicador y su configuración. Solo lleva identificadores, nombres de columnas e importancias:
   el contrato rechaza cualquier campo no declarado, así que no se cuelan tensores, atributos
   crudos (`raw_attributes`) ni rutas absolutas.

## 2. Estructura

```text
{
  format, format_version, created_at,
  run:        trazabilidad a run.json
  explainer:  método, biblioteca, versión y configuración
  target:     instancia y salida explicadas
  importance: { scale, nodes[], attributes[], edges[] }
  subgraph:   { k, selection, tie_break, nodes[], edges[] }
  warnings[]: advertencias de interpretación
}
```

### 2.1 `run`: trazabilidad a la corrida

Copia campos del `run.json` de la corrida que entrenó el modelo
([`gnn-training.md`](gnn-training.md)).

| Campo | Tipo | Regla |
|---|---|---|
| `run_id` | `str` | El de `run.json` (`<AAAAMMDD-HHMMSS>_<variante>_s<semilla>`). |
| `run_json` | `str` | Ruta del `run.json`, **relativa** a la raíz del repositorio. |
| `format_version` | `str` | `format_version` del `run.json`. |
| `variant`, `seed`, `dataset_id` | `str`, `int`, `str` | Los del `run.json`. |
| `split.version`, `split.sha256` | `str`, `str` | Versión y SHA-256 (64 hex) de la partición, como en `run.json` (#133). |
| `git_commit` | `str` o `null` | Commit del `run.json` (40 hex); `null` si Git no estaba disponible. |

### 2.2 `explainer`: método

| Campo | Tipo | Regla |
|---|---|---|
| `name`, `library`, `library_version`, `algorithm` | `str` | Por ejemplo `GNNExplainer`, `torch_geometric`, `2.8.0` y la ruta de la clase. |
| `explanation_type` | `model` \| `phenomenon` | Como en `torch_geometric.explain`: explica la predicción del modelo o el objetivo medido. |
| `node_mask_type` | `object` \| `attributes` \| `common_attributes` \| `null` | Tipo de máscara de nodos; `null` si no se calcula. |
| `edge_mask_type` | `object` \| `null` | Tipo de máscara de aristas; `null` si no se calcula. |
| `seed` | `int` | Semilla del explicador (puede diferir de la del entrenamiento). |
| `config` | `object` | Hiperparámetros completos del explicador (épocas, tasa de aprendizaje, `mode`, `level`…). |
| `uses_attention` | `bool` | `true` si la importancia viene de pesos de atención. |

### 2.3 `target`: qué se explica

| Campo | Tipo | Regla |
|---|---|---|
| `graph_id`, `sample_id` | `str`, `str` o `null` | Instancia explicada. |
| `is_synthetic` | `bool` | Debe coincidir con el prefijo `synthetic:` del `graph_id` (EXP-09). |
| `output`, `output_index` | `str`, `int ≥ 0` | Salida del modelo: una de `MODEL_OUTPUT_NAMES` (`log_propionate_acetate`, `log_butyrate_acetate`, `log_total`; ver [`metrics.md`](metrics.md)) o un AGCC, y su columna en la salida. |
| `unit` | `str` | Unidad canónica de la salida (`1` para una log-razón, `mmol_kg` para una concentración). |
| `model_output` | `number` o `null` | Valor que predijo el modelo, en `unit`. |

### 2.4 `importance`: importancia calculada

`scale` declara cómo leer los valores:

| Campo | Regla |
|---|---|
| `kind` | `normalized` (rango `[0, 1]`, o `[-1, 1]` si el explicador da signo) o `raw`. |
| `range` | `[mínimo, máximo]` finitos; todo valor de importancia cae dentro (EXP-02). |
| `normalization` | Cómo se normalizó: `max_abs`, `sum_to_one`… o `none`. |
| `aggregation` | Cómo se pasó de una máscara por elemento a un valor por nodo, atributo o arista (por ejemplo, `sum_over_feature_mask`). |

| Lista | Campos de cada elemento |
|---|---|
| `nodes` | `node_type`, `node_id`, `importance`. |
| `attributes` | `node_type`, `node_id`, `attribute` (nombre de la columna de `x` en `node_feature_schema`, por ejemplo `abundance (relative_abundance)`), `importance`. |
| `edges` | `source_type`, `relation_type`, `target_type`, `source_id`, `target_id`, `importance`, `evidence`. |

`evidence` = `{evidence_status, evidence_method, evidence_source}` copiados de la arista del grafo.
Es `null` **solo** en una relación inversa (`rev_*`), que la conversión a `HeteroData` agrega para
el paso de mensajes y que no existe en los registros.

Los identificadores son los del grafo: `node_id` y la tripleta de relación del
[esquema v1](../graph/graph-schema-v1.md). No se renombran ni se reindexan.

### 2.5 `subgraph`: subgrafo top-k

| Campo | Regla (`1.0.0`) |
|---|---|
| `k` | Entero `≥ 1`: máximo de aristas. |
| `selection` | `top_k_edges_by_importance`: las `min(k, número de aristas)` aristas de mayor importancia. |
| `tie_break` | `lexicographic_edge_key`: a igual importancia, gana la clave `(source_type, relation_type, target_type, source_id, target_id)` menor. Así la selección es determinista. |
| `edges` | Referencias (sin importancia ni evidencia) a aristas de `importance.edges`. |
| `nodes` | Exactamente el conjunto de extremos de `edges`. |

La extracción determinista del subgrafo se implementa en `nutrigraphdt.explainability.subgraph` (#169),
garantizando conservación exacta de extremos (`EXP-07`), desempate lexicográfico determinista,
manejo explícito de relaciones inversas y serialización JSON de ida y vuelta.

### 2.6 `warnings`: advertencias de interpretación

Lista de `{code, message}`. Son obligatorias:

| `code` | Cuándo |
|---|---|
| `association_not_causation` | Siempre. |
| `importance_is_not_evidence` | Siempre. |
| `synthetic_data` | Si `target.is_synthetic` es `true`. |
| `attention_is_not_explanation` | Si `explainer.uses_attention` es `true`. |

Se pueden agregar otras (por ejemplo, la inestabilidad entre semillas del explicador).

## 3. Reglas de validación

`validate_explanation` aplica todas y devuelve todas las infracciones juntas.

| Regla | Comprueba |
|---|---|
| EXP-01 | Estructura y tipos: formato y versión exactos, campos obligatorios, **ningún campo no declarado**, `run_json` relativo, SHA-256 y commit con su forma. |
| EXP-02 | `scale.range` es un intervalo finito; una escala `normalized` usa `[0, 1]` o `[-1, 1]`; toda importancia es finita y está dentro del rango. |
| EXP-03 | Los tipos de nodo existen y cada arista es una relación del esquema v1 o su inversa `rev_*`. |
| EXP-04 | Sin nodos, atributos ni aristas repetidos. |
| EXP-05 | Si hay importancia de nodos, cada atributo y cada extremo de arista se refiere a un nodo listado. |
| EXP-06 | Cada arista del grafo declara su evidencia; el estado es uno de los cinco de DS-01 y el método lo respalda (vocabulario de EDG-04 más `synthetic_generator`); en una instancia sintética la evidencia es `synthetic`. |
| EXP-07 | El subgrafo tiene a lo más `k` aristas, sin repetidos, todas con importancia calculada, con `nodes` igual a sus extremos y, con `top_k_edges_by_importance`, exactamente las de mayor importancia según el desempate declarado. |
| EXP-08 | Están las advertencias obligatorias. |
| EXP-09 | `target.is_synthetic` coincide con el prefijo `synthetic:` del `graph_id`. |

## 4. Ejemplo

[`examples/explanation-synthetic.json`](examples/explanation-synthetic.json) explica la salida
`log_butyrate_acetate` de una variante `hetero_sage` hipotética sobre la instancia sintética por
omisión del generador (`generate_synthetic_dataset()`). Los identificadores, las aristas y su
evidencia son los del dataset sintético; **las importancias y la salida del modelo son valores
ilustrativos del ejemplo**, no el resultado de un explicador. El subgrafo top-4 recorre la ruta
mecanística sintética sustrato → taxón → función → butirato. Una prueba
(`tests/unit/test_explanation_contract.py`) verifica que el ejemplo es válido y que sus aristas y
evidencia coinciden con el generador.

```python
import json
from pathlib import Path

from nutrigraphdt.explainability import validate_explanation

data = json.loads(Path("docs/models/examples/explanation-synthetic.json").read_text("utf-8"))
explanation = validate_explanation(data)  # lanza ExplanationContractError si no cumple
print(explanation.subgraph.k, len(explanation.importance.edges))
```

## 5. Versionado y coordinación

- Un cambio que agregue un campo opcional sube la versión menor (`1.1.0`); uno que cambie o
  retire un campo, o la regla de selección del subgrafo, sube la mayor.
- #157 (A55-P2) comprobará qué explicadores de PyG producen estas máscaras sobre `HeteroData`;
  #170 (A60-P1) implementará el wrapper que escribe este formato; #169 (A60-P3), la extracción
  del subgrafo; #158 (A55-P4), la revisión con Investigación.
- Preguntas abiertas para #158: si `[-1, 1]` (importancia con signo) debe admitirse en F7; qué
  advertencias adicionales exige Investigación para D1; y si las aristas `hypothetical` deben
  marcarse de forma especial en la visualización.
