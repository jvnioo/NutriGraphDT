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

Comando `python scripts/overfit_gnn.py` (valores por defecto). Python 3.14.6, torch 2.14.0+cpu,
torch-geometric 2.8.0. Grafos `synthetic:graph:0001` a `synthetic:graph:0008`, alineados con
`align_graph_types` (#119) antes de agruparlos.

| Variante | Pérdida inicial | Pérdida final (época 300) | Mínima | ¿Sobreajusta? |
|---|---:|---:|---:|---|
| `homo_sage` | 1.0477 | 9.60e-05 | 1.49e-08 | sí |
| `hetero_sage` | 0.9983 | 4.88e-08 | 6.64e-09 | sí |
| `hetero_gat` | 1.0822 | 5.80e-04 | 6.03e-08 | sí |

Las tres variantes sobreajustan el lote, así que no hace falta abrir un issue de corrección.

Las tres bajan de 1e-3 entre las épocas 50 y 58. Después hay picos aislados, típicos de Adam con
`lr` fijo y una pérdida muy cercana a cero, y la pérdida se recupera de ellos:

| Variante | Primera época < 1e-3 | Pico máximo posterior | Épocas posteriores > 1e-3 |
|---|---:|---:|---:|
| `homo_sage` | 58 | 3.48e-03 | 13 |
| `hetero_sage` | 52 | 1.54e-02 | 35 |
| `hetero_gat` | 50 | 5.26e-03 | 28 |

El pico de `hetero_sage` supera por un momento el umbral. El criterio usa la pérdida de la
última época, que queda muy por debajo. El entrenamiento real (A44-3, #97) conserva la mejor
época según `val`, no la última.

Hasta #119, el lote mezclaba aristas entre grafos cuando no todos tenían las mismas relaciones,
así que las cifras anteriores no son comparables con estas.

Curvas (`log10` de la pérdida; una de cada cinco épocas y la última):

```mermaid
xychart-beta
    title "homo_sage: log10 de la pérdida de entrenamiento"
    x-axis "época" [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206, 211, 216, 221, 226, 231, 236, 241, 246, 251, 256, 261, 266, 271, 276, 281, 286, 291, 296, 300]
    y-axis "log10(MSE)" -8 --> 1
    line [0.020, -0.079, -0.194, -0.388, -0.750, -1.298, -1.407, -1.977, -2.050, -2.427, -2.629, -2.825, -3.150, -3.243, -3.568, -3.790, -4.036, -4.143, -4.466, -4.689, -4.831, -5.138, -5.447, -5.454, -5.773, -6.111, -6.123, -6.461, -6.745, -6.766, -7.248, -7.288, -7.046, -5.694, -3.864, -2.555, -3.095, -4.030, -3.308, -5.968, -3.766, -4.677, -4.478, -4.449, -5.966, -5.228, -5.042, -5.328, -5.850, -6.485, -6.855, -6.118, -4.702, -3.075, -3.117, -4.378, -3.385, -3.381, -5.205, -3.946, -4.018]
```

```mermaid
xychart-beta
    title "hetero_sage: log10 de la pérdida de entrenamiento"
    x-axis "época" [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206, 211, 216, 221, 226, 231, 236, 241, 246, 251, 256, 261, 266, 271, 276, 281, 286, 291, 296, 300]
    y-axis "log10(MSE)" -8 --> 0
    line [-0.001, -0.243, -0.610, -1.200, -1.788, -1.657, -1.976, -2.338, -2.591, -2.802, -2.898, -3.087, -3.356, -3.586, -3.684, -2.565, -3.431, -2.364, -4.589, -2.843, -3.748, -3.395, -4.011, -3.731, -5.987, -4.224, -4.295, -4.734, -5.219, -5.421, -5.300, -5.212, -5.672, -5.971, -5.898, -5.349, -4.692, -3.526, -2.113, -3.408, -2.444, -2.734, -3.298, -3.215, -3.583, -3.827, -3.901, -4.334, -4.379, -4.589, -5.262, -4.798, -5.622, -5.976, -5.482, -5.682, -6.202, -6.941, -7.438, -7.533, -7.311]
```

```mermaid
xychart-beta
    title "hetero_gat: log10 de la pérdida de entrenamiento"
    x-axis "época" [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206, 211, 216, 221, 226, 231, 236, 241, 246, 251, 256, 261, 266, 271, 276, 281, 286, 291, 296, 300]
    y-axis "log10(MSE)" -6 --> 1
    line [0.034, -0.207, -0.602, -1.230, -1.545, -1.773, -2.023, -2.386, -2.618, -2.826, -2.945, -3.138, -3.549, -3.757, -3.862, -4.125, -4.317, -4.602, -4.684, -5.111, -5.334, -5.206, -3.565, -2.351, -3.193, -3.112, -3.323, -3.573, -3.682, -4.468, -3.929, -4.976, -4.772, -4.556, -4.827, -5.238, -5.526, -5.764, -5.633, -5.585, -5.444, -4.393, -2.981, -2.817, -3.282, -3.871, -3.559, -3.587, -3.956, -4.673, -4.655, -4.353, -4.704, -4.712, -4.671, -4.470, -3.778, -2.788, -2.667, -2.785, -3.237]
```
