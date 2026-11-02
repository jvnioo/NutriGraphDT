# Contrato de salida de las explicaciones (A55-P3, #156)

- **Formato:** `nutrigraphdt-explanation`, versión **`2.0.0`**.
- **Validador:** `nutrigraphdt.explainability.validate_explanation` (no requiere PyTorch).
- **Ejemplo:** [`examples/explanation-synthetic.json`](examples/explanation-synthetic.json),
  sintético y válido.
- **Estado:** revisado por Investigación (A55-P4, #158; respuesta emitida el 01-11-2026). La
  versión `2.0.0` aplica sus decisiones C-01, C-02, C-04, C-06, C-07 y C-09 (#240, #242): las
  relaciones `rev_*` ya no se listan, el top-k se elige por valor absoluto, toda arista declara
  su evidencia y una explicación de D1 lleva las advertencias de C-02. La selección del modelo
  fuera de fold (C-05) es #241. Las explicaciones `1.0.0` no validan: se regeneran.

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

**Qué salidas se explican (C-04).** Una salida se explica solo si el modelo supera a `dummy_mean`
en la métrica de esa salida: `fraction_mae_pp` macro para z1 y z2, `log_total_mae` para ln T. La
prueba es el $t$ corregido (Nadeau y Bengio, 2003): el límite superior $U$ del IC 95 % bilateral
de Δ = MAE(modelo) − MAE(`dummy_mean`) es negativo. En D1, con las corridas del 01-11-2026, las
tres GNN superan a `dummy_mean` en z1 y z2 y no en ln T (Tabla 6 de la respuesta a A55), así que
ln T no se explica. Las concentraciones $c_k$ no se explican en F7: las atribuciones de z1, z2 y
ln T no se suman para dar la de $c_k$. `nutrigraphdt.explainability.explainable_outputs` aplica
el criterio sobre `fold_metrics.csv` y `HeteroExplainer(explainable_outputs=...)` rechaza las
demás salidas.

### 2.4 `importance`: importancia calculada

`scale` declara cómo leer los valores:

| Campo | Regla |
|---|---|
| `kind` | `normalized` (rango `[0, 1]`, o `[-1, 1]` si el explicador da signo) o `raw`. |
| `range` | `[mínimo, máximo]` finitos; todo valor de importancia cae dentro (EXP-02). |
| `normalization` | Cómo se normalizó: `max_abs`, `sum_to_one`… o `none`. Una escala `[-1, 1]` exige `max_abs` (C-01). |
| `aggregation` | Cómo se pasó de una máscara por elemento a un valor por nodo, atributo o arista (por ejemplo, `sum_over_feature_mask`; el wrapper agrega `edges: abs_direct_plus_abs_reverse`). |

**Signo (C-01).** La importancia lleva signo solo si el explicador lo entrega (por ejemplo,
IntegratedGradients); GNNExplainer da máscaras no negativas. Con signo, la escala es `[-1, 1]`
normalizada por `max_abs`, y si el método es IntegratedGradients su línea base queda en
`explainer.config.baseline` (EXP-10; Sundararajan et al., 2017).

| Lista | Campos de cada elemento |
|---|---|
| `nodes` | `node_type`, `node_id`, `importance`. |
| `attributes` | `node_type`, `node_id`, `attribute` (nombre de la columna de `x` en `node_feature_schema`, por ejemplo `abundance (relative_abundance)`), `importance`. |
| `edges` | `source_type`, `relation_type`, `target_type`, `source_id`, `target_id`, `importance`, `evidence`. |

`evidence` = `{evidence_status, evidence_method, evidence_source}` copiados de la arista del grafo.
Es obligatoria en toda arista.

**Relaciones inversas (C-09).** La conversión a `HeteroData` agrega relaciones `rev_*` para el
paso de mensajes; no existen en los registros ni tienen evidencia. Desde `2.0.0` no se listan:
la importancia de cada `rev_*` se suma a la de su arista directa (misma pareja de extremos) como
`|directa| + |inversa|`, y `edges` contiene solo aristas del esquema v1 (EXP-03). Lo hace
`fold_reverse_edge_masks` antes de normalizar.

Los identificadores son los del grafo: `node_id` y la tripleta de relación del
[esquema v1](../graph/graph-schema-v1.md). No se renombran ni se reindexan.

### 2.5 `subgraph`: subgrafo top-k

| Campo | Regla (`2.0.0`) |
|---|---|
| `k` | Entero `≥ 1`: máximo de aristas. |
| `selection` | `top_k_edges_by_abs_importance`: las `min(k, número de aristas)` aristas de mayor **valor absoluto** de importancia (C-01). |
| `tie_break` | `lexicographic_edge_key`: a igual valor absoluto, gana la clave `(source_type, relation_type, target_type, source_id, target_id)` menor. Así la selección es determinista. |
| `edges` | Referencias (sin importancia ni evidencia) a aristas de `importance.edges`. |
| `nodes` | Exactamente el conjunto de extremos de `edges`. |

Solo compiten aristas directas: la importancia de las inversas ya está sumada a ellas (C-09). La
extracción y serialización del subgrafo se implementan en
`nutrigraphdt.explainability.subgraph` (#169; ver
[§6 de la compatibilidad del wrapper](explainer-wrapper-compatibility.md)).

### 2.6 `warnings`: advertencias de interpretación

Lista de `{code, message}`. Son obligatorias:

| `code` | Cuándo |
|---|---|
| `association_not_causation` | Siempre. |
| `importance_is_not_evidence` | Siempre. |
| `synthetic_data` | Si `target.is_synthetic` es `true`. |
| `attention_is_not_explanation` | Si `explainer.uses_attention` es `true`. |
| `diet_day_confounding` | Instancia real de D1 (`run.dataset_id` empieza por `D1_`): la dieta está confundida con el día de muestreo (D-03). |
| `exploratory_treatment_contrast` | Instancia real de D1: con el desbalance 34/15/7, todo contraste entre dietas es exploratorio (L1). |
| `isolated_taxa_pending_s04` | Instancia real con importancia de taxones y ninguna arista que toque un taxón: los taxones están aislados hasta S-04 (L2/L3). |

El wrapper agrega además, cuando corresponde (C-02, C-07):

| `code` | Cuándo |
|---|---|
| `insufficient_group_size` | Instancia real de un animal Fitobiótico (`diet_treatment == "Prebiotic"`): 7 animales en 6 corrales, 1 o 2 por fold de test. |
| `model_not_better_than_day_only` | Instancia real, salvo que el modelo supere a `day_only` fuera de corral (`HeteroExplainer(beats_day_only=True)`). Hoy ninguna GNN lo supera en D1. |
| `explainer_instability` | Φ̂ de Nogueira et al. (2018) del top-k entre ≥ 5 semillas del explicador menor que 0,40 en la estimación puntual (`explain_across_seeds`; umbral provisional). |
| `explainer_not_validated` | El explicador no pasó el control de ruta plantada frente a objetivos permutados de #168. Hoy solo `EdgeGradientSaliency` lo pasó; ninguna explicación con esta advertencia se interpreta. |

**Estabilidad (C-07).** `explain_across_seeds` corre el explicador con al menos 5 semillas por
instancia, salida y modelo y devuelve Φ̂, su IC 95 % asintótico (Nogueira et al., 2018, §5) y la
correlación de Kendall media entre ejecuciones, sin umbral. Φ̂ vale 1 si todas las selecciones
coinciden y 0, en esperanza, para selecciones al azar; con k fijo coincide con el índice de
Kuncheva. Escala de Fleiss et al. (2003): pobre bajo 0,40, intermedia a buena hasta 0,75,
excelente sobre 0,75. La estabilidad no prueba fidelidad: por eso el control de #168 va primero.

**Aristas en D1 (C-06).** Mientras los taxones estén aislados (S-04), el wrapper rechaza pedir
máscaras de aristas sobre un grafo real: en D1 solo se explican atributos.

## 3. Reglas de validación

`validate_explanation` aplica todas y devuelve todas las infracciones juntas.

| Regla | Comprueba |
|---|---|
| EXP-01 | Estructura y tipos: formato y versión exactos, campos obligatorios (incluida la evidencia de cada arista), **ningún campo no declarado**, `run_json` relativo, SHA-256 y commit con su forma. |
| EXP-02 | `scale.range` es un intervalo finito; una escala `normalized` usa `[0, 1]` o `[-1, 1]`, y `[-1, 1]` exige `max_abs`; toda importancia es finita y está dentro del rango. |
| EXP-03 | Los tipos de nodo existen y cada arista es una relación directa del esquema v1; una `rev_*` se rechaza (C-09). |
| EXP-04 | Sin nodos, atributos ni aristas repetidos. |
| EXP-05 | Si hay importancia de nodos, cada atributo y cada extremo de arista se refiere a un nodo listado. |
| EXP-06 | El estado es uno de los cinco de DS-01 y el método lo respalda (vocabulario de EDG-04 más `synthetic_generator`); en una instancia sintética la evidencia es `synthetic`. |
| EXP-07 | El subgrafo tiene a lo más `k` aristas, sin repetidos, todas con importancia calculada, con `nodes` igual a sus extremos y exactamente las de mayor valor absoluto de importancia según el desempate declarado. |
| EXP-08 | Están las advertencias obligatorias de §2.6, incluidas las de D1 y la de taxones aislados. |
| EXP-09 | `target.is_synthetic` coincide con el prefijo `synthetic:` del `graph_id`. |
| EXP-10 | Si el método es IntegratedGradients, `explainer.config` declara su `baseline` (C-01). |

## 4. Ejemplo

[`examples/explanation-synthetic.json`](examples/explanation-synthetic.json) explica la salida
`log_butyrate_acetate` de una variante `hetero_sage` hipotética sobre la instancia sintética por
omisión del generador (`generate_synthetic_dataset()`). Los identificadores, las aristas y su
evidencia son los del dataset sintético; **las importancias y la salida del modelo son valores
ilustrativos del ejemplo**, no el resultado de un explicador. Desde `2.0.0` solo lista aristas
directas (la importancia de cada inversa ya está sumada). El subgrafo top-4 recorre la ruta
mecanística sintética sustrato → taxón → función → butirato hasta la medición en el huésped. Una prueba
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

- Un cambio que agregue un campo opcional sube la versión menor (`2.1.0`); uno que cambie o
  retire un campo, o la regla de selección del subgrafo, sube la mayor.
- `2.0.0` (#240, #242): sin `rev_*` (C-09), evidencia obligatoria, top-k por valor absoluto
  (C-01), `max_abs` para escalas con signo, línea base de IntegratedGradients (EXP-10) y
  advertencias de D1 (C-02). `1.0.0`: primera versión (#156).
- #157 (A55-P2) comprobará qué explicadores de PyG producen estas máscaras sobre `HeteroData`;
  #170 (A60-P1) implementará el wrapper que escribe este formato; #169 (A60-P3), la extracción
  del subgrafo; #158 (A55-P4), la revisión con Investigación.
- Las preguntas abiertas para #158 quedaron respondidas: la importancia con signo se admite con
  `max_abs` (C-01), las advertencias de D1 están en §2.6 (C-02) y las aristas `hypothetical` se
  marcan con un estilo distinto y una leyenda en la visualización de F7 (C-03, #243).
