# Compatibilidad del wrapper de explicadores con HeteroData (A60-P1, #170)

- **Módulo:** `nutrigraphdt.explainability.wrapper`
- **Estado:** implementación de Desarrollo. La revisión científica con Investigación es #171.
- **Dependencias:** [A55-P2](#157) (PoC de explicadores), [A55-P3](#156) (contrato de salida).
- **Advertencia científica:** La importancia que produce el wrapper mide asociación dentro
  del modelo, no causalidad ni evidencia biológica. Ver `docs/models/explanation-contract.md`.

## 1. Resumen

`HeteroExplainer` encapsula `torch_geometric.explain.Explainer` para modelos `SCFAGraphModel`
sobre `HeteroData`. Produce artefactos conformes al contrato `nutrigraphdt-explanation 1.0.0`
(#156) y detecta de forma activa las combinaciones incompatibles entre variante, algoritmo y
tipo de máscara, fallando con `IncompatibleExplainerError` en vez de devolver resultados
parciales silenciosos.

## 2. Tabla de compatibilidad

La tabla recoge el estado de cada combinación sobre el dataset sintético
(`generate_synthetic_dataset`), con `torch 2.14.1` y `torch_geometric 2.8.1`.
La PoC de #157 (`docs/models/explainers-poc.md`) y las pruebas de `tests/unit/test_hetero_explainer.py`
verifican estos resultados.

| Variante | Algoritmo | Máscaras | Estado | Notas |
|---|---|---|---|---|
| `hetero_sage` | `GNNExplainer` | atributos + aristas | ✅ compatible | Ruta principal. |
| `hetero_sage` | `GNNExplainer` | solo atributos | ✅ compatible | Sin máscaras de aristas. |
| `hetero_sage` | `GNNExplainer` | solo nodos | ✅ compatible | `node_mask_type="object"`. |
| `hetero_gat` | `GNNExplainer` | atributos + aristas | ✅ compatible | Ruta principal con atención. |
| `hetero_gat` | `AttentionExplainer` | aristas (atención) | ✅ compatible¹ | Requiere `uses_attention`; ver advertencias. |
| `homo_sage` | `GNNExplainer` | solo atributos | ✅ compatible | Aristas no admitidas (ver §3). |
| `homo_sage` | `GNNExplainer` | atributos + aristas | ❌ incompatible | `IncompatibleExplainerError` (reach=0). |
| `hetero_sage` | `AttentionExplainer` | aristas | ❌ incompatible | `IncompatibleExplainerError` (sin capas GAT). |
| cualquier variante | `CaptumExplainer` | — | ⚠️ opcional | Requiere `pip install -e '.[explain]'`. |

¹ `AttentionExplainer` solo calcula importancia de aristas. El wrapper desactiva automáticamente
`node_mask_type` cuando el algoritmo es de atención.

## 3. Incompatibilidades documentadas

### 3.1 Máscaras de aristas en `homo_sage`

`homo_sage` convierte el grafo a representación homogénea dentro de `convolve`, de modo que
las máscaras por tipo de arista (tripleta) no llegan a ninguna capa `MessagePassing` (alcance =
0). El wrapper lo detecta con `edge_mask_reach` antes de ejecutar el explicador y lanza
`IncompatibleExplainerError` de inmediato.

En `homo_sage`, las únicas máscaras válidas son las de nodos (`node_mask_type="object"`) y de
atributos (`node_mask_type="attributes"`).

### 3.2 `AttentionExplainer` en modelos sin capas GAT

`AttentionExplainer` necesita coeficientes de atención de `GATConv`. Solo es compatible con
`hetero_gat`. El wrapper detecta la clase del modelo y lanza `IncompatibleExplainerError` antes
de crear el `Explainer` de PyG.

### 3.3 Estado compartido entre métodos

Tras `GNNExplainer` con máscaras de aristas, llamar a `CaptumExplainer` sobre el **mismo
objeto de modelo** puede fallar con «differentiated Tensor not used», aunque `clear_masks`
haya limpiado las máscaras. El wrapper no hace `deepcopy` del modelo (no es serializable con
`mappingproxy`), por lo que el llamador debe crear una instancia de `HeteroExplainer` por
algoritmo si va a mezclar `GNNExplainer` y `CaptumExplainer` sobre el mismo modelo.

### 3.4 Aristas irrelevantes

El wrapper excluye automáticamente los tipos de arista que no reciben convolución en ninguna
capa del modelo (`layer_edge_types`). Estas aristas no generan gradiente de máscara y, de
incluirse, provocarían fallos silenciosos. El filtrado es idéntico al de la PoC de #157.

## 4. Uso básico

```python
from nutrigraphdt.explainability import HeteroExplainer, validate_explanation
from nutrigraphdt.data.synthetic import generate_synthetic_dataset
from nutrigraphdt.graph.heterodata import build_synthetic_graphs
from nutrigraphdt.models.gnn.base import GraphMetadata
from nutrigraphdt.models.gnn.factory import build_model, load_model_config
from pathlib import Path

dataset = generate_synthetic_dataset()
graphs = build_synthetic_graphs(dataset).graphs
data = graphs[dataset.instances[0].graph_id]
metadata = GraphMetadata.from_graphs([data])

config = load_model_config(Path("configs/models/hetero_sage.yaml"))
model = build_model(config, metadata).eval()

explainer = HeteroExplainer(
    model,
    algorithm="gnn_explainer",  # GNNExplainer de PyG
    epochs=200,
    seed=42,
    top_k=10,
    unit="1",  # log-razón
)
explanation = explainer.explain(data, target="butyrate")

# Validación contra el contrato 1.0.0
validated = validate_explanation(explanation.model_dump())
print(validated.format_version, len(validated.importance.edges))
```

### Variante con `homo_sage` (solo nodos/atributos)

```python
explainer = HeteroExplainer(
    model,
    algorithm="gnn_explainer",
    node_mask_type="attributes",
    edge_mask_type=None,  # homo_sage no admite aristas
    epochs=200,
    seed=42,
)
```

### Variante con `hetero_gat` y atención

```python
# AttentionExplainer: solo aristas, advertencia obligatoria
explainer = HeteroExplainer(model_gat, algorithm="attention", seed=42)
explanation = explainer.explain(data, target="butyrate")
codes = {w.code for w in explanation.warnings}
assert "attention_is_not_explanation" in codes
```

### Con `run` de trazabilidad

```python
from nutrigraphdt.explainability import RunRef, SplitRef

run = RunRef(
    run_id="20261028-120000_hetero_sage_s42",
    run_json="runs/20261028-120000_hetero_sage_s42/run.json",
    format_version="1.0.0",
    variant="hetero_sage",
    seed=42,
    dataset_id="holofood-v1",
    split=SplitRef(version="3.0.0", sha256="a" * 64),
    git_commit=None,
)
explainer = HeteroExplainer(model, run=run, epochs=200, seed=42)
```

## 5. Configuración

| Parámetro | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `algorithm` | `str \| ExplainerAlgorithm` | `"gnn_explainer"` | Nombre del algoritmo o instancia de PyG. |
| `node_mask_type` | `"attributes" \| "object" \| None` | `"attributes"` | Tipo de máscara de nodos. |
| `edge_mask_type` | `"object" \| None` | `"object"` | Tipo de máscara de aristas; `None` en `homo_sage`. |
| `epochs` | `int` | `100` | Épocas de optimización (GNNExplainer, PGExplainer). |
| `lr` | `float` | `0.01` | Tasa de aprendizaje del explicador. |
| `seed` | `int` | `42` | Semilla para reproducibilidad. |
| `top_k` | `int` | `10` | Máximo de aristas en el subgrafo. |
| `unit` | `str` | `"1"` | Unidad de la salida (`"1"` = log-razón, `"mmol_kg"` = concentración). |
| `run` | `RunRef \| Mapping \| None` | `None` | Trazabilidad de la corrida de entrenamiento. |
| `node_feature_names` | `Mapping[str, Sequence[str]] \| None` | `None` | Nombres de columnas de `x` por tipo; se infieren del grafo si no se pasan. |

## 6. Errores

| Excepción | Cuándo |
|---|---|
| `IncompatibleExplainerError` | Algoritmo o máscara incompatible con la variante del modelo. |
| `ValueError` | Target no encontrado en el modelo, o índice fuera de rango. |
| `TypeError` | Tipo de `algorithm` o `target` no reconocido. |
| `ExplanationContractError` | La explicación construida viola el contrato (no debería ocurrir en uso normal). |

## 7. Preguntas abiertas

- Cuántas épocas de `GNNExplainer` son suficientes para un modelo entrenado en D1 (#171).
- Si `captum` debe pasar a dependencia del extra `explain` (actualmente es solo para la PoC).
- Si el estado compartido entre `GNNExplainer` y `CaptumExplainer` (§3.3) es reproducible
  fuera del grafo sintético.

## 8. Referencias

- [`docs/models/explanation-contract.md`](explanation-contract.md) — Contrato de salida `1.0.0`.
- [`docs/models/explainers-poc.md`](explainers-poc.md) — PoC de compatibilidad (#157).
- [`docs/models/explanations-protocol-review.md`](explanations-protocol-review.md) — Revisión cruzada (#158).
- [`scripts/explain_synthetic.py`](../../scripts/explain_synthetic.py) — Ejemplo ejecutable.
- [`tests/unit/test_hetero_explainer.py`](../../tests/unit/test_hetero_explainer.py) — Pruebas unitarias.
