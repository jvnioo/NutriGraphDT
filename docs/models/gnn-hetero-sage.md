# GraphSAGE heterogénea (`hetero_sage`)

`HeteroSAGE` implementa A41-3 (#79) con una `HeteroConv` por capa y una
`SAGEConv((-1, -1), hidden)` por tripleta de `GraphMetadata.edge_types`, incluidas las relaciones
inversas `rev_*`. `aggr` controla la agregación de vecinos de `SAGEConv` (`mean` por defecto);
`relation_aggr` controla cómo se agregan las relaciones de destino (`sum` por defecto).

La clase implementa solo `convolve`. `SCFAGraphModel` aplica entre capas la actualización residual
con ReLU y dropout, la lectura por grafo y la cabeza de tres AGCC. La lectura excluye `metabolite`
y `phenotype`, que pueden participar en el paso de mensajes, pero no entran directamente en la
predicción.

## Inicialización lazy

Antes de crear el optimizador, invoque `initialize_lazy_parameters(model)`. La función crea un
`HeteroData` sintético a partir de la metadata, con un nodo por tipo y una relación vacía por cada
tripleta, y ejecuta un forward bajo `torch.no_grad()`. Así inicializa también relaciones ausentes
del lote usado para el calentamiento; el modo train/eval existente se conserva. El helper acepta
cualquier subclase de `SCFAGraphModel` con parámetros lazy, incluida la variante futura
`hetero_gat`.

```python
from nutrigraphdt.models.gnn import HeteroSAGE, initialize_lazy_parameters

model = HeteroSAGE(metadata, config)
initialize_lazy_parameters(model)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
```

## Convoluciones de la última capa

La última capa no tiene convoluciones hacia `metabolite` ni `phenotype`: esos tipos no entran a
la lectura, así que su actualización en la última capa nunca llegaría a la predicción ni
recibiría gradiente (#111). Las tripletas de cada capa las da `layer_edge_types`; la decisión
está en el §5.1 de [gnn-architecture.md](gnn-architecture.md). En las capas anteriores participan
todas las relaciones de la metadata, y en el grafo sintético todas reciben gradiente.

En D1 pueden faltar 20 de las 22 relaciones del esquema sintético. La inicialización usa toda la
metadata del modelo, no solo las claves de aristas presentes en un lote D1.
