# Construcción de la tabla de atributos para modelos no basados en grafos (A40-3)

Este documento describe la especificación formal del módulo `nutrigraphdt.models.tabular`,
cuyo objetivo es transformar la información biológica y experimental del grafo en un
formato tabular estandarizado (una fila por animal o muestra) para entrenar baselines
comparables (`DummyRegressor`, `Ridge`, `ElasticNet`, `RandomForest`, `LightGBM`) frente
a las redes neuronales de grafos (GNN).

## 1. Columnas de atributos ($X$) y espacio de características

Cada muestra individual ($i$) se mapea a una fila con las siguientes categorías de atributos:

1. **Abundancias taxonómicas (`taxon:<node_id>`)**:
   - Para datos reales (D1 HoloFood), se extraen de las features de nodo `taxon` del
     grafo heterogéneo (`build_hetero_graph`) y de la tabla `features` de `attach_sample_context`.
   - Para datos sintéticos, de los nodos `taxon` del `SyntheticDataset`.
   - Valores continuos de abundancia relativa o conteos normalizados.
2. **Tratamiento dietario (`diet:treatment` y `diet:composition:<component>`)**:
   - En D1 HoloFood, el brazo de tratamiento experimental asignado por corral (`diet_treatment`,
     con los nombres de la API: `"Control"`, `"Probiotic"` y `"Prebiotic"`). `"Prebiotic"` es el
     tratamiento `CE`, un **fitobiótico** (extracto de uva blanca): en resultados se rotula así
     (D-02 de la respuesta de Investigación).
   - En el dataset sintético, las variables nutricionales composicionales (`crude_protein`,
     `crude_fiber`, `crude_fat`, `metabolizable_energy`, `calcium`, `total_phosphorus`).
3. **Aditivos (`additive:<node_id>:dose`, etc.)**:
   - En datos con suplementación (sintéticos o futuros ensayos), dosis, categoría y tipo de control.
   - En D1 HoloFood no existen nodos de aditivo.
4. **Variables del huésped (`host:body_weight_g`, etc.)**:
   - Covariables numéricas del animal (ej. peso vivo en gramos `body_weight_g`, edad en días).

## 2. Columnas objetivo ($y$)

Las tres variables objetivo canónicas corresponden a las concentraciones molares de
ácidos grasos de cadena corta (AGCC):
- `acetate`
- `propionate`
- `butyrate`

En D1 HoloFood, se extraen de la tabla `targets` (donde viven en los nodos `metabolite`
medidos en el contenido cecal). En datos sintéticos, de `outputs.jsonl`.

## 3. Prevención estricta de fuga de datos (No Target Leakage)

El módulo implementa `TabularDataset.verify_no_target_leakage()` como salvaguarda
inmutable durante la construcción:
1. Ninguna columna objetivo (`acetate`, `propionate`, `butyrate`) puede formar parte
   de los nombres de columnas de $X$.
2. Ningún atributo con prefijo `metabolite:` o `target:` se admite en $X$.
3. En atributos no taxonómicos, los términos relacionados con AGCC (`scfa`, `acetate`,
   `propionate`, `butyrate`) son rechazados automáticamente.
4. Los taxones con epítetos biológicos válidos (como *butyrate-producing bacterium*)
   se diferencian de variables de metabolito y se conservan como covariables del microbioma.

## 4. Partición Train / Val / Test (A40-1)

El dataset tabular se integra directamente con la partición canónica de `get_split()`
(A40-1, #71):
- Cada muestra se etiqueta con su subconjunto (`train`, `val`, `test`).
- Ningún animal ni corral (`pen_code`) aparece en más de un subconjunto.
- Métodos auxiliares `dataset.train_dataset`, `dataset.val_dataset`, `dataset.test_dataset`
  y `dataset.get_split_matrices(subset_name)` devuelven las matrices particionadas con
  dimensiones y vocabularios categóricos idénticos.

## 5. Ejemplo de uso

```python
from nutrigraphdt.data.config import load_sources
from nutrigraphdt.data.integration import attach_sample_context
from nutrigraphdt.data.loaders import MetaboliteLoader, MetadataLoader
from nutrigraphdt.data.pipeline import DataPipeline
from nutrigraphdt.models import build_tabular_dataset, get_split

# 1. Pipeline de datos
sources = load_sources()
tables = DataPipeline({"D1_holofood": sources["D1_holofood"]}).run(["D1_holofood"]).dataset
tables, _ = attach_sample_context(
    tables,
    metadata=MetadataLoader(sources["D1_holofood_metadata"]).load(),
    metabolites=MetaboliteLoader(sources["D1_holofood_scfa_content"]).load(),
)

# 2. Construcción tabular con la partición oficial A40-1
split = get_split()
tab_ds = build_tabular_dataset(tables, split=split)

# 3. Extracción de matrices numéricas para baselines (scikit-learn / LightGBM)
X_train, y_train = tab_ds.get_split_matrices("train", numeric=True, one_hot=True)
X_val, y_val = tab_ds.get_split_matrices("val", numeric=True, one_hot=True)
X_test, y_test = tab_ds.get_split_matrices("test", numeric=True, one_hot=True)
```
