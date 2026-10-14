# Componentes compartidos de las GNN (A41-5)

`nutrigraphdt.models.gnn` implementa las piezas que el diseño de A41-1 (#77,
`docs/models/gnn-architecture.md`) asigna a A41-5. Con ellas, las tres variantes (`homo_sage` #78,
`hetero_sage` #79 y `hetero_gat` #80) difieren solo en la convolución. Requiere el extra `graph`
y no se importa desde `nutrigraphdt.models`, de modo que los baselines siguen funcionando sin
PyTorch.

La implementación de `hetero_sage`, su inicialización lazy y el alcance de los gradientes por capa
se describen en [gnn-hetero-sage.md](gnn-hetero-sage.md).

La variante con atención, recuperación de pesos y alcance de interpretación se describen en
[gnn-hetero-gat.md](gnn-hetero-gat.md).

```text
x_t, missing_mask_t ──► NodeTypeEncoder ──► h^0 ──► [convolve × L + ResidualUpdate] ──► h^L
h^L ──► mean_readout ──► [B, 6·hidden] ──► ScfaRegressionHead ──► [B, 3]
```

| Pieza | Módulo | Sección del diseño |
|---|---|---|
| `add_graph_target`, `masked_mse_loss` | `target.py` | §2.1 Target por grafo |
| `GraphMetadata`, `ModelConfig`, `SCFAGraphModel` | `base.py` | §3 Interfaz común |
| `NodeTypeEncoder`, `ResidualUpdate`, `mean_readout`, `ScfaRegressionHead` | `components.py` | §4 Componentes compartidos |

## Target por grafo

`add_graph_target(data)` agrega a cada grafo:

| Atributo | Forma | Contenido |
|---|---|---|
| `data.y_graph` | `[1, 3]`, `float32` | Acetato, propionato y butirato, en el orden de `DEFAULT_SCFA_TARGETS`; `0.0` donde falta. |
| `data.y_graph_mask` | `[1, 3]`, `bool` | `True` donde el nodo `metabolite` correspondiente tiene `y_mask = True`. |

- Un nodo `metabolite` se asigna a un AGCC por su `raw_attributes["chemical_id"]` (si no lo
  tiene, por su `node_id`), con la tabla `CHEMICAL_ID_TO_CANONICAL` de A40-3. En D1 ambos son el
  nombre canónico (`acetate`); en el sintético el `node_id` es opaco
  (`synthetic:metabolite:0001`) y el `chemical_id` es `synthetic:metabolite:acetate`.
- La coincidencia es **exacta**. Los demás metabolitos (`isobutyrate`, `valerate`, lactato…)
  quedan fuera del target.
- Dos nodos con valor para el mismo AGCC son un error.
- `DataLoader` concatena ambos atributos en `[B, 3]`.

`masked_mse_loss(prediction, target, mask)` es el MSE sobre las celdas con `mask = True`. Un lote
sin ningún valor devuelve `0.0` conectado al grafo de cómputo.

## Interfaz común

- **`GraphMetadata`** describe el dataset: columnas de `x` por tipo de nodo (`node_channels`) y la
  unión de tipos de arista, incluidas las inversas `rev_*`. Se construye con
  `GraphMetadata.from_graphs(graphs)` o desde `node_feature_schema` con `from_feature_schema`.
  `to_pyg()` devuelve el mismo formato que `HeteroData.metadata()`.
- **`ModelConfig`** tiene los hiperparámetros comunes con los valores iniciales del §6:
  `hidden_channels = 64`, `num_layers = 2`, `dropout = 0.2`. Los de cada variante (agregación,
  cabezas de atención) y la lectura desde YAML quedan para #78–#80 y la fábrica de A41-8 (#84).
- **`SCFAGraphModel(metadata, config)`** es la clase base abstracta. Una variante implementa solo
  `convolve(layer, h_dict, edge_index_dict)`, que devuelve la actualización (sin activación) de
  los tipos que son destino de alguna arista. `forward(data)` aplica encoder, `num_layers` capas
  de `convolve` con residual, lectura y cabeza, y devuelve `float32` `[B, 3]`.
  - Acepta un grafo individual (`B = 1`) o un lote de `DataLoader`.
  - Lee `x`, `missing_mask`, `edge_index` y `batch`. No lee `y`, `y_mask`, `y_graph`,
    `y_graph_mask`, `raw_attributes` ni la evidencia.

```python
from torch_geometric.loader import DataLoader

from nutrigraphdt.graph.builder import add_reverse_edges
from nutrigraphdt.models.gnn import GraphMetadata, ModelConfig, add_graph_target, masked_mse_loss

graphs = [add_graph_target(add_reverse_edges(graph)) for graph in validated_graphs]
model = MiVariante(GraphMetadata.from_graphs(graphs), ModelConfig())  # subclase de SCFAGraphModel

for batch in DataLoader(graphs, batch_size=16, shuffle=True):
    prediction = model(batch)  # [B, 3]
    loss = masked_mse_loss(prediction, batch.y_graph, batch.y_graph_mask)
```

## Componentes

| Componente | Comportamiento |
|---|---|
| `NodeTypeEncoder` | `Linear(2·F_t, hidden)` sobre `[x_t ‖ missing_mask_t]`, para que un `0.0` ausente no se confunda con un cero medido. Un tipo con `F_t = 0` (`diet` y `metabolite` en D1) usa un vector aprendido por tipo, igual para todos sus nodos. |
| `ResidualUpdate` | `h_t + dropout(relu(update_t))`. Un tipo sin actualización (aislado, como `taxon` y `diet` en D1) conserva su embedding. |
| `mean_readout` | Media por grafo de `diet`, `additive`, `substrate`, `taxon`, `function` y `host`, concatenada en el orden de `NODE_TYPES`: `[B, 6·hidden]` en cualquier dataset. Un tipo sin nodos aporta ceros. `metabolite` y `phenotype` no entran. |
| `ScfaRegressionHead` | `Linear(6·hidden, hidden) → ReLU → Dropout → Linear(hidden, 3)`, sin activación final. |

## Limitaciones

- **El escalado no está aquí.** El §6.2 del diseño estandariza `x` y el target con estadísticas
  de `train`; corresponde al entrenamiento (A41-7 y act. 44). Con valores crudos, el peso
  corporal del huésped (del orden de 100 g en D1) domina la lectura.
- **Mapeo de AGCC distinto al de A40-3.** `_canonicalize_target_name` de
  `nutrigraphdt.models.tabular` también busca por subcadena, y en D1 asigna `isobutyrate` a
  `butyrate`. Aquí se usa solo la coincidencia exacta; la discrepancia está informada en el PR
  de A41-5 para que se resuelva en A40-3.

## Expectativas de gradientes en A41-6

La suite tensorial común comprueba gradientes con un grafo controlado, con features en todos los
tipos de nodo y al menos dos vecinos por destino y relación. En grafos con datos distintos, GAT
puede tener gradientes nulos en parámetros de atención cuando un destino tiene un solo vecino o
cuando varios nodos sin features comparten el mismo embedding; esas dos causas dependen de los
datos y no representan por sí solas un defecto del modelo.

En `HeteroSAGE` y `HeteroGAT`, las convoluciones por relación de la última capa cuyo destino es
`metabolite` o `phenotype` no afectan la predicción porque la lectura los excluye. Su falta de
gradiente es una pregunta abierta de diseño de A41-1; A41-6 la refleja en el test, pero no
resuelve si esa decisión debe cambiar. `HomoSAGE` comparte una convolución entre tipos y, por
tanto, no tiene parámetros separables por destino excluido.
