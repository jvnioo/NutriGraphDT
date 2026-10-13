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

## Gradientes de la última capa

En el grafo sintético, las relaciones participan en distintas capas del paso de mensajes. Las
convoluciones de la primera capa deben recibir gradiente para todas las relaciones cuando se
calcula la pérdida desde la predicción. No se espera gradiente en las convoluciones de la última
capa cuyo nodo destino sea `metabolite` o `phenotype`: esos tipos están excluidos de la lectura y
ya no transmiten mensajes después de esa capa. Las convoluciones de esas relaciones sí pueden
influir en la predicción cuando operan en una capa anterior.

En D1 pueden faltar 20 de las 22 relaciones del esquema sintético. La inicialización usa toda la
metadata del modelo, no solo las claves de aristas presentes en un lote D1.
