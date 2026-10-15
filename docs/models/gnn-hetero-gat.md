# GAT heterogénea (`hetero_gat`)

`HeteroGAT` implementa A41-4 (#80) con una `HeteroConv` por capa y una
`GATConv((-1, -1), out, heads=heads, concat=concat, add_self_loops=False)` por tripleta de
`GraphMetadata.edge_types`, incluidas las relaciones inversas `rev_*`. `heads` vale 4 por
defecto y `relation_aggr` agrega actualizaciones por tipo destino (`sum` por defecto; también se
admite `mean`).

La dimensión por cabeza conserva el ancho oculto del modelo:

- Con `concat=True` (predeterminado), `out = hidden_channels // heads`; por tanto,
  `hidden_channels` debe ser divisible por `heads`. Las salidas de las cabezas se concatenan.
- Con `concat=False`, `out = hidden_channels` y PyG promedia las cabezas. No se requiere que
  `hidden_channels` sea divisible por `heads`.

En ambas configuraciones cada relación produce `[N_destino, hidden_channels]`, compatible con
la actualización residual común. `add_self_loops=False` evita añadir lazos sobre relaciones
bipartitas; el residual conserva la representación del nodo. El dropout de atención de
`GATConv` no se expone como parámetro y se deja en el valor predeterminado de PyG. El dropout de
la actualización residual y la cabeza continúa controlado por `ModelConfig`.

## Predicción y pesos de atención

`forward(data)` hereda el flujo común de `SCFAGraphModel` y devuelve la predicción `[B, 3]`.
Para recuperar los coeficientes de atención, use el método opcional:

```python
prediction, attention = model.forward_with_attention(batch)
```

`prediction` tiene el mismo contrato que `forward`. `attention` es un diccionario con una entrada
por capa y tipo de relación presente:

```python
(layer, edge_type): (edge_index, alpha)
```

`layer` es el índice de capa desde cero; `edge_type` es la tripleta `(origen, relación, destino)`.
`edge_index` tiene forma `[2, E]` y `alpha` forma `[E, heads]`, con una fila por arista y una
columna por cabeza. Las aristas ausentes del grafo de entrada no generan entradas en el
diccionario, aunque la convolución correspondiente forme parte de la metadata del modelo.

Internamente, el método captura los pesos durante el `forward` común, de modo que encoder,
residuales, lectura y cabeza son los mismos que en `forward`; el estado de captura se restaura
incluso si el cálculo falla.

## Uso para explicabilidad

Los pesos ofrecen una señal local de cómo cada cabeza pondera vecinos dentro de una relación, y
pueden ayudar a seleccionar aristas candidatas para análisis de la fase F7. Deben interpretarse
junto con la relación, la capa, las cabezas, el grafo y el comportamiento de la predicción.
Por sí solos no demuestran importancia causal ni una relación biológica validada. La lectura
final del modelo sigue excluyendo `metabolite` y `phenotype`, aunque esos nodos participen en el
paso de mensajes.

La última capa no crea convoluciones hacia `metabolite` ni `phenotype` (#111), así que
`attention` no tiene entradas `(L - 1, (·, ·, metabolite))` ni `(L - 1, (·, ·, phenotype))`:
esos pesos saldrían de parámetros que nunca se entrenan. Cuando cada destino de una relación
tiene un solo vecino, su atención vale 1 por construcción y tampoco es informativa. En D1 esto
ocurre siempre con `host → rev_measured_in → metabolite`. Ver el §5.1 de
[gnn-architecture.md](gnn-architecture.md).

Antes de crear el optimizador, inicialice las convoluciones lazy con metadata completa, también
cuando los primeros grafos de entrenamiento no contengan todas las relaciones:

```python
from nutrigraphdt.models.gnn import HeteroGAT, initialize_lazy_parameters

model = HeteroGAT(metadata, config, heads=4, concat=True)
initialize_lazy_parameters(model)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
```
