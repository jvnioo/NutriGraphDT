# Prueba de sobreajuste de las GNN (A41-7)

Prueba de cordura previa al pipeline de entrenamiento (act. 44): cada variante debe poder
llevar a casi cero la pérdida de entrenamiento sobre un mismo lote pequeño. Si una variante no lo
logra, el defecto es de construcción (gradientes que no llegan, capas sin efecto, escalas que
impiden optimizar), no de falta de datos. Pasarla **no** dice nada sobre generalización.

La lógica está en `nutrigraphdt.models.gnn.sanity` y el experimento en `scripts/overfit_gnn.py`;
`tests/integration/test_gnn_overfit.py` lo ejecuta con un lote y épocas reducidos. Requiere el
extra `graph`.

```bash
python scripts/overfit_gnn.py
```

## Protocolo

- **Lote.** `--n-graphs` grafos sintéticos (8 por defecto) de semillas consecutivas desde
  `--first-seed`, cada uno convertido con `build_synthetic_graphs` (compuerta de VG-07), con
  relaciones inversas (`add_reverse_edges`) y target por grafo (`add_graph_target`). Los 8
  grafos tienen los tres AGCC.
- **Escalado.** Features por tipo y columna y target por AGCC, con las estadísticas del propio
  lote (`prepare_overfit_batch`). Aquí el lote es el conjunto de entrenamiento, así que no hay
  fuga; no reemplaza el escalado del pipeline (A44-2, #96), que ajusta con `train`.
- **Modelos.** `ModelConfig(dropout=0.0)`: `hidden_channels = 64` y `num_layers = 2` del §6 del
  [diseño](gnn-architecture.md), sin dropout para que la pérdida refleje solo la capacidad de
  ajuste. Agregaciones y cabezas con sus valores iniciales. `torch.manual_seed(42)` antes de
  construir cada variante.
- **Optimización.** Adam con `lr = 1e-3` (§6), 300 pasos completos sobre el mismo lote, pérdida
  `masked_mse_loss` en la escala estandarizada.
- **Criterio.** Pérdida final menor que `--threshold` (`1e-2` por defecto): con el target
  estandarizado, la varianza de partida es 1, así que el umbral es el 1 % de esa varianza.

## Resultado

Comando `python scripts/overfit_gnn.py` (valores por defecto). Python 3.12.0, torch 2.14.1+cpu,
torch-geometric 2.8.0. Grafos `synthetic:graph:0001` a `synthetic:graph:0008`.

| Variante | Pérdida inicial | Pérdida final (época 300) | Mínima | ¿Sobreajusta? |
|---|---:|---:|---:|---|
| `homo_sage` | 1.0275 | 5.64e-07 | 1.39e-08 | sí |
| `hetero_sage` | 1.0038 | 9.97e-06 | 7.29e-08 | sí |
| `hetero_gat` | 1.1078 | 8.27e-09 | 1.98e-09 | sí |

Las tres variantes sobreajustan el lote, así que no hace falta abrir un issue de corrección.

Las tres bajan de 1e-3 entre las épocas 50 y 64. Después hay picos aislados, típicos de Adam con
`lr` fijo y una pérdida muy cercana a cero, de los que la pérdida se recupera:

| Variante | Primera época < 1e-3 | Pico máximo posterior | Épocas posteriores > 1e-3 |
|---|---:|---:|---:|
| `homo_sage` | 64 | 3.64e-03 | 15 |
| `hetero_sage` | 51 | 1.94e-02 | 38 |
| `hetero_gat` | 50 | 6.45e-03 | 23 |

El pico de `hetero_sage` supera momentáneamente el umbral; el criterio usa la pérdida de la
última época, que queda tres órdenes de magnitud por debajo. El entrenamiento real (A44-3,
#97) conserva la mejor época según `val`, no la última.

Curvas (`log10` de la pérdida; una de cada cinco épocas y la última):

```mermaid
xychart-beta
    title "homo_sage: log10 de la pérdida de entrenamiento"
    x-axis "época" [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206, 211, 216, 221, 226, 231, 236, 241, 246, 251, 256, 261, 266, 271, 276, 281, 286, 291, 296, 300]
    y-axis "log10(MSE)" -8 --> 1
    line [0.012, -0.075, -0.170, -0.295, -0.447, -0.622, -0.866, -1.178, -1.592, -2.099, -2.369, -2.600, -2.693, -3.353, -3.371, -3.417, -3.818, -4.080, -4.381, -4.028, -2.545, -2.739, -3.881, -3.298, -3.870, -3.962, -3.893, -5.566, -4.583, -4.454, -4.671, -4.937, -5.110, -5.216, -5.477, -6.933, -5.771, -6.779, -5.748, -5.263, -4.324, -3.034, -2.684, -2.991, -3.705, -5.297, -3.877, -3.739, -3.909, -4.229, -4.598, -4.904, -5.074, -5.121, -5.164, -5.374, -6.156, -6.350, -5.881, -7.840, -6.249]
```

```mermaid
xychart-beta
    title "hetero_sage: log10 de la pérdida de entrenamiento"
    x-axis "época" [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206, 211, 216, 221, 226, 231, 236, 241, 246, 251, 256, 261, 266, 271, 276, 281, 286, 291, 296, 300]
    y-axis "log10(MSE)" -8 --> 1
    line [0.002, -0.199, -0.494, -0.988, -1.237, -1.772, -1.721, -2.149, -2.412, -2.470, -3.020, -2.811, -3.444, -3.617, -3.458, -3.652, -3.951, -4.068, -4.321, -4.506, -4.863, -5.384, -5.402, -5.356, -6.262, -5.791, -6.452, -6.293, -6.446, -6.990, -7.035, -5.974, -4.361, -2.625, -3.267, -3.582, -3.037, -3.055, -3.685, -4.468, -3.956, -3.962, -4.211, -4.681, -4.896, -4.865, -4.537, -3.664, -2.406, -1.865, -2.470, -3.343, -2.654, -4.118, -3.122, -4.647, -3.571, -5.016, -4.019, -5.572, -5.002]
```

```mermaid
xychart-beta
    title "hetero_gat: log10 de la pérdida de entrenamiento"
    x-axis "época" [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206, 211, 216, 221, 226, 231, 236, 241, 246, 251, 256, 261, 266, 271, 276, 281, 286, 291, 296, 300]
    y-axis "log10(MSE)" -9 --> 1
    line [0.044, -0.149, -0.422, -0.937, -1.222, -1.654, -1.952, -2.421, -2.433, -2.711, -3.099, -3.147, -3.481, -3.632, -3.790, -3.974, -3.305, -2.785, -2.952, -3.155, -3.342, -3.522, -3.818, -4.966, -4.162, -4.565, -3.868, -3.345, -2.806, -6.220, -3.258, -3.657, -4.121, -3.783, -3.925, -5.756, -4.518, -3.390, -2.256, -2.610, -2.675, -3.121, -5.165, -3.490, -3.832, -5.747, -4.205, -4.294, -4.875, -6.194, -6.186, -5.818, -5.901, -6.256, -7.175, -7.013, -6.308, -6.316, -7.552, -6.771, -8.083]
```
