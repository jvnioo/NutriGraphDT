# GNN homogénea de referencia `homo_sage` (A41-2)

`HomoSAGE` (`nutrigraphdt.models.gnn.homo_sage`) es la variante de control de la actividad 41:
ignora los tipos de nodo y de arista, para medir cuánto aportan `hetero_sage` (#79) y
`hetero_gat` (#80) al modelar la heterogeneidad. Sigue el §5 del diseño de A41-1 (#77,
`docs/models/gnn-architecture.md`) y hereda de `SCFAGraphModel` (A41-5,
[componentes compartidos](gnn-components.md)).

```text
x_t, missing_mask_t ──► NodeTypeEncoder ──► h_t
h_t ──► to_homogeneous() ──► SAGEConv(hidden, hidden, aggr) ──► separar por node_type ──► residual   (× num_layers)
h_t ──► mean_readout ──► ScfaRegressionHead ──► [B, 3]
```

- **Proyección antes de homogeneizar.** Los tipos tienen distinto número de columnas, así que
  los encoders por tipo de A41-5 llevan todo a `hidden` antes de `to_homogeneous()`.
- **Una convolución compartida por capa.** Cada capa usa una sola `SAGEConv(hidden, hidden)`
  para todos los nodos y relaciones; el tipo de relación no se usa. Sus parámetros no dependen
  del dataset (2 tripletas en D1, 22 en el sintético).
- **Todos los tipos se actualizan.** `SAGEConv` incluye el término del propio nodo, así que un
  nodo aislado (`taxon` y `diet` en D1) también recibe actualización. Después, el residual y
  la lectura son los de A41-5.
- **Hiperparámetros.** `ModelConfig` (hidden 64, 2 capas, dropout 0.2) y `aggr="mean"`
  (permitidas: `mean`, `max`, `sum`), los valores iniciales del §6 del diseño.

```python
from torch_geometric.loader import DataLoader

from nutrigraphdt.models.gnn import GraphMetadata, HomoSAGE, ModelConfig

model = HomoSAGE(GraphMetadata.from_graphs(graphs), ModelConfig())
prediction = model(next(iter(DataLoader(graphs, batch_size=16))))  # [16, 3]
```

La salida tiene una fila por grafo del lote: en el criterio de aceptación de #78, `N_objetivo`
es el número de grafos (§2 del diseño).
