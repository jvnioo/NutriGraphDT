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

Comando `python scripts/overfit_gnn.py` (valores por defecto) sobre `main` con #120 (convoluciones
podadas) y #123 (lotes alineados). Python 3.14.6, torch 2.14.0+cpu, torch-geometric 2.8.0. Grafos
`synthetic:graph:0001` a `synthetic:graph:0008`.

| Variante | Pérdida inicial | Pérdida final (época 300) | Mínima | ¿Sobreajusta? |
|---|---:|---:|---:|---|
| `homo_sage` | 1.0477 | 9.60e-05 | 1.49e-08 | sí |
| `hetero_sage` | 1.0233 | 1.05e-05 | 1.96e-09 | sí |
| `hetero_gat` | 1.1021 | 3.08e-13 | 6.28e-14 | sí |

Las tres variantes sobreajustan el lote, así que no hace falta abrir un issue de corrección.

Las tres bajan de 1e-3 entre las épocas 47 y 58. Después, `homo_sage` y `hetero_sage` tienen picos
aislados, típicos de Adam con `lr` fijo y una pérdida muy cercana a cero, y la pérdida se recupera
de ellos. `hetero_gat` no vuelve a superar 1e-3:

| Variante | Primera época < 1e-3 | Pico máximo posterior | Épocas posteriores > 1e-3 |
|---|---:|---:|---:|
| `homo_sage` | 58 | 3.48e-03 | 13 |
| `hetero_sage` | 47 | 2.37e-02 | 48 |
| `hetero_gat` | 52 | 8.96e-04 | 0 |

El pico de `hetero_sage` supera por un momento el umbral. El criterio usa la pérdida de la última
época, que queda tres órdenes de magnitud por debajo. El entrenamiento real (A44-3, #97)
conserva la mejor época según `val`, no la última.

Las cifras anteriores no son comparables con estas, por dos cambios: hasta #119 el lote mezclaba
aristas entre grafos que no tenían las mismas relaciones, y #111 quitó de `hetero_sage` y
`hetero_gat` las convoluciones que no llegan a la lectura. Por eso, con la misma semilla, los
pesos iniciales son otros.

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
    y-axis "log10(MSE)" -9 --> 1
    line [0.010, -0.239, -0.658, -1.306, -1.479, -1.736, -2.112, -2.489, -2.434, -2.760, -2.892, -3.247, -2.830, -3.309, -2.979, -4.406, -3.135, -3.298, -4.428, -4.320, -2.870, -2.113, -3.350, -2.732, -3.171, -3.294, -3.519, -3.964, -3.721, -5.749, -4.320, -4.304, -4.745, -5.408, -6.029, -6.090, -5.752, -5.528, -5.727, -7.884, -5.891, -6.483, -8.708, -6.570, -5.379, -3.902, -2.216, -3.067, -2.190, -4.553, -2.965, -2.915, -3.110, -3.394, -3.703, -4.060, -4.527, -5.297, -6.498, -5.361, -4.979]
```

```mermaid
xychart-beta
    title "hetero_gat: log10 de la pérdida de entrenamiento"
    x-axis "época" [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156, 161, 166, 171, 176, 181, 186, 191, 196, 201, 206, 211, 216, 221, 226, 231, 236, 241, 246, 251, 256, 261, 266, 271, 276, 281, 286, 291, 296, 300]
    y-axis "log10(MSE)" -12 --> 1
    line [0.042, -0.200, -0.564, -1.016, -1.613, -1.625, -2.085, -2.208, -2.407, -2.717, -2.980, -3.089, -3.539, -3.461, -4.030, -3.920, -4.509, -4.346, -4.815, -4.896, -5.180, -5.419, -5.517, -6.142, -5.987, -6.258, -6.539, -6.585, -7.210, -7.086, -7.423, -7.586, -7.926, -7.914, -8.461, -8.431, -8.730, -9.081, -9.250, -9.362, -9.564, -9.883, -9.969, -10.160, -10.619, -10.811, -10.881, -11.104, -11.449, -11.674, -11.828, -12.000, -12.000, -12.000, -12.000, -12.000, -12.000, -12.000, -12.000, -12.000, -12.000]
```
