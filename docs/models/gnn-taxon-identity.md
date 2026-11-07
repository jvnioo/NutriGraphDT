# Identidad de los taxones por linaje en D1 (#266)

Investigación decidió en #239 cómo representar la identidad de los taxones
([decisión](../research/decision_taxon_identity_D1.md)). Este documento describe la implementación y
la comparación técnica que pide su sección 4. El reporte generado está en
[`reports/gnn/d1_taxon_identity/`](../../reports/gnn/d1_taxon_identity/).

## 1. El problema

Antes de #175 y #266, cada taxón de D1 tenía una sola columna, su abundancia relativa. El encoder es
lineal, los taxones no reciben mensajes y la lectura promedia por tipo. Como las abundancias suman 1
sobre el mismo conjunto de taxones, el bloque `taxon` de la lectura valía lo mismo en todos los
animales (`docs/research/check_d1_taxon_readout.py`). **La GNN no recibía información del microbioma
en D1:** sus métricas de #142 salían solo del diseño.

## 2. Qué se implementó

**Aristas funcionales (#175).** `has_capacity` hacia los KO aprobados, desde 38 géneros.

**Linaje por abundancia (`nutrigraphdt.models.training.taxon_identity`).**

```text
x_t = a_t · onehot(grupo_t)     # [N, V + 1]
```

- `grupo_t` es la familia del taxón o, si no la tiene, el rango más profundo sobre género que alcance
  (`lineage_group`, leído de `taxonomy_id`). Cubre a los géneros sin enlace y a los residuales.
- `TaxonLineageEncoder.fit` elige el vocabulario **solo con el train interno del fold**: prevalencia
  ≥ 0,1 y como máximo 30 grupos (`TaxonIdentityConfig`). Son elecciones de Desarrollo; la decisión de
  #239 da como referencia que 30 familias reúnen el 98,9 % de las lecturas que llegan a familia.
- Los grupos fuera del vocabulario van a la columna `otras`, así que la suma por grafo se conserva y un
  grupo nuevo en el test no rompe la evaluación.
- `run_compositional_fold(..., taxon_identity=...)` codifica antes de escalar y adapta `metadata`. La
  corrida guarda el vocabulario en `run.json` (formato `1.1.0`), y `predict_compositional` lo aplica al
  recargarla.

La media por grafo de `x_t` es ahora el perfil de abundancia por familia, distinto en cada animal.

**Control sin identidad.** `nonlinear_taxon_encoder: true` en la configuración del modelo cambia la
proyección de `taxon` por un MLP. Ve la forma de la distribución, sin saber qué taxón es cuál.

## 3. Comparación técnica

```bash
python scripts/evaluate_taxon_identity.py --device cuda
python scripts/evaluate_taxon_identity.py --device cuda --resume   # retoma una corrida cortada
```

| Brazo | Grafo | `x` de `taxon` | Qué mide |
|---|---|---|---|
| `gnn_actual` | Sin nodos `function` | `a_t`, encoder lineal | Referencia: el bloque `taxon` es constante |
| `gnn_mlp` | Sin nodos `function` | `MLP(a_t)` | Solo la forma de la distribución |
| `gnn_functional` | `has_capacity` y `produces` | `a_t`, encoder lineal | La ruta funcional |
| `gnn_functional_lineage` | `has_capacity` y `produces` | `a_t · onehot(grupo)` | **Lo adoptado** |
| `ridge_design` | Tabla del diseño | | Sin microbioma |
| `ridge_family` | Diseño y perfil por familia | | Un modelo tabular con la misma información |
| `ridge_genus` | Diseño y los 876 taxones | | La tabla ancha |

Todos usan los folds y las semillas de #139, el objetivo composicional y las métricas de D-03. La
comparación decide **cuánto** aporta cada parte, no **si** se implementa, y ninguna evaluación de D1 se
llama «mecanística» (#256, sección 5).

## 4. Resultados

Corrida del 07-11-2026: 600 folds de GNN y 150 de `ridge`, sin fallos, en GPU. MAE macro de las
fracciones (`fraction_mae_pp`), media ± desviación entre folds y semillas:

| Brazo | `homo_sage` | `hetero_sage` | `hetero_gat` |
|---|---:|---:|---:|
| `gnn_actual` | 4,16 ± 0,78 | 4,09 ± 0,75 | 4,20 ± 0,79 |
| `gnn_mlp` | 4,09 ± 0,69 | 4,11 ± 0,68 | 4,12 ± 0,70 |
| `gnn_functional` | 4,10 ± 0,70 | 4,05 ± 0,71 | 4,13 ± 0,59 |
| `gnn_functional_lineage` | 4,19 ± 0,75 | 4,11 ± 0,71 | 4,07 ± 0,70 |

Tablas con `ridge`: `ridge_design` 3,98 ± 0,72, `ridge_family` **3,69 ± 0,64** y `ridge_genus`
4,39 ± 1,40. Referencia de #140: `day_only` 4,03.

**Lectura:**

1. **Las cuatro GNN no se distinguen entre sí.** Todas las comparaciones entre brazos tienen un IC
   95 % corregido que incluye el cero. La representación adoptada no mejora a la GNN actual en esta
   evaluación.
2. **La combinación no supera a `ridge` por familia.** Es peor en `homo_sage` (+0,51 pp [0,14; 0,88])
   y en `hetero_sage` (+0,42 pp [0,05; 0,79]), y no se distingue en `hetero_gat` (+0,38 pp [−0,01;
   0,78]). Como pide la decisión de #239, se informa así: **el grafo no agrega capacidad predictiva en
   D1 y su aporte queda en la explicabilidad.**
3. **Hay señal del microbioma:** `ridge_family` mejora a `ridge_design` (−0,29 pp [−0,51; −0,07]). Es
   la primera evidencia de este proyecto de que el perfil por familia aporta por sobre el diseño, en
   una comparación sin corregir por multiplicidad.
4. **La GNN no aprovecha esa señal**, aunque recibe la misma información. No se puede atribuir solo al
   grafo: también puede deberse a la arquitectura, a la escala de las columnas de linaje tras promediar
   876 nodos o al ajuste, que no se buscó por brazo. Ninguna de esas causas se probó; queda como trabajo
   aparte para no ajustar con el test.

El reporte completo y las demás métricas están en
[`reports/gnn/d1_taxon_identity/report.md`](../../reports/gnn/d1_taxon_identity/report.md).

**Procedencia.** Los primeros 216 folds de GNN y los 150 de `ridge` salieron del commit `9bed0c2`, y el
resto del commit que introdujo `for_training`, que quita la trazabilidad de los lotes. Dos folds del
primer tramo, repetidos con el código nuevo, dieron un `fraction_mae_pp` idéntico.

## 5. Rendimiento

`for_training` (`nutrigraphdt.models.gnn.batching`) quita de cada lote los atributos de trazabilidad.
PyG los recorría elemento por elemento, y eran casi todo el tiempo de entrenamiento: un fold pasó de
unos 15 s a 1,5 s en GPU, con predicciones, historial y violaciones idénticos
(`tests/unit/test_training_batch_view.py`). Los grafos originales conservan su procedencia.

## Limitaciones

- La identidad por familia no distingue géneros de una misma familia, salvo los 38 con aristas.
- `top_k` y `min_prevalence` no son valores científicos.
- Con 56 animales, las diferencias tienen una incertidumbre amplia.
