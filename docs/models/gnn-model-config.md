# Configuración y fábrica de modelos GNN (A41-8)

`nutrigraphdt.models.gnn.factory` lee la variante y sus hiperparámetros desde un YAML de
`configs/models/` y construye el modelo con `build_model`. Cambiar de variante o de valores solo
requiere editar el archivo. Requiere el extra `graph`, que incluye PyYAML.

```python
from nutrigraphdt.models.gnn import GraphMetadata, build_model, load_model_config

cfg = load_model_config("configs/models/hetero_sage.yaml")
torch.manual_seed(42)  # la inicialización de los pesos es aleatoria
model = build_model(cfg, GraphMetadata.from_graphs(graphs))  # graphs: ver gnn-components.md
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
```

`build_model` devuelve el modelo con las capas perezosas de las variantes heterogéneas ya
inicializadas (`initialize_lazy_parameters`), así que el optimizador se puede crear de inmediato.
`metadata` describe el dataset (§3 del [diseño](gnn-architecture.md)): la fábrica no la infiere
del archivo.

## Archivos

Hay un archivo por variante, con los valores iniciales del §6 del diseño:

| Archivo | `variant` | Campos propios (valor inicial) |
|---|---|---|
| `configs/models/homo_sage.yaml` | `homo_sage` | `aggr` (`mean`) |
| `configs/models/hetero_sage.yaml` | `hetero_sage` | `aggr` (`mean`), `relation_aggr` (`sum`) |
| `configs/models/hetero_gat.yaml` | `hetero_gat` | `heads` (4), `concat` (`true`), `relation_aggr` (`sum`) |

Campos comunes a las tres variantes: `hidden_channels` (64), `num_layers` (2) y `dropout` (0.2).
Un campo omitido toma su valor inicial; `variant` es obligatorio.

## Validación

La validación es de Pydantic v2 (`extra="forbid"`, modo estricto) y ocurre al leer el archivo,
antes de construir el modelo. Se rechaza con `ModelConfigError` (subclase de `ValueError`) y un
mensaje que nombra el archivo y cada campo inválido:

| Caso | Ejemplo rechazado |
|---|---|
| Falta `variant` o no existe | `variant: gcn` |
| Campo de otra variante o desconocido | `heads: 4` en `homo_sage` |
| Tipo incorrecto, sin conversión implícita | `hidden_channels: "64"`, `hidden_channels: true`, `concat: "yes"` |
| Entero no positivo | `hidden_channels: 0`, `num_layers: 0`, `heads: 0` |
| `dropout` fuera de `[0, 1)` | `dropout: 1.0` |
| Agregación no permitida | `aggr` fuera de `mean`, `max`, `sum`; `relation_aggr` fuera de `sum`, `mean` |
| `hidden_channels` no divisible por `heads` con `concat: true` | `hidden_channels: 10`, `heads: 4` |
| YAML mal formado o que no es un objeto | una lista en la raíz |

Por ejemplo:

```text
configs/models/homo_sage.yaml: configuración de modelo inválida (variantes: homo_sage, hetero_sage, hetero_gat).
  - homo_sage.heads: Extra inputs are not permitted
```

Al cambiar de variante hay que quitar los campos propios de la anterior que la nueva no admite
(por ejemplo, `heads` al pasar de `hetero_gat` a `hetero_sage`): el rechazo es intencional, para
que un valor no quede ignorado en silencio.

Los rangos repiten los de los constructores de las variantes (`ModelConfig`, `HomoSAGE`,
`HeteroSAGE`, `HeteroGAT`), que siguen validando por su cuenta cuando se usan sin la fábrica.

## Formato

El Issue pide YAML para los modelos, mientras que `configs/baselines/` usa JSON. A44-4 (#98)
anticipa esta diferencia: la alineación del formato de la configuración de entrenamiento queda
para A44-6 (#100).
