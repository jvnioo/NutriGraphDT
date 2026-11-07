# Identidad de los taxones en D1: comparación técnica (#266)

Generado con `python scripts/evaluate_taxon_identity.py`, dispositivo `cuda` (última ejecución: 0.0 h).

## Método

Implementa la comparación de la [decisión de #239](../../../docs/research/decision_taxon_identity_D1.md), sección 4.

- **Cohorte y folds:** 56 animales; plan `configs/splits/d1_holofood_cv.json` (k = 5, semillas [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]), el de #139. Mismos folds y semilla de entrenamiento por fold en todos los brazos.
- **Grafos:** agregados a género con `has_capacity` y `produces` (#175, #173). Los brazos `gnn_actual` y `gnn_mlp` quitan los nodos `function` y sus aristas.
- **Vocabulario de linaje:** prevalencia ≥ 0.1 en el train interno del fold y como máximo 30 grupos; 30 grupos en todos los folds. El test y el val interno no intervienen.
- **Objetivo y métricas:** composicional de D-03, fuera de fold.
- **Procedencia de la corrida:** corrida en dos tramos: 150 folds de ridge y 216 de GNN con el commit 9bed0c2, y el resto con d1c9224, que quita la trazabilidad de los lotes. Dos folds del primer tramo, repetidos con el código nuevo, dieron un fraction_mae_pp idéntico.
- **`ridge`:** diseño, diseño y perfil por familia, y diseño y los 876 taxones, con `alpha` elegido por `GroupKFold` interno por corral. Las tablas salen de los mismos grafos.

## Resultados (media ± desviación entre folds y semillas)

| Modelo | Brazo | `fraction_mae_pp` | `fraction_r2` | `log_total_mae` | `reconstructed_mae` | Folds |
|---|---|---:|---:|---:|---:|---:|
| `hetero_gat` | `gnn_actual` | 4.20 ± 0.79 | -0.06 ± 0.40 | 0.27 ± 0.07 | 7.78 ± 1.47 | 50 |
| `hetero_gat` | `gnn_functional` | 4.13 ± 0.59 | -0.03 ± 0.31 | 0.26 ± 0.07 | 7.66 ± 1.43 | 50 |
| `hetero_gat` | `gnn_functional_lineage` | 4.07 ± 0.70 | -0.02 ± 0.38 | 0.27 ± 0.07 | 7.77 ± 1.37 | 50 |
| `hetero_gat` | `gnn_mlp` | 4.12 ± 0.70 | -0.02 ± 0.35 | 0.27 ± 0.07 | 7.82 ± 1.39 | 50 |
| `hetero_sage` | `gnn_actual` | 4.09 ± 0.75 | -0.01 ± 0.39 | 0.27 ± 0.08 | 7.89 ± 1.47 | 50 |
| `hetero_sage` | `gnn_functional` | 4.05 ± 0.71 | 0.00 ± 0.36 | 0.27 ± 0.07 | 7.86 ± 1.41 | 50 |
| `hetero_sage` | `gnn_functional_lineage` | 4.11 ± 0.71 | -0.02 ± 0.35 | 0.27 ± 0.08 | 7.93 ± 1.46 | 50 |
| `hetero_sage` | `gnn_mlp` | 4.11 ± 0.68 | -0.01 ± 0.33 | 0.27 ± 0.07 | 7.90 ± 1.36 | 50 |
| `homo_sage` | `gnn_actual` | 4.16 ± 0.78 | -0.04 ± 0.42 | 0.27 ± 0.07 | 7.88 ± 1.46 | 50 |
| `homo_sage` | `gnn_functional` | 4.10 ± 0.70 | -0.01 ± 0.35 | 0.27 ± 0.07 | 7.86 ± 1.42 | 50 |
| `homo_sage` | `gnn_functional_lineage` | 4.19 ± 0.75 | -0.08 ± 0.41 | 0.27 ± 0.08 | 7.92 ± 1.46 | 50 |
| `homo_sage` | `gnn_mlp` | 4.09 ± 0.69 | -0.01 ± 0.36 | 0.27 ± 0.07 | 7.84 ± 1.45 | 50 |
| — | `ridge_design` | 3.98 ± 0.72 | 0.06 ± 0.29 | 0.26 ± 0.08 | 7.71 ± 1.50 | 50 |
| — | `ridge_family` | 3.69 ± 0.64 | 0.19 ± 0.26 | 0.26 ± 0.08 | 7.66 ± 1.58 | 50 |
| — | `ridge_genus` | 4.39 ± 1.40 | -0.53 ± 2.08 | 0.27 ± 0.10 | 7.89 ± 1.88 | 50 |

Referencia de #140: `day_only` tiene `fraction_mae_pp` 4.03 y `fraction_r2` 0.04.

## Comparaciones pareadas de `fraction_mae_pp`

`Δ = brazo − referencia`, con el t corregido de Nadeau y Bengio. Valores negativos favorecen al brazo.

| Comparación | Modelo | Media brazo | Media referencia | Δ | IC 95 % | p |
|---|---|---:|---:|---:|---|---:|
| Lo adoptado frente a la GNN actual | `homo_sage` | 4.19 | 4.16 | 0.04 | [-0.27, 0.34] | 0.813 |
| Aporte de la ruta funcional | `homo_sage` | 4.10 | 4.16 | -0.05 | [-0.46, 0.35] | 0.788 |
| Aporte del linaje | `homo_sage` | 4.19 | 4.10 | 0.09 | [-0.34, 0.53] | 0.676 |
| Forma de la distribución, sin identidad | `homo_sage` | 4.09 | 4.16 | -0.07 | [-0.40, 0.26] | 0.664 |
| Lo adoptado frente a ridge por familia | `homo_sage` | 4.19 | 3.69 | 0.51 | [0.14, 0.88] | 0.008 |
| GNN actual frente a ridge sobre el diseño | `homo_sage` | 4.16 | 3.98 | 0.18 | [-0.16, 0.52] | 0.289 |
| Lo adoptado frente a la GNN actual | `hetero_sage` | 4.11 | 4.09 | 0.02 | [-0.30, 0.33] | 0.910 |
| Aporte de la ruta funcional | `hetero_sage` | 4.05 | 4.09 | -0.04 | [-0.37, 0.29] | 0.810 |
| Aporte del linaje | `hetero_sage` | 4.11 | 4.05 | 0.06 | [-0.28, 0.40] | 0.738 |
| Forma de la distribución, sin identidad | `hetero_sage` | 4.11 | 4.09 | 0.03 | [-0.25, 0.30] | 0.854 |
| Lo adoptado frente a ridge por familia | `hetero_sage` | 4.11 | 3.69 | 0.42 | [0.05, 0.79] | 0.026 |
| GNN actual frente a ridge sobre el diseño | `hetero_sage` | 4.09 | 3.98 | 0.11 | [-0.18, 0.41] | 0.446 |
| Lo adoptado frente a la GNN actual | `hetero_gat` | 4.07 | 4.20 | -0.13 | [-0.60, 0.34] | 0.587 |
| Aporte de la ruta funcional | `hetero_gat` | 4.13 | 4.20 | -0.07 | [-0.54, 0.41] | 0.783 |
| Aporte del linaje | `hetero_gat` | 4.07 | 4.13 | -0.06 | [-0.43, 0.30] | 0.732 |
| Forma de la distribución, sin identidad | `hetero_gat` | 4.12 | 4.20 | -0.08 | [-0.40, 0.25] | 0.632 |
| Lo adoptado frente a ridge por familia | `hetero_gat` | 4.07 | 3.69 | 0.38 | [-0.01, 0.78] | 0.057 |
| GNN actual frente a ridge sobre el diseño | `hetero_gat` | 4.20 | 3.98 | 0.22 | [-0.12, 0.56] | 0.203 |
| Perfil por familia frente al diseño | — | 3.69 | 3.98 | -0.29 | [-0.51, -0.07] | 0.011 |
| Tabla ancha frente a familia | — | 4.39 | 3.69 | 0.70 | [-0.55, 1.94] | 0.265 |

Las demás métricas están en `paired.csv`.

## Conclusión

- **La combinación no supera a `ridge` con la tabla por familia** en `fraction_mae_pp` (el IC 95 % corregido incluye el cero o favorece a `ridge`, en todas las variantes). Como pide la decisión de #239, se informa así: **el grafo no agrega capacidad predictiva en D1 y su aporte queda en la explicabilidad.**
- Frente a la GNN actual, la combinación mejora `fraction_mae_pp` en: ninguna variante.
- El perfil por familia mejora a `ridge` sobre el diseño.
- **Hay señal del microbioma que `ridge` capta y la GNN no aprovecha, con la misma información de entrada.** Por eso, este resultado no permite atribuir la diferencia solo al grafo: también puede deberse a la arquitectura, a la escala de las columnas de linaje o al ajuste, que no se buscó por brazo. Ninguna de esas causas se probó aquí.

## Cobertura de la ruta (decisión de #256, sección 5)

Ninguna evaluación de D1 se llama «mecanística»: esta es una evaluación con estructura funcional anotada.

| AGCC | Géneros con ruta | % lecturas a género | % del total de lecturas |
|---|---:|---:|---:|
| Acetato | 35 | 36.1 | 16.1 |
| n-Butirato | 14 | 35.8 | 16.0 |
| Propionato | 7 | 2.1 | 0.9 |

## Limitaciones

- Con 56 animales, las diferencias tienen una incertidumbre amplia; el IC corregido considera que los folds no son independientes.
- Capacidad anotada no es actividad demostrada, y no se afirma ningún efecto de la dieta a través del microbioma (#258).
- La identidad por familia no distingue géneros de una misma familia, salvo los 38 con aristas funcionales.
- `top_k` y `min_prevalence` son elecciones de Desarrollo, no valores científicos.
- Los hiperparámetros son los de `configs/models/`, sin búsqueda por brazo.
